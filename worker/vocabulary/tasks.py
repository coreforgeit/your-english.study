import logging

from db.session import async_session_factory
from worker.broker import broker
from worker.vocabulary.service import VocabularyReviewService


logger = logging.getLogger(__name__)


@broker.task
async def review_word(*, word_id: int) -> None:
    logger.info('Задача проверки слова принята: word_id=%s', word_id)

    async with async_session_factory() as session:
        try:
            await VocabularyReviewService(session).review(word_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception('Проверка слова завершилась ошибкой: word_id=%s', word_id)
            raise
