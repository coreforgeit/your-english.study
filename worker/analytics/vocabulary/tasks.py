import logging

from taskiq import Context, TaskiqDepends

from db.session import async_session_factory
from enums import WorkerTaskName
from services.repetition_goal import RepetitionGoalCounter
from task_queue.tasks import send_word_status_changed_notification
from worker.analytics.vocabulary.service import (
    VocabularyRepetitionAnalyticsService,
)
from worker.broker import broker


logger = logging.getLogger(__name__)


@broker.task(task_name=WorkerTaskName.RECORD_WORD_REPETITION.value)
async def record_word_repetition(
    *,
    user_id: int,
    word_id: int,
    session_id: str,
    is_correct: bool,
    context: Context = TaskiqDepends(),
) -> None:
    task_id = context.message.task_id
    logger.info(
        f'Задача повторения принята: user_id={user_id} word_id={word_id} '
        f'task_id={task_id}',
    )
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
            logger.info(
                f'Прогресс повторения сохранён в БД: user_id={user_id} '
                f'word_id={word_id} is_correct={is_correct} task_id={task_id}',
            )

        except Exception:
            await session.rollback()
            logger.exception(
                f'Не удалось сохранить повторение: user_id={user_id} '
                f'word_id={word_id} task_id={task_id}',
            )
            raise

        try:
            remaining = await RepetitionGoalCounter(session).decrement(
                user_id,
                task_id=task_id,
            )
        except Exception:
            logger.exception(
                f'Не удалось обновить счётчик повторений: user_id={user_id} '
                f'word_id={word_id} task_id={task_id}',
            )
            raise
        logger.info(
            f'Повторение обработано: user_id={user_id} word_id={word_id} '
            f'task_id={task_id} remaining={remaining}',
        )

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
