import logging

from db.session import async_session_factory
from enums import LearnedWordStatus, WorkerTaskName
from worker.broker import broker
from worker.notifications.actions import (
    NewWordsMilestoneNotificationAction,
    WordStatusChangedNotificationAction,
)


logger = logging.getLogger(__name__)


@broker.task(
    task_name=WorkerTaskName.CHECK_NEW_WORDS_MILESTONE_NOTIFICATION.value,
)
async def check_new_words_milestone_notification(*, user_id: int) -> None:
    async with async_session_factory() as session:
        try:
            await NewWordsMilestoneNotificationAction(session).execute(user_id)
        except Exception:
            logger.exception(
                f'Не удалось проверить уведомление о новых словах: '
                f'user_id={user_id}',
            )
            raise


@broker.task(
    task_name=WorkerTaskName.SEND_WORD_STATUS_CHANGED_NOTIFICATION.value,
)
async def send_word_status_changed_notification(
    *,
    user_id: int,
    word_id: int,
    status: str,
) -> None:
    learned_word_status = LearnedWordStatus(status)
    async with async_session_factory() as session:
        try:
            await WordStatusChangedNotificationAction(session).execute(
                user_id=user_id,
                word_id=word_id,
                status=learned_word_status,
            )
        except Exception:
            logger.exception(
                f'Не удалось отправить уведомление о смене статуса: '
                f'user_id={user_id} word_id={word_id} '
                f'status={learned_word_status.value}',
            )
            raise
