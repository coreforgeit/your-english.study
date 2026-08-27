import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from enums import LearnedWordStatus, NotificationType
from worker.notifications.actions import (
    NewWordsMilestoneNotificationAction,
    NotificationPublisher,
    WordStatusChangedNotificationAction,
)


class NewWordsMilestoneNotificationActionTest(
    unittest.IsolatedAsyncioTestCase,
):
    @staticmethod
    def make_session(*scalar_results: object) -> MagicMock:
        session = MagicMock(spec=AsyncSession)
        session.scalar = AsyncMock(side_effect=scalar_results)
        return session

    @staticmethod
    def make_publisher() -> MagicMock:
        publisher = MagicMock(spec=NotificationPublisher)
        publisher.publish = AsyncMock()
        return publisher

    async def test_sends_five_words_notification_for_local_day(self) -> None:
        session = self.make_session('Asia/Tbilisi', 5)
        publisher = self.make_publisher()
        action = NewWordsMilestoneNotificationAction(session, publisher)

        notification_type = await action.execute(
            42,
            now_utc=datetime(2026, 8, 26, 22, tzinfo=UTC),
        )

        self.assertEqual(
            notification_type,
            NotificationType.FIVE_NEW_WORDS_TODAY,
        )
        publisher.publish.assert_awaited_once_with(
            42,
            NotificationType.FIVE_NEW_WORDS_TODAY,
        )
        count_statement = session.scalar.await_args_list[1].args[0]
        compiled_statement = str(
            count_statement.compile(
                compile_kwargs={'literal_binds': True},
            ),
        )
        self.assertIn(
            "learned_words.created_at >= '2026-08-26 20:00:00+00:00'",
            compiled_statement,
        )
        self.assertIn(
            "learned_words.created_at < '2026-08-27 20:00:00+00:00'",
            compiled_statement,
        )

    async def test_sends_ten_words_notification(self) -> None:
        session = self.make_session('UTC', 10)
        publisher = self.make_publisher()

        notification_type = await NewWordsMilestoneNotificationAction(
            session,
            publisher,
        ).execute(42)

        self.assertEqual(
            notification_type,
            NotificationType.TEN_NEW_WORDS_TODAY,
        )
        publisher.publish.assert_awaited_once_with(
            42,
            NotificationType.TEN_NEW_WORDS_TODAY,
        )

    async def test_skips_other_word_counts(self) -> None:
        session = self.make_session('UTC', 6)
        publisher = self.make_publisher()

        notification_type = await NewWordsMilestoneNotificationAction(
            session,
            publisher,
        ).execute(42)

        self.assertIsNone(notification_type)
        publisher.publish.assert_not_awaited()


class WordStatusChangedNotificationActionTest(
    unittest.IsolatedAsyncioTestCase,
):
    @staticmethod
    def make_action() -> tuple[
        WordStatusChangedNotificationAction,
        MagicMock,
    ]:
        session = MagicMock(spec=AsyncSession)
        session.scalar = AsyncMock(return_value='example')
        publisher = MagicMock(spec=NotificationPublisher)
        publisher.publish = AsyncMock()
        return WordStatusChangedNotificationAction(session, publisher), publisher

    async def test_learned_status_uses_special_notification(self) -> None:
        action, publisher = self.make_action()

        notification_type = await action.execute(
            user_id=42,
            word_id=7,
            status=LearnedWordStatus.LEARNED,
        )

        self.assertEqual(notification_type, NotificationType.WORD_LEARNED)
        publisher.publish.assert_awaited_once_with(
            42,
            NotificationType.WORD_LEARNED,
            word='example',
        )

    async def test_familiar_status_keeps_generic_text(self) -> None:
        action, publisher = self.make_action()

        notification_type = await action.execute(
            user_id=42,
            word_id=7,
            status=LearnedWordStatus.FAMILIAR,
        )

        self.assertEqual(
            notification_type,
            NotificationType.WORD_STATUS_CHANGED,
        )
        publisher.publish.assert_awaited_once_with(
            42,
            NotificationType.WORD_STATUS_CHANGED,
            word='example',
            status='знакомое',
        )
