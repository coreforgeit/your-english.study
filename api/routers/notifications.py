import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from redis.asyncio import Redis

from api.dependencies import CurrentTelegramUser, get_current_telegram_user
from api.services.session import redis_client
from services.notifications import UserNotification, user_notifications_channel


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix='/telegram-app/notifications',
    tags=['notifications'],
)

NOTIFICATION_HEARTBEAT_SECONDS = 15.0


async def notification_events(
    user_id: int,
    redis: Redis = redis_client,
) -> AsyncGenerator[str, None]:
    channel = user_notifications_channel(user_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        yield ': connected\n\n'

        while True:
            message: dict[str, Any] | None = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=NOTIFICATION_HEARTBEAT_SECONDS,
            )
            if message is None:
                yield ': keep-alive\n\n'
                continue

            try:
                notification = UserNotification.model_validate_json(
                    message.get('data'),
                )
            except (TypeError, ValidationError):
                logger.warning(
                    f'Получено некорректное уведомление: user_id={user_id}',
                )
                continue

            yield (
                f'event: notification\n'
                f'data: {notification.model_dump_json()}\n\n'
            )
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.get('/stream', response_class=StreamingResponse)
async def stream_notifications(
    _current_user: CurrentTelegramUser = Depends(get_current_telegram_user),
) -> StreamingResponse:
    return StreamingResponse(
        notification_events(_current_user.id),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )
