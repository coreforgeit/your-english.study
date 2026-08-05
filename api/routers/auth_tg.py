from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from api.schemas.auth_tg import TelegramAuthRequest
from api.services.session import (
    SESSION_COOKIE_NAME,
    SessionService,
    get_session_service,
)
from api.services.telegram_auth import get_telegram_user_id
from core.config import settings


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
) -> bool:
    if settings.debug:
        user_id = 524275902
    else:
        user_id = get_telegram_user_id(payload.init_data, settings.bot_token)

    if user_id is None:
        return False

    session_user_id = None
    if session_id:
        session_user_id = await sessions.get_user_id(session_id)

    if session_user_id != user_id:
        session_id = await sessions.create(user_id)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not settings.debug,
        samesite='lax',
        path='/',
    )
    response.headers['Cache-Control'] = 'no-store'
    return True
