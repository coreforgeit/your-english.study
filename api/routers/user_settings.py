from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.schemas.user_settings import (
    UserSettingsData,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from api.services.user_settings import UserSettingsService


router = APIRouter(prefix='/telegram-app/settings', tags=['user-settings'])


@router.get('', response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> UserSettingsResponse:
    settings = await UserSettingsService(session).get_for_user(current_user.id)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User settings not found',
        )

    return UserSettingsResponse(data=UserSettingsData.model_validate(settings))


@router.patch('', response_model=UserSettingsResponse)
async def update_user_settings(
    payload: UserSettingsUpdate,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> UserSettingsResponse:
    settings = await UserSettingsService(session).update_for_user(
        current_user.id,
        payload.model_dump(exclude_unset=True),
    )
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User settings not found',
        )

    return UserSettingsResponse(data=UserSettingsData.model_validate(settings))
