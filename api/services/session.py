import hashlib
import secrets

from redis.asyncio import Redis

from api.schemas.session import SessionData
from core.config import settings
from enums import RedisKey


SESSION_COOKIE_NAME = 'tg_session'
SESSION_TTL_SECONDS = 60 * 60


redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class SessionService:
    def __init__(self, redis: Redis = redis_client):
        self.redis = redis

    async def create(
        self,
        user_id: int,
        language_level: int | None,
    ) -> str:
        session_id = secrets.token_urlsafe(32)
        session_data = SessionData(
            user_id=user_id,
            language_level=language_level,
        )
        await self.redis.set(
            self._key(session_id),
            session_data.model_dump_json(),
            ex=SESSION_TTL_SECONDS,
        )
        return session_id

    async def get(self, session_id: str) -> SessionData | None:
        key = self._key(session_id)
        raw_session = await self.redis.getex(
            key,
            ex=SESSION_TTL_SECONDS,
        )
        if raw_session is None:
            return None

        try:
            return SessionData.model_validate_json(raw_session)
        except (TypeError, ValueError):
            await self.redis.delete(key)
            return None

    @staticmethod
    def get_session_id(session_token: str) -> str:
        return hashlib.sha256(session_token.encode()).hexdigest()

    @classmethod
    def _key(cls, session_token: str) -> str:
        return f'{RedisKey.TELEGRAM_SESSION}:{cls.get_session_id(session_token)}'


session_service = SessionService()


def get_session_service() -> SessionService:
    return session_service


async def close_session_store() -> None:
    await redis_client.aclose()
