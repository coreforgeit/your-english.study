import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.schemas.common import ApiResponse
from api.schemas.user_settings import (
    LanguageLevelData,
    UserSettingsData,
    UserSettingsUpdate,
)
from api.services.user_settings import UserSettingsService
from task_queue.tasks import send_daily_word_learning_reminder

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/telegram-app/settings', tags=['user-settings'])


@router.get(
    '/language-levels',
    response_model=ApiResponse[list[LanguageLevelData]],
)
async def get_language_levels(
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[list[LanguageLevelData]]:
    levels = await UserSettingsService(session).get_language_levels()
    return ApiResponse[list[LanguageLevelData]](
        data=[LanguageLevelData.model_validate(level) for level in levels],
    )


@router.get('', response_model=ApiResponse[UserSettingsData])
async def get_user_settings(
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserSettingsData]:

    logger.info(f'get_user_settings')
    settings = await UserSettingsService(session).get_for_user(current_user.id)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User settings not found',
        )

    data = UserSettingsData.model_validate(settings)
    logger.info(f'get_user_settings: {data}')
    return ApiResponse[UserSettingsData](
        data=data,
    )


@router.patch('', response_model=ApiResponse[UserSettingsData])
async def update_user_settings(
    payload: UserSettingsUpdate,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserSettingsData]:
    settings = await UserSettingsService(session).update_for_user(
        current_user.id,
        payload.model_dump(exclude_unset=True),
    )
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User settings not found',
        )

    await session.commit()
    await send_daily_word_learning_reminder.kiq(user_id=current_user.id)

    return ApiResponse[UserSettingsData](
        data=UserSettingsData.model_validate(settings),
    )
