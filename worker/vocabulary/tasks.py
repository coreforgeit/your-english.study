import logging

from ai.enums import TextModel
from db.session import async_session_factory
from worker.broker import broker
from worker.vocabulary.service import VocabularyReviewService


logger = logging.getLogger(__name__)


@broker.task
async def review_word(*, word_id: int, model: str) -> None:
    text_model = TextModel(model)
    logger.info(
        'Задача проверки слова принята: word_id=%s model=%s',
        word_id,
        text_model.value,
    )

    async with async_session_factory() as session:
        try:
            service = VocabularyReviewService(session, text_model)
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
