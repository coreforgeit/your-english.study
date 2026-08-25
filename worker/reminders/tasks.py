import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from apscheduler.triggers.cron import CronTrigger

from core.config import settings as app_settings
from db.models import UserSettings
from db.session import async_session_factory
from enums import AppLaunchMode, ReminderKey, WorkerTaskName
from services import VocabularyRepetitionService
from worker.broker import broker
from worker.scheduler import register_scheduler_initializer, scheduler


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReminderSettingsSnapshot:
    reminders_enabled: bool | None
    reminder_time: time | None
    timezone: str | None


class DailyWordLearningReminder:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    @staticmethod
    def _make_settings_snapshot(
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

    async def _get_settings(self) -> ReminderSettingsSnapshot | None:
        async with async_session_factory() as session:
            user_settings = await session.scalar(
                sa.select(UserSettings).where(
                    UserSettings.user_id == self.user_id,
                ),
            )

        if user_settings is None:
            return None

        return self._make_settings_snapshot(user_settings)

    @classmethod
    async def _get_all_settings(
        cls,
    ) -> dict[int, ReminderSettingsSnapshot]:
        async with async_session_factory() as session:
            result = await session.scalars(sa.select(UserSettings))
            user_settings = result.all()

        return {
            settings.user_id: cls._make_settings_snapshot(settings)
            for settings in user_settings
        }

    @staticmethod
    def _get_next_run_at_utc(
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

    def _remove_job(self) -> bool:
        job_id = ReminderKey.DAILY_WORD_LEARNING.for_user(self.user_id)
        if scheduler.get_job(job_id) is None:
            return False

        scheduler.remove_job(job_id)
        return True

    async def _has_due_words(self) -> bool:
        async with async_session_factory() as session:
            return await VocabularyRepetitionService(session).has_due_words(
                self.user_id,
            )

    @staticmethod
    def _get_app_launch_url(mode: AppLaunchMode) -> str:
        app_url = urlsplit(app_settings.app_url)
        query = [
            (key, value)
            for key, value in parse_qsl(
                app_url.query,
                keep_blank_values=True,
            )
            if key != 'mode'
        ]
        query.append(('mode', mode.value))
        return urlunsplit(app_url._replace(query=urlencode(query)))

    async def send(self) -> None:
        user_settings = await self._get_settings()
        if user_settings is None:
            self._remove_job()
            logger.warning(
                f'Настройки для ежедневного напоминания не найдены: '
                f'user_id={self.user_id}',
            )
            return

        if not user_settings.reminders_enabled:
            self._remove_job()
            logger.info(
                f'Ежедневное напоминание отключено: '
                f'user_id={self.user_id}',
            )
            return

        try:
            has_due_words = await self._has_due_words()
        except Exception:
            logger.exception(
                f'Не удалось проверить слова для повторения: '
                f'user_id={self.user_id}',
            )
            raise

        if not has_due_words:
            logger.info(
                f'Напоминание пропущено: нет слов для повторения, '
                f'user_id={self.user_id}',
            )
            return

        if not app_settings.bot_token:
            logger.error(
                f'Не задан production-токен Telegram-бота: '
                f'user_id={self.user_id}',
            )
            return

        try:
            async with Bot(token=app_settings.bot_token) as bot:
                await bot.send_message(
                    chat_id=self.user_id,
                    text='Пора повторить изученные слова.',
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text='Начать повторение',
                                    web_app=WebAppInfo(
                                        url=self._get_app_launch_url(
                                            AppLaunchMode.REPEAT,
                                        ),
                                    ),
                                ),
                            ],
                        ],
                    ),
                )
        except Exception:
            logger.exception(
                f'Не удалось отправить ежедневное напоминание: '
                f'user_id={self.user_id}',
            )
            raise

        logger.info(
            f'Ежедневное напоминание отправлено: user_id={self.user_id}',
        )

    @staticmethod
    async def run_scheduled(*, user_id: int) -> None:
        await DailyWordLearningReminder(user_id).send()

    async def schedule(
        self,
        user_settings: ReminderSettingsSnapshot | None = None,
    ) -> bool:
        job_id = ReminderKey.DAILY_WORD_LEARNING.for_user(self.user_id)
        if user_settings is None:
            user_settings = await self._get_settings()

        if user_settings is None:
            self._remove_job()
            logger.warning(
                f'Настройки для ежедневного напоминания не найдены: '
                f'user_id={self.user_id}',
            )
            return False

        if (
            not user_settings.reminders_enabled
            or user_settings.reminder_time is None
            or user_settings.timezone is None
        ):
            self._remove_job()
            logger.warning(
                f'Напоминание не создано user_id={self.user_id}',
            )
            return False

        try:
            user_timezone = ZoneInfo(user_settings.timezone)
        except ZoneInfoNotFoundError:
            self._remove_job()
            logger.warning(
                f'Ежедневное напоминание не создано: '
                f'неизвестный часовой пояс, user_id={self.user_id}',
            )
            return False

        next_run_at_utc = self._get_next_run_at_utc(
            reminder_time=user_settings.reminder_time,
            timezone=user_timezone,
        )
        trigger = CronTrigger(
            hour=user_settings.reminder_time.hour,
            minute=user_settings.reminder_time.minute,
            second=user_settings.reminder_time.second,
            start_date=next_run_at_utc,
            timezone=user_timezone,
        )

        scheduler.add_job(
            DailyWordLearningReminder.run_scheduled,
            trigger=trigger,
            id=job_id,
            kwargs={'user_id': self.user_id},
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        logger.info(
            f'Ежедневное напоминание запланировано: '
            f'user_id={self.user_id} '
            f'next_run_at_utc={next_run_at_utc.isoformat()}',
        )
        return True

    @classmethod
    async def rebuild_all(cls) -> None:
        all_user_settings = await cls._get_all_settings()
        reminder_key_prefix = f'{ReminderKey.DAILY_WORD_LEARNING.value}:'

        for job in scheduler.get_jobs():
            if job.id.startswith(reminder_key_prefix):
                scheduler.remove_job(job.id)

        scheduled_count = 0
        for user_id, user_settings in all_user_settings.items():
            is_scheduled = await cls(user_id).schedule(user_settings)
            scheduled_count += int(is_scheduled)

        logger.info(
            f'Ежедневные напоминания восстановлены: '
            f'пользователей={len(all_user_settings)}, '
            f'задач={scheduled_count}',
        )


register_scheduler_initializer(DailyWordLearningReminder.rebuild_all)


@broker.task(task_name=WorkerTaskName.DAILY_WORD_LEARNING_REMINDER.value)
async def send_daily_word_learning_reminder(
    *,
    user_id: int,
) -> None:
    reminder = DailyWordLearningReminder(user_id)
    await reminder.schedule()
