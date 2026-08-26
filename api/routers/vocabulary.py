import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.parsers import (
    ParsedVocabularyAnswerRequest,
    parse_vocabulary_answer_request,
)
from api.schemas.common import ApiResponse
from api.schemas.vocabulary import (
    VocabularyRepeatWordData,
    VocabularyRepeatWordRequest,
    VocabularyWordAnswerData,
    VocabularyWordStatusData,
    VocabularyWordsRequest,
    WordRead,
    WordReviewRequest,
    WordReviewResponse,
)
from api.services.vocabulary import VocabularyService
from api.services.vocabulary_answer import (
    VocabularyAnswerAICheckError,
    VocabularyAnswerRequiredError,
    VocabularyAnswerService,
    VocabularyAnswerTranscriptionError,
    VocabularyAnswerWordNotFoundError,
)
from db.models import WordEn
from enums import WordStatus
from services import VocabularyRepetitionService
from task_queue.tasks import record_word_repetition, review_word


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/telegram-app', tags=['vocabulary'])


@router.patch(
    '/words/{word_id}/manual-review',
    response_model=ApiResponse[VocabularyWordStatusData],
)
async def mark_word_for_manual_review(
    word_id: int,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[VocabularyWordStatusData]:
    word = await VocabularyService(session).mark_word_for_manual_review(
        word_id,
    )
    if word is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    logger.info(
        f'Слово отправлено на ручную проверку: '
        f'user_id={current_user.id} word_id={word.id}',
    )
    return ApiResponse[VocabularyWordStatusData](
        data=VocabularyWordStatusData(
            id=word.id,
            status=word.status,
        ),
    )


@router.get(
    '/words/interval-repetitions',
    response_model=ApiResponse[list[int]],
)
async def get_interval_repetitions(
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[list[int]]:
    service = VocabularyRepetitionService(session)
    word_ids = await service.get_due_word_ids(current_user.id)
    return ApiResponse[list[int]](data=word_ids)


@router.post('/words/learn', response_model=ApiResponse[WordRead])
async def learn_word(
    payload: VocabularyWordsRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[WordRead]:
    logger.info('Learn word request: user_id=%s', current_user.id)
    # logger.info(f'payload: {payload}')
    service = VocabularyService(session)
    word = await service.get_new_word_for_user(
        user_id=current_user.id,
        session_id=current_user.session_id,
        language_level_grade=current_user.language_level,
    )
    if word is None:
        logger.info('Learn word response failed: no new word found user_id=%s', current_user.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    if not word.is_reviewed:
        await review_word.kiq(
            word_id=word.id,
            model=WordReviewRequest().model,
            session_id=current_user.session_id,
        )


    return ApiResponse[WordRead](data=word)


@router.post(
    '/words/repeat',
    response_model=ApiResponse[VocabularyRepeatWordData],
)
async def repeat_word(
    payload: VocabularyRepeatWordRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[VocabularyRepeatWordData]:
    logger.info(
        'Repeat word request: user_id=%s word_id=%s',
        current_user.id,
        payload.word_id,
    )
    service = VocabularyService(session)
    repeat_word_data = await service.get_learned_word_for_user(
        user_id=current_user.id,
        payload=payload,
    )
    if repeat_word_data is None:
        logger.info(
            'Repeat word response failed: no learned word found user_id=%s word_id=%s',
            current_user.id,
            payload.word_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    word_data = WordRead.model_validate(repeat_word_data.word)
    return ApiResponse[VocabularyRepeatWordData](
        data=VocabularyRepeatWordData(
            **word_data.model_dump(),
            answer_language=repeat_word_data.answer_language,
        ),
    )


@router.post(
    '/words/answer',
    response_model=ApiResponse[VocabularyWordAnswerData],
)
async def answer_word(
    parsed_request: ParsedVocabularyAnswerRequest = Depends(
        parse_vocabulary_answer_request,
    ),
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[VocabularyWordAnswerData]:
    try:
        result = await VocabularyAnswerService(session).process(
            payload=parsed_request.payload,
            audio_file=parsed_request.audio_file,
            user_id=current_user.id,
        )
    except VocabularyAnswerRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Text answer or audio file is required',
        ) from exc
    except VocabularyAnswerWordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        ) from exc
    except VocabularyAnswerTranscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Audio transcription failed',
        ) from exc
    except VocabularyAnswerAICheckError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='AI answer check failed',
        ) from exc

    try:
        await record_word_repetition.kiq(
            user_id=current_user.id,
            word_id=parsed_request.payload.word_id,
            session_id=current_user.session_id,
            is_correct=result.check_result.is_correct,
        )
    except Exception:
        logger.exception(
            f'Не удалось отправить повторение слова в воркер: '
            f'user_id={current_user.id} '
            f'word_id={parsed_request.payload.word_id}',
        )

    data = VocabularyWordAnswerData(
        success=True,
        answer=result.answer,
        correct_answer=result.check_result.correct_answer,
        is_correct=result.check_result.is_correct,
        skip=result.skip,
        has_typo=result.check_result.has_typo,
        typo=result.check_result.typo,
        comment=result.check_result.comment,
    )
    # logger.info(f'>> {data}')
    return ApiResponse[VocabularyWordAnswerData](data=data)


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
        session_id=current_user.session_id,
    )

    return WordReviewResponse(success=True)
