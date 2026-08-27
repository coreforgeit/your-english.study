import logging

from db.session import async_session_factory
from enums import TextModel, WorkerTaskName
from worker.broker import broker
from worker.vocabulary.learning_service import VocabularyLearningService
from worker.vocabulary.service import VocabularyReviewService


logger = logging.getLogger(__name__)


@broker.task(task_name=WorkerTaskName.REVIEW_WORD.value)
async def review_word(
    *,
    word_id: int,
    model: str,
    session_id: str | None = None,
) -> None:
    text_model = TextModel(model)
    logger.info(
        'Задача проверки слова принята: word_id=%s model=%s',
        word_id,
        text_model.value,
    )

    async with async_session_factory() as session:
        try:
            service = VocabularyReviewService(
                session,
                text_model,
                session_id=session_id,
            )
            await service.review(word_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                'Проверка слова завершилась ошибкой: word_id=%s model=%s',
                word_id,
                text_model.value,
            )
            raise


@broker.task(task_name=WorkerTaskName.RECORD_LEARNED_WORD.value)
async def record_learned_word(
    *,
    user_id: int,
    word_id: int,
    session_id: str,
) -> None:
    logger.info(
        f'Задача сохранения изученного слова принята: '
        f'user_id={user_id} word_id={word_id}',
    )

    async with async_session_factory() as session:
        try:
            needs_review = await VocabularyLearningService(
                session,
            ).record_learned_word(
                user_id=user_id,
                word_id=word_id,
                session_id=session_id,
            )
            if needs_review:
                await review_word.kiq(
                    word_id=word_id,
                    model=TextModel.GPT_4O_MINI.value,
                    session_id=session_id,
                )

            await session.commit()
            logger.info(
                f'Изученное слово сохранено: '
                f'user_id={user_id} word_id={word_id} '
                f'отправлено_на_проверку={needs_review}',
            )
        except Exception:
            await session.rollback()
            logger.exception(
                f'Не удалось сохранить изученное слово: '
                f'user_id={user_id} word_id={word_id}',
            )
            raise
