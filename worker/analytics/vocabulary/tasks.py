import logging

from db.session import async_session_factory
from enums import WorkerTaskName
from task_queue.tasks import send_word_status_changed_notification
from worker.analytics.vocabulary.service import (
    VocabularyRepetitionAnalyticsService,
)
from worker.broker import broker


logger = logging.getLogger(__name__)


@broker.task(task_name=WorkerTaskName.RECORD_WORD_REPETITION)
async def record_word_repetition(
    *,
    user_id: int,
    word_id: int,
    session_id: str,
    is_correct: bool,
) -> None:
    async with async_session_factory() as session:
        try:
            changed_status = await VocabularyRepetitionAnalyticsService(
                session,
            ).record_answer(
                user_id=user_id,
                word_id=word_id,
                session_id=session_id,
                is_correct=is_correct,
            )
            await session.commit()
            logger.info(f'Повторение слова обработано: user_id={user_id} word_id={word_id} is_correct={is_correct}')

        except Exception:
            await session.rollback()
            logger.exception(f'Не удалось обработать повторение слова: user_id={user_id} word_id={word_id}')
            raise

    if changed_status is None:
        return

    try:
        await send_word_status_changed_notification.kiq(
            user_id=user_id,
            word_id=word_id,
            status=changed_status.value,
        )
    except Exception:
        logger.exception(
            f'Не удалось поставить уведомление о смене статуса в очередь: '
            f'user_id={user_id} word_id={word_id}',
        )
