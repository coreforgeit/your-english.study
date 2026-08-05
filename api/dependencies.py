from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.session import (
    SESSION_COOKIE_NAME,
    SessionService,
    get_session_service,
)
from db.session import async_session_factory


@dataclass(frozen=True, slots=True)
class CurrentTelegramUser:
    id: int
    session_id: str


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_telegram_user(
    session_id: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
    sessions: SessionService = Depends(get_session_service),
) -> CurrentTelegramUser:
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Session is missing',
        )

    try:
        user_id = await sessions.get_user_id(session_id)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Session store is unavailable',
        ) from exc

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Session is invalid or expired',
        )

    return CurrentTelegramUser(
        id=user_id,
        session_id=sessions.get_session_id(session_id),
    )
