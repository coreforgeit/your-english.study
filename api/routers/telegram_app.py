import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.schemas.telegram_app import (
    AnswerType,
    TelegramWordAnswerData,
    TelegramWordAnswerRequest,
    TelegramWordAnswerResponse,
    TelegramWordsRequest,
    TelegramWordsResponse,
)
from api.services.telegram_app import TelegramAppService


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/telegram-app', tags=['telegram-app'])


@router.post('/words/reapit', response_model=TelegramWordsResponse)
async def repeat_word(
    payload: TelegramWordsRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> TelegramWordsResponse:
    logger.info(
        'Repeat word request: user_id=%s level=%s',
        current_user.id,
        payload.level,
    )
    service = TelegramAppService(session)
    word = await service.get_learned_word_for_user(
        user_id=current_user.id,
        payload=payload,
    )
    if word is None:
        logger.info(
            'Repeat word response failed: no learned word found user_id=%s level=%s',
            current_user.id,
            payload.level,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    return TelegramWordsResponse(data=word)


@router.post('/words/learn', response_model=TelegramWordsResponse)
async def learn_word(
    payload: TelegramWordsRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> TelegramWordsResponse:
    logger.info(
        'Learn word request: user_id=%s level=%s',
        current_user.id,
        payload.level,
    )
    service = TelegramAppService(session)
    word = await service.get_new_word_for_user(
        user_id=current_user.id,
        payload=payload,
    )
    if word is None:
        logger.info(
            'Learn word response failed: no new word found user_id=%s level=%s',
            current_user.id,
            payload.level,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    return TelegramWordsResponse(data=word)


@router.post('/words/answer', response_model=TelegramWordAnswerResponse)
async def answer_word(
    request: Request,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> TelegramWordAnswerResponse:
    payload = await _parse_answer_request(request)
    logger.info(
        'Answer request: user_id=%s word_id=%s answer_type=%s answer_language=%s',
        current_user.id,
        payload.word_id,
        payload.answer_type,
        payload.answer_language,
    )

    if payload.answer_type == AnswerType.AUDIO:
        logger.info('Audio answer accepted: word_id=%s', payload.word_id)
        return TelegramWordAnswerResponse(
            data=TelegramWordAnswerData(success=True),
        )

    if payload.answer is None:
        logger.info('Text answer rejected: answer is missing word_id=%s', payload.word_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Text answer is required',
        )

    service = TelegramAppService(session)
    is_correct = await service.check_text_answer(
        word_id=payload.word_id,
        answer_language=payload.answer_language,
        answer=payload.answer,
    )
    if is_correct is None:
        logger.info('Answer rejected: word not found word_id=%s', payload.word_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    return TelegramWordAnswerResponse(
        data=TelegramWordAnswerData(success=True, is_correct=is_correct),
    )


async def _parse_answer_request(request: Request) -> TelegramWordAnswerRequest:
    content_type = request.headers.get('content-type', '')

    if content_type.startswith('multipart/form-data'):
        form = await request.form()
        raw_payload = {
            'word_id': form.get('word_id'),
            'answer_type': form.get('answer_type'),
            'answer_language': form.get('answer_language'),
            'answer': form.get('answer'),
        }
    else:
        raw_payload = await request.json()

    try:
        return TelegramWordAnswerRequest.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
