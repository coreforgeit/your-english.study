import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTelegramUser, get_current_telegram_user, get_session
from api.parsers import parse_vocabulary_answer_request
from api.schemas.common import ApiResponse
from api.schemas.vocabulary import (
    VocabularyRepeatWordRequest,
    VocabularyWordAnswerData,
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
from task_queue.tasks import review_word


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/telegram-app', tags=['vocabulary'])


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


@router.post('/words/repeat', response_model=ApiResponse[WordRead])
async def repeat_word(
    payload: VocabularyRepeatWordRequest,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[WordRead]:
    logger.info(
        'Repeat word request: user_id=%s word_id=%s',
        current_user.id,
        payload.word_id,
    )
    service = VocabularyService(session)
    word = await service.get_learned_word_for_user(
        user_id=current_user.id,
        payload=payload,
    )
    if word is None:
        logger.info(
            'Repeat word response failed: no learned word found user_id=%s word_id=%s',
            current_user.id,
            payload.word_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Word not found',
        )

    return ApiResponse[WordRead](data=word)


@router.post(
    '/words/answer',
    response_model=ApiResponse[VocabularyWordAnswerData],
)
async def answer_word(
    request: Request,
    current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[VocabularyWordAnswerData]:
    parsed_request = await parse_vocabulary_answer_request(request)
    try:
        result = await VocabularyAnswerService(session).process(
            payload=parsed_request.payload,
            audio_file=parsed_request.audio_file,
            user_id=current_user.id,
            session_id=current_user.session_id,
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

    return ApiResponse[VocabularyWordAnswerData](
        data=VocabularyWordAnswerData(
            success=True,
            answer=result.answer,
            correct_answer=result.check_result.correct_answer,
            is_correct=result.check_result.is_correct,
            skip=result.skip,
            has_typo=result.check_result.has_typo,
            typo=result.check_result.typo,
            comment=result.check_result.comment,
        ),
    )


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