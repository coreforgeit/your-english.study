import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from aiogram import Bot
from apscheduler.triggers.cron import CronTrigger

from core.config import settings as app_settings
from db.models import UserSettings
from db.session import async_session_factory
from enums import ReminderKey
from services import VocabularyRepetitionService
from worker.broker import broker
from worker.scheduler import register_scheduler_initializer, scheduler


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReminderSettingsSnapshot:
    reminders_enabled: bool | None
    reminder_time: time | None
    timezone: str | None


def _make_reminder_settings_snapshot(
    user_settings: UserSettings,
) -> ReminderSettingsSnapshot:
    return ReminderSettingsSnapshot(
        reminders_enabled=user_settings.reminders_enabled,
        reminder_time=user_settings.reminder_time,
        timezone=(
            str(user_settings.timezone)
            if user_settings.timezone is not None
            else None
        ),
    )


async def _get_reminder_settings(
    user_id: int,
) -> ReminderSettingsSnapshot | None:
    async with async_session_factory() as session:
        user_settings = await session.scalar(
            sa.select(UserSettings).where(UserSettings.user_id == user_id),
        )

    if user_settings is None:
        return None

    return _make_reminder_settings_snapshot(user_settings)


async def _get_all_reminder_settings() -> dict[int, ReminderSettingsSnapshot]:
    async with async_session_factory() as session:
        result = await session.scalars(sa.select(UserSettings))
        user_settings = result.all()

    return {
        settings.user_id: _make_reminder_settings_snapshot(settings)
        for settings in user_settings
    }


def _get_next_reminder_at_utc(
    reminder_time: time,
    timezone: ZoneInfo,
    *,
    now_utc: datetime | None = None,
) -> datetime:
    current_utc = now_utc or datetime.now(UTC)
    if current_utc.tzinfo is None:
        raise ValueError('now_utc must be timezone-aware')

    current_local = current_utc.astimezone(timezone)
    normalized_time = reminder_time.replace(tzinfo=None, microsecond=0)
    next_local = datetime.combine(
        current_local.date(),
        normalized_time,
        tzinfo=timezone,
    )
    if next_local <= current_local:
        next_local += timedelta(days=1)

    return next_local.astimezone(UTC)


def _remove_reminder_job(user_id: int) -> bool:
    job_id = ReminderKey.DAILY_WORD_LEARNING.for_user(user_id)
    if scheduler.get_job(job_id) is None:
        return False

    scheduler.remove_job(job_id)
    return True


async def _has_due_repetition_words(user_id: int) -> bool:
    async with async_session_factory() as session:
        return await VocabularyRepetitionService(session).has_due_words(user_id)


async def _send_daily_word_learning_reminder(*, user_id: int) -> None:
    user_settings = await _get_reminder_settings(user_id)
    if user_settings is None:
        _remove_reminder_job(user_id)
        logger.warning(
            f'Настройки для ежедневного напоминания не найдены: '
            f'user_id={user_id}',
        )
        return

    if user_settings.reminders_enabled is not True:
        _remove_reminder_job(user_id)
        logger.info(
            f'Ежедневное напоминание отключено: user_id={user_id}',
        )
        return

    try:
        has_due_words = await _has_due_repetition_words(user_id)
    except Exception:
        logger.exception(
            f'Не удалось проверить слова для повторения: user_id={user_id}',
        )
        raise

    if not has_due_words:
        logger.info(
            f'Напоминание пропущено: нет слов для повторения, '
            f'user_id={user_id}',
        )
        return

    if not app_settings.bot_token:
        logger.error(
            f'Не задан production-токен Telegram-бота: user_id={user_id}',
        )
        return

    try:
        async with Bot(token=app_settings.bot_token) as bot:
            await bot.send_message(
                chat_id=user_id,
                text='Напоминание тест',
            )
    except Exception:
        logger.exception(
            f'Не удалось отправить ежедневное напоминание: '
            f'user_id={user_id}',
        )
        raise

    logger.info(
        f'Ежедневное напоминание отправлено: user_id={user_id}',
    )


async def _schedule_daily_word_learning_reminder(
    user_id: int,
    user_settings: ReminderSettingsSnapshot | None = None,
) -> bool:
    job_id = ReminderKey.DAILY_WORD_LEARNING.for_user(user_id)
    if user_settings is None:
        user_settings = await _get_reminder_settings(user_id)

    if user_settings is None:
        _remove_reminder_job(user_id)
        logger.warning(
            f'Настройки для ежедневного напоминания не найдены: '
            f'user_id={user_id}',
        )
        return False

    if (
        user_settings.reminders_enabled is None
        or user_settings.reminder_time is None
        or user_settings.timezone is None
    ):
        _remove_reminder_job(user_id)
        logger.warning(
            f'Напоминание не создано: неполные настройки, user_id={user_id}',
        )
        return False

    if user_settings.reminders_enabled is False:
        if _remove_reminder_job(user_id):
            logger.info(
                f'Ежедневное напоминание удалено: user_id={user_id}',
            )
        return False

    try:
        user_timezone = ZoneInfo(user_settings.timezone)
    except ZoneInfoNotFoundError:
        _remove_reminder_job(user_id)
        logger.warning(
            f'Ежедневное напоминание не создано: '
            f'неизвестный часовой пояс, user_id={user_id}',
        )
        return False

    next_run_at_utc = _get_next_reminder_at_utc(
        user_settings.reminder_time,
        user_timezone,
    )
    trigger = CronTrigger(
        hour=user_settings.reminder_time.hour,
        minute=user_settings.reminder_time.minute,
        second=user_settings.reminder_time.second,
        start_date=next_run_at_utc,
        timezone=user_timezone,
    )

    scheduler.add_job(
        _send_daily_word_learning_reminder,
        trigger=trigger,
        id=job_id,
        kwargs={'user_id': user_id},
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    logger.info(
        f'Ежедневное напоминание запланировано: user_id={user_id} '
        f'next_run_at_utc={next_run_at_utc.isoformat()}',
    )
    return True


async def _rebuild_daily_word_learning_reminders() -> None:
    all_user_settings = await _get_all_reminder_settings()
    reminder_key_prefix = f'{ReminderKey.DAILY_WORD_LEARNING.value}:'

    for job in scheduler.get_jobs():
        if job.id.startswith(reminder_key_prefix):
            scheduler.remove_job(job.id)

    scheduled_count = 0
    for user_id, user_settings in all_user_settings.items():
        is_scheduled = await _schedule_daily_word_learning_reminder(
            user_id,
            user_settings,
        )
        scheduled_count += int(is_scheduled)

    logger.info(
        f'Ежедневные напоминания восстановлены: '
        f'пользователей={len(all_user_settings)}, '
        f'задач={scheduled_count}',
    )


register_scheduler_initializer(_rebuild_daily_word_learning_reminders)


@broker.task
async def send_daily_word_learning_reminder(
    *,
    user_id: int,
) -> None:
    await _schedule_daily_word_learning_reminder(user_id)
