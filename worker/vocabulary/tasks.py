import logging

from db.session import async_session_factory
from enums import TextModel, WorkerTaskName
from worker.broker import broker
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
