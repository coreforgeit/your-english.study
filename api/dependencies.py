from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session_factory


@dataclass(frozen=True, slots=True)
class CurrentTelegramUser:
    id: int


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_telegram_user() -> CurrentTelegramUser:
    return CurrentTelegramUser(id=524275902)
