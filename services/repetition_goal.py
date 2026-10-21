import logging
from datetime import UTC, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import UserSettings
from enums import NotificationType, RedisKey
from services.notifications import build_notification, user_notifications_channel


logger = logging.getLogger(__name__)


class RepetitionGoalCounter:
    DAILY_LIMIT = 30
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    # Инициализация не перезаписывает остаток и не продлевает срок жизни ключа.
    _INITIALIZE_SCRIPT = """
local remaining = redis.call('HGET', KEYS[1], 'remaining')
if remaining then
    return tonumber(remaining)
end
redis.call('HSET', KEYS[1], 'remaining', ARGV[1])
redis.call('EXPIREAT', KEYS[1], ARGV[2])
return tonumber(ARGV[1])
"""

    # Изменение остатка, защита от повторной доставки и событие атомарны.
    _DECREMENT_SCRIPT = """
local remaining = tonumber(redis.call('HGET', KEYS[1], 'remaining'))
if not remaining then
    return -1
end
if remaining <= 0 or redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then
    return remaining
end
redis.call('HSET', KEYS[1], ARGV[1], 1)
remaining = redis.call('HINCRBY', KEYS[1], 'remaining', -1)
if remaining == 0 then
    redis.call('PUBLISH', ARGV[2], ARGV[3])
end
return remaining
"""

    def __init__(self, session: AsyncSession, redis: Redis | None = None) -> None:
        self.session = session
        self.redis = redis if redis is not None else self._redis_client

    async def get_remaining(self, user_id: int) -> int | None:
        value = await self.redis.hget(self._key(user_id), 'remaining')
        return int(value) if value is not None else None

    async def initialize(self, user_id: int, word_count: int) -> int:
        if not 0 <= word_count <= self.DAILY_LIMIT:
            raise ValueError('Количество слов должно быть от 0 до 30')

        expires_at = await self._get_expires_at(user_id)
        return int(await self.redis.eval(
            self._INITIALIZE_SCRIPT,
            1,
            self._key(user_id),
            word_count,
            int(expires_at.timestamp()),
        ))

    async def decrement(self, user_id: int, *, task_id: str) -> int | None:
        notification = build_notification(NotificationType.REPETITIONS_COMPLETED)
        remaining = int(await self.redis.eval(
            self._DECREMENT_SCRIPT,
            1,
            self._key(user_id),
            f'task:{task_id}',
            user_notifications_channel(user_id),
            notification.model_dump_json(),
        ))
        return remaining if remaining >= 0 else None

    async def _get_expires_at(self, user_id: int) -> datetime:
        timezone_value = await self.session.scalar(
            sa.select(UserSettings.timezone).where(UserSettings.user_id == user_id),
        )
        user_timezone: tzinfo = UTC
        if timezone_value is not None:
            try:
                user_timezone = ZoneInfo(str(timezone_value))
            except ZoneInfoNotFoundError:
                logger.warning(
                    f'Для цели повторения используется UTC: '
                    f'неизвестный часовой пояс, user_id={user_id}',
                )

        tomorrow = datetime.now(UTC).astimezone(user_timezone).date() + timedelta(days=1)
        return datetime.combine(tomorrow, time.min, tzinfo=user_timezone).astimezone(UTC)

    @staticmethod
    def _key(user_id: int) -> str:
        return f'{RedisKey.REPETITION_GOAL}:{user_id}'

    @classmethod
    async def close_store(cls) -> None:
        await cls._redis_client.aclose()
