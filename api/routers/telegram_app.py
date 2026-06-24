import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from ai.errors import AudioTranscriptionError
from ai.transcriptions import AudioTranscriptionService
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
    payload, audio_file = await _parse_answer_request(request)
    logger.info(
        'Answer request: user_id=%s word_id=%s answer_type=%s answer_language=%s',
        current_user.id,
        payload.word_id,
        payload.answer_type,
        payload.answer_language,
    )

    service = TelegramAppService(session)

    if payload.answer_type == AnswerType.AUDIO:
        if audio_file is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Audio file is required',
            )

        audio_bytes = await audio_file.read()
        try:
            transcription = await AudioTranscriptionService().transcribe_audio(
                audio=audio_bytes,
                filename=audio_file.filename or 'answer.webm',
                content_type=audio_file.content_type or 'audio/webm',
                language=payload.answer_language,
                trim_silence=False,
            )
        except AudioTranscriptionError as exc:
            logger.exception(f'Ошибка расшифровки аудио: word_id={payload.word_id}')
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='Audio transcription failed',
            ) from exc

        logger.info(
            f'Аудио расшифровано: word_id={payload.word_id}, '
            f'text={transcription.text!r}'
        )
        check_result = await service.check_text_answer(
            word_id=payload.word_id,
            answer_language=payload.answer_language,
            answer=transcription.text,
        )
        if check_result is None:
            logger.info(f'Ответ отклонен: слово не найдено word_id={payload.word_id}')
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Word not found',
            )

        await service.save_answer_error(
            user_id=current_user.id,
            word_id=payload.word_id,
            answer_type=payload.answer_type,
            answer_language=payload.answer_language,
            user_answer=transcription.text,
            check_result=check_result,
        )

        return TelegramWordAnswerResponse(
            data=TelegramWordAnswerData(
                success=True,
                answer=transcription.text,
                is_correct=check_result.is_correct,
                has_typo=check_result.has_typo,
                typo=check_result.typo,
            ),
        )

    if payload.answer is None:
        logger.info('Text answer rejected: answer is missing word_id=%s', payload.word_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Text answer is required',
        )

    text_answer = payload.answer.strip()
    check_result = await service.check_text_answer(
        word_id=payload.word_id,
        answer_language=payload.answer_language,
        answer=text_answer,
    )
    if check_result is None:
        logger.info('Answer rejected: word not found word_id=%s', payload.word_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    await service.save_answer_error(
        user_id=current_user.id,
        word_id=payload.word_id,
        answer_type=payload.answer_type,
        answer_language=payload.answer_language,
        user_answer=text_answer,
        check_result=check_result,
    )

    return TelegramWordAnswerResponse(
        data=TelegramWordAnswerData(
            success=True,
            answer=text_answer,
            is_correct=check_result.is_correct,
            has_typo=check_result.has_typo,
            typo=check_result.typo,
        ),
    )


async def _parse_answer_request(
    request: Request,
) -> tuple[TelegramWordAnswerRequest, UploadFile | None]:
    content_type = request.headers.get('content-type', '')
    audio_file = None

    if content_type.startswith('multipart/form-data'):
        form = await request.form()
        raw_audio_file = form.get('audio_file')
        if isinstance(raw_audio_file, StarletteUploadFile):
            audio_file = raw_audio_file

        raw_payload = {
            'word_id': form.get('word_id'),
            'answer_type': form.get('answer_type'),
            'answer_language': form.get('answer_language'),
            'answer': form.get('answer'),
        }
    else:
        raw_payload = await request.json()

    try:
        return TelegramWordAnswerRequest.model_validate(raw_payload), audio_file
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
