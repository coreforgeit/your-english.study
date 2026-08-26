import unittest
from unittest.mock import AsyncMock

from api.dependencies import CurrentTelegramUser
from api.routers.notifications import notification_events, stream_notifications
from enums import LearnedWordStatus
from services.notifications import UserNotification, user_notifications_channel


class FakePubSub:
    def __init__(self, messages: list[dict[str, str] | None]) -> None:
        self.messages = messages
        self.subscribe = AsyncMock()
        self.unsubscribe = AsyncMock()
        self.aclose = AsyncMock()

    async def get_message(self, **_: object) -> dict[str, str] | None:
        return self.messages.pop(0)


class FakeRedis:
    def __init__(self, pubsub: FakePubSub) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> FakePubSub:
        return self._pubsub


class NotificationsRouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_notification_from_user_channel(self):
        notification = UserNotification(
            word='example',
            status=LearnedWordStatus.FAMILIAR,
        )
        pubsub = FakePubSub(
            [{'data': notification.model_dump_json()}],
        )
        events = notification_events(42, FakeRedis(pubsub))

        self.assertEqual(await anext(events), ': connected\n\n')
        self.assertEqual(
            await anext(events),
            f'event: notification\ndata: {notification.model_dump_json()}\n\n',
        )

        await events.aclose()
        channel = user_notifications_channel(42)
        pubsub.subscribe.assert_awaited_once_with(channel)
        pubsub.unsubscribe.assert_awaited_once_with(channel)
        pubsub.aclose.assert_awaited_once_with()

    async def test_stream_has_sse_headers(self):
        response = await stream_notifications(
            CurrentTelegramUser(id=42, session_id='session'),
        )

        self.assertEqual(response.media_type, 'text/event-stream')
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertEqual(response.headers['x-accel-buffering'], 'no')
