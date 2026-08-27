import logging
from datetime import UTC, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import LearnedWord, UserSettings, WordEn
from enums import LearnedWordStatus, NotificationType
from services.notifications import build_notification, user_notifications_channel


logger = logging.getLogger(__name__)
notification_redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)

NEW_WORDS_MILESTONES: dict[int, NotificationType] = {
    5: NotificationType.FIVE_NEW_WORDS_TODAY,
    10: NotificationType.TEN_NEW_WORDS_TODAY,
}


class NotificationPublisher:
    def __init__(self, redis: Redis | None = None) -> None:
        self.redis = redis if redis is not None else notification_redis_client

    async def publish(
        self,
        user_id: int,
        notification_type: NotificationType,
        **context: str,
    ) -> None:
        notification = build_notification(notification_type, **context)
        await self.redis.publish(
            user_notifications_channel(user_id),
            notification.model_dump_json(),
        )


class NewWordsMilestoneNotificationAction:
    def __init__(
        self,
        session: AsyncSession,
        publisher: NotificationPublisher | None = None,
    ) -> None:
        self.session = session
        self.publisher = (
            publisher if publisher is not None else NotificationPublisher()
        )

    async def execute(
        self,
        user_id: int,
        *,
        now_utc: datetime | None = None,
    ) -> NotificationType | None:
        user_timezone = await self._get_user_timezone(user_id)
        start_utc, end_utc = self._get_local_day_bounds_utc(
            user_timezone,
            now_utc=now_utc,
        )
        learned_words_count = await self.session.scalar(
            sa.select(sa.func.count(LearnedWord.id)).where(
                LearnedWord.user_id == user_id,
                LearnedWord.created_at >= start_utc,
                LearnedWord.created_at < end_utc,
            ),
        )
        notification_type = NEW_WORDS_MILESTONES.get(
            int(learned_words_count or 0),
        )
        if notification_type is None:
            return None

        await self.publisher.publish(user_id, notification_type)
        return notification_type

    async def _get_user_timezone(self, user_id: int) -> tzinfo:
        timezone_value = await self.session.scalar(
            sa.select(UserSettings.timezone).where(
                UserSettings.user_id == user_id,
            ),
        )
        if timezone_value is None:
            return UTC

        try:
            return ZoneInfo(str(timezone_value))
        except ZoneInfoNotFoundError:
            logger.warning(
                f'Для подсчёта новых слов используется UTC: '
                f'неизвестный часовой пояс, user_id={user_id}',
            )
            return UTC

    @staticmethod
    def _get_local_day_bounds_utc(
        user_timezone: tzinfo,
        *,
        now_utc: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        current_utc = now_utc or datetime.now(UTC)
        if current_utc.tzinfo is None:
            raise ValueError('now_utc должен содержать часовой пояс')

        current_local = current_utc.astimezone(user_timezone)
        start_local = datetime.combine(
            current_local.date(),
            time.min,
            tzinfo=user_timezone,
        )
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)


class WordStatusChangedNotificationAction:
    def __init__(
        self,
        session: AsyncSession,
        publisher: NotificationPublisher | None = None,
    ) -> None:
        self.session = session
        self.publisher = (
            publisher if publisher is not None else NotificationPublisher()
        )

    async def execute(
        self,
        *,
        user_id: int,
        word_id: int,
        status: LearnedWordStatus,
    ) -> NotificationType | None:
        word = await self.session.scalar(
            sa.select(WordEn.word).where(WordEn.id == word_id),
        )
        if not word:
            logger.warning(
                f'Уведомление о смене статуса не отправлено: '
                f'слово не найдено, user_id={user_id} word_id={word_id}',
            )
            return None

        if status == LearnedWordStatus.LEARNED:
            notification_type = NotificationType.WORD_LEARNED
            context = {'word': word}
        else:
            notification_type = NotificationType.WORD_STATUS_CHANGED
            context = {
                'word': word,
                'status': self._get_status_label(status),
            }

        await self.publisher.publish(
            user_id,
            notification_type,
            **context,
        )
        return notification_type

    @staticmethod
    def _get_status_label(status: LearnedWordStatus) -> str:
        if status == LearnedWordStatus.NEW:
            return 'новое'
        if status == LearnedWordStatus.FAMILIAR:
            return 'знакомое'
        return 'изучено'
