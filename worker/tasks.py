import logging

from worker.broker import broker


logger = logging.getLogger(__name__)


@broker.task
async def test(
    *,
    user_id: int,
    word_id: int,
) -> None:
    logger.info(
        'Task accepted: task=test user_id=%s word_id=%s',
        user_id,
        word_id,
    )
