import logging
import unicodedata
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from ai.errors import AudioTranscriptionError
from ai.transcriptions import AudioTranscriptionService
from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.schemas.vocabulary import (
    VocabularyIntervalRepetitionsResponse,
    VocabularyWordAnswerData,
    VocabularyWordAnswerRequest,
    VocabularyWordAnswerResponse,
    VocabularyWordsRequest,
    VocabularyWordsResponse,
    WordReviewRequest,
    WordReviewResponse,
)
from api.services.audio_answer_samples import AudioAnswerSampleService
from api.services.vocabulary import VocabularyService
from db.models import WordEn
from enums import AnswerType, TextModel, WordStatus
from worker.vocabulary.tasks import record_word_repetition, review_word


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/telegram-app', tags=['vocabulary'])


@router.get(
    '/words/interval-repetitions',
    response_model=VocabularyIntervalRepetitionsResponse,
)
async def get_interval_repetitions(
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> VocabularyIntervalRepetitionsResponse:
    service = VocabularyService(session)
    word_ids = await service.get_interval_repetition_word_ids(current_user.id)
    return VocabularyIntervalRepetitionsResponse(data=word_ids)


@router.post('/words/reapit', response_model=VocabularyWordsResponse)
async def repeat_word(
    payload: VocabularyWordsRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> VocabularyWordsResponse:
    logger.info(
        'Repeat word request: user_id=%s level=%s',
        current_user.id,
        payload.level,
    )
    service = VocabularyService(session)
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

    return VocabularyWordsResponse(data=word)


@router.post('/words/learn', response_model=VocabularyWordsResponse)
async def learn_word(
    payload: VocabularyWordsRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> VocabularyWordsResponse:
    logger.info(
        'Learn word request: user_id=%s level=%s',
        current_user.id,
        payload.level,
    )
    service = VocabularyService(session)
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

    if not word.is_reviewed:
        await review_word.kiq(
            word_id=word.id,
            model=WordReviewRequest().model,
        )

    return VocabularyWordsResponse(data=word)


@router.post(
    path='/words/{word_id}/review',
    response_model=WordReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_word_review(
    word_id: int,
    payload: WordReviewRequest | None = None,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> WordReviewResponse:
    word = await session.get(WordEn, word_id)
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Word not found')

    model = payload.model if payload is not None else WordReviewRequest().model

    word.status = WordStatus.CHECKING
    await session.flush()

    await review_word.kiq(
        word_id=word.id,
        model=model.value,
    )

    return WordReviewResponse(success=True)


@router.post('/words/answer', response_model=VocabularyWordAnswerResponse)
async def answer_word(
    request: Request,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> VocabularyWordAnswerResponse:
    total_started_at = perf_counter()
    payload, audio_file = await _parse_answer_request(request)

    logger.info(
        'Answer request: user_id=%s word_id=%s answer_type=%s answer_language=%s',
        current_user.id,
        payload.word_id,
        payload.answer_type,
        payload.answer_language,
    )

    service = VocabularyService(session)

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

        logger.info(f'Аудио расшифровано: {transcription.text!r} ')

        processed_answer = _postprocess_transcribed_answer(transcription.text)
        logger.info('Audio transcription postprocessed: raw=%r processed=%r', transcription.text, processed_answer)

        answer_lookup_started_at = perf_counter()
        check_result = await service.check_text_answer(
            word_id=payload.word_id,
            answer_language=payload.answer_language,
            answer=processed_answer,
        )
        answer_lookup_duration_ms = (perf_counter() - answer_lookup_started_at) * 1000
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
            user_answer=processed_answer,
            check_result=check_result,
        )

        await _enqueue_word_repetition_record(
            user_id=current_user.id,
            word_id=payload.word_id,
            is_correct=check_result.is_correct,
        )

        total_duration_ms = (perf_counter() - total_started_at) * 1000
        logger.info(
            'Answer audio timing: user_id=%s word_id=%s trim_ms=%.2f '
            'transcription_ms=%.2f answer_lookup_ms=%.2f total_ms=%.2f transcription=%r',
            current_user.id,
            payload.word_id,
            transcription.trim_duration_ms,
            transcription.transcription_duration_ms,
            answer_lookup_duration_ms,
            total_duration_ms,
            processed_answer,
        )

        response = VocabularyWordAnswerResponse(
            data=VocabularyWordAnswerData(
                success=True,
                answer=processed_answer,
                correct_answer=check_result.correct_answer,
                is_correct=check_result.is_correct,
                has_typo=check_result.has_typo,
                typo=check_result.typo,
            ),
        )

        return response

    if payload.answer is None:
        logger.info('Text answer rejected: answer is missing word_id=%s', payload.word_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Text answer is required',
        )

    text_answer = payload.answer.strip()
    answer_lookup_started_at = perf_counter()
    check_result = await service.check_text_answer(
        word_id=payload.word_id,
        answer_language=payload.answer_language,
        answer=text_answer,
    )
    answer_lookup_duration_ms = (perf_counter() - answer_lookup_started_at) * 1000
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
    await _enqueue_word_repetition_record(
        user_id=current_user.id,
        word_id=payload.word_id,
        is_correct=check_result.is_correct,
    )

    total_duration_ms = (perf_counter() - total_started_at) * 1000
    logger.info(
        'Answer text timing: user_id=%s word_id=%s answer_lookup_ms=%.2f total_ms=%.2f answer=%r',
        current_user.id,
        payload.word_id,
        answer_lookup_duration_ms,
        total_duration_ms,
        text_answer,
    )

    return VocabularyWordAnswerResponse(
        data=VocabularyWordAnswerData(
            success=True,
            answer=text_answer,
            correct_answer=check_result.correct_answer,
            is_correct=check_result.is_correct,
            has_typo=check_result.has_typo,
            typo=check_result.typo,
        ),
    )


async def _parse_answer_request(
    request: Request,
) -> tuple[VocabularyWordAnswerRequest, UploadFile | None]:
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
        return VocabularyWordAnswerRequest.model_validate(raw_payload), audio_file
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _postprocess_transcribed_answer(value: str) -> str:
    without_punctuation = ''.join(
        char
        for char in value
        if not unicodedata.category(char).startswith('P')
    )
    return ' '.join(without_punctuation.lower().split())


async def _enqueue_word_repetition_record(
    *,
    user_id: int,
    word_id: int,
    is_correct: bool,
) -> None:
    try:
        await record_word_repetition.kiq(
            user_id=user_id,
            word_id=word_id,
            is_correct=is_correct,
        )
    except Exception:
        logger.exception(
            'Не удалось отправить запись повторения в воркер: user_id=%s word_id=%s',
            user_id,
            word_id,
        )
