import logging

import sqlalchemy as sa
from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.config import settings
from db.models import WordEn
from db.session import async_session_factory
from enums import WorkerTaskName
from services.notifications import UserNotification, user_notifications_channel
from worker.analytics.vocabulary.service import (
    VocabularyRepetitionAnalyticsService,
)
from worker.broker import broker


logger = logging.getLogger(__name__)
notification_redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


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
            word = None
            if changed_status is not None:
                word = await session.scalar(
                    sa.select(WordEn.word).where(WordEn.id == word_id),
                )
            await session.commit()
            logger.info(f'Повторение слова обработано: user_id={user_id} word_id={word_id} is_correct={is_correct}')

        except Exception:
            await session.rollback()
            logger.exception(f'Не удалось обработать повторение слова: user_id={user_id} word_id={word_id}')
            raise

    if changed_status is None:
        return

    if not word:
        logger.warning(
            f'Уведомление о смене статуса не отправлено: слово не найдено, '
            f'user_id={user_id} word_id={word_id}',
        )
        return

    try:
        await notification_redis_client.publish(
            user_notifications_channel(user_id),
            UserNotification(
                word=word,
                status=changed_status,
            ).model_dump_json(),
        )
    except RedisError:
        logger.exception(
            f'Не удалось отправить уведомление о смене статуса: '
            f'user_id={user_id} word_id={word_id}',
        )
