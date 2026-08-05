import hashlib
import secrets

from redis.asyncio import Redis

from core.config import settings


SESSION_COOKIE_NAME = 'tg_session'
SESSION_TTL_SECONDS = 60 * 60


redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class SessionService:
    def __init__(self, redis: Redis = redis_client):
        self.redis = redis

    async def create(self, user_id: int) -> str:
        session_id = secrets.token_urlsafe(32)
        await self.redis.set(
            self._key(session_id),
            str(user_id),
            ex=SESSION_TTL_SECONDS,
        )
        return session_id

    async def get_user_id(self, session_id: str) -> int | None:
        user_id = await self.redis.getex(
            self._key(session_id),
            ex=SESSION_TTL_SECONDS,
        )
        if user_id is None:
            return None

        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def get_session_id(session_token: str) -> str:
        return hashlib.sha256(session_token.encode()).hexdigest()

    @classmethod
    def _key(cls, session_token: str) -> str:
        return f'telegram-session:{cls.get_session_id(session_token)}'


session_service = SessionService()


def get_session_service() -> SessionService:
    return session_service


async def close_session_store() -> None:
    await redis_client.aclose()
