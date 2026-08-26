import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.schemas.auth_tg import TelegramAuthRequest
from api.services.session import (
    SESSION_COOKIE_NAME,
    SessionService,
    get_session_service,
)
from api.services.telegram_auth import get_telegram_user_id
from api.services.user_settings import UserSettingsService
from core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(tags=['auth'])


@router.post('/auth_tg', response_model=bool)
async def auth_tg(
    payload: TelegramAuthRequest,
    response: Response,
    session_id: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
    sessions: SessionService = Depends(get_session_service),
    session: AsyncSession = Depends(get_session),
) -> bool:
    if settings.debug:
        user_id = 524275902
    else:
        user_id = get_telegram_user_id(payload.init_data, settings.bot_token)

    if user_id is None:
        logger.info('POST /api/auth_tg response: false')
        return False

    session_data = None
    if session_id:
        session_data = await sessions.get(session_id)

    if session_data is None or session_data.user_id != user_id:
        language_level = await UserSettingsService(
            session,
        ).get_effective_language_level(user_id)
        session_id = await sessions.create(
            user_id=user_id,
            language_level=language_level,
        )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not settings.debug,
        samesite='lax',
        path='/',
    )
    response.headers['Cache-Control'] = 'no-store'
    logger.info('POST /api/auth_tg response: true')
    return True
