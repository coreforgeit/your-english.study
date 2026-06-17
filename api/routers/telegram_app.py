from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.schemas.telegram_app import TelegramWordsRequest, TelegramWordsResponse
from api.services.telegram_app import TelegramAppService


router = APIRouter(prefix='/telegram-app', tags=['telegram-app'])


@router.post('/words', response_model=TelegramWordsResponse)
async def get_words(
    payload: TelegramWordsRequest,
    session: AsyncSession = Depends(get_session),
) -> TelegramWordsResponse:
    service = TelegramAppService(session)
    words = await service.get_words(payload)
    return TelegramWordsResponse(words=words)
