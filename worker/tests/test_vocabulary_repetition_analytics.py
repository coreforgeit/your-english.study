import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LearnedWord, WordRepetitionAnswer
from enums import LearnedWordStatus
from worker.analytics.vocabulary.service import (
    VocabularyRepetitionAnalyticsService,
)
from worker.analytics.vocabulary.tasks import record_word_repetition


class VocabularyRepetitionAnalyticsServiceTest(
    unittest.IsolatedAsyncioTestCase,
):
    @staticmethod
    def make_session() -> MagicMock:
        session = MagicMock(spec=AsyncSession)
        session.flush = AsyncMock()
        session.scalar = AsyncMock()
        session.scalars = AsyncMock()
        return session

    @staticmethod
    def make_learned_word(
        status: LearnedWordStatus,
    ) -> LearnedWord:
        return LearnedWord(
            user_id=42,
            word_id=7,
            session_id='learning-session',
            review_count=4,
            status=status,
        )

    async def test_saves_current_answer_before_loading_recent_answers(
        self,
    ) -> None:
        session = self.make_session()
        learned_word = self.make_learned_word(LearnedWordStatus.NEW)
        session.scalar.return_value = learned_word
        recent_answers_result = MagicMock()
        recent_answers_result.all.return_value = [True, True, True]
        session.scalars.return_value = recent_answers_result
        service = VocabularyRepetitionAnalyticsService(session)

        def get_next_status(
            current_status: LearnedWordStatus,
            recent_answers: list[bool],
        ) -> LearnedWordStatus:
            self.assertEqual(learned_word.review_count, 4)
            return VocabularyRepetitionAnalyticsService._get_next_status(
                current_status,
                recent_answers,
            )

        service._get_next_status = MagicMock(side_effect=get_next_status)

        changed_status = await service.record_answer(
            user_id=42,
            word_id=7,
            session_id='answer-session',
            is_correct=True,
        )

        self.assertEqual(changed_status, LearnedWordStatus.FAMILIAR)
        session.flush.assert_awaited_once_with()
        added_answer = session.add.call_args.args[0]
        self.assertIsInstance(added_answer, WordRepetitionAnswer)
        self.assertTrue(added_answer.is_correct)
        self.assertEqual(added_answer.word_status, LearnedWordStatus.NEW)
        service._get_next_status.assert_called_once_with(
            LearnedWordStatus.NEW,
            [True, True, True],
        )
        self.assertEqual(learned_word.review_count, 5)
        self.assertIsInstance(learned_word.last_reviewed_at, datetime)

        recent_answers_statement = session.scalars.await_args.args[0]
        compiled_statement = str(
            recent_answers_statement.compile(
                compile_kwargs={'literal_binds': True},
            ),
        )
        self.assertIn(
            'ORDER BY word_repetition_answers.created_at DESC, '
            'word_repetition_answers.id DESC',
            compiled_statement,
        )
        self.assertIn(
            "word_repetition_answers.word_status = 'new'",
            compiled_statement,
        )
        self.assertIn('LIMIT 3', compiled_statement)

    async def test_uses_only_answers_from_familiar_status(self) -> None:
        session = self.make_session()
        learned_word = self.make_learned_word(LearnedWordStatus.FAMILIAR)
        session.scalar.return_value = learned_word
        recent_answers_result = MagicMock()
        recent_answers_result.all.return_value = [True, True, True]
        session.scalars.return_value = recent_answers_result
        service = VocabularyRepetitionAnalyticsService(session)

        changed_status = await service.record_answer(
            user_id=42,
            word_id=7,
            session_id='answer-session',
            is_correct=True,
        )

        self.assertEqual(changed_status, LearnedWordStatus.LEARNED)
        added_answer = session.add.call_args.args[0]
        self.assertEqual(
            added_answer.word_status,
            LearnedWordStatus.FAMILIAR,
        )

        recent_answers_statement = session.scalars.await_args.args[0]
        compiled_statement = str(
            recent_answers_statement.compile(
                compile_kwargs={'literal_binds': True},
            ),
        )
        self.assertIn(
            "word_repetition_answers.word_status = 'familiar'",
            compiled_statement,
        )

    async def test_learned_word_only_records_answer_and_review_metadata(
        self,
    ) -> None:
        session = self.make_session()
        learned_word = self.make_learned_word(LearnedWordStatus.LEARNED)
        session.scalar.return_value = learned_word
        service = VocabularyRepetitionAnalyticsService(session)

        changed_status = await service.record_answer(
            user_id=42,
            word_id=7,
            session_id='answer-session',
            is_correct=False,
        )

        self.assertIsNone(changed_status)
        self.assertEqual(learned_word.review_count, 5)
        added_answer = session.add.call_args.args[0]
        self.assertEqual(
            added_answer.word_status,
            LearnedWordStatus.LEARNED,
        )
        session.scalars.assert_not_awaited()

    async def test_returns_none_when_status_is_unchanged(self) -> None:
        session = self.make_session()
        learned_word = self.make_learned_word(LearnedWordStatus.NEW)
        session.scalar.return_value = learned_word
        recent_answers_result = MagicMock()
        recent_answers_result.all.return_value = [True, False]
        session.scalars.return_value = recent_answers_result
        service = VocabularyRepetitionAnalyticsService(session)

        changed_status = await service.record_answer(
            user_id=42,
            word_id=7,
            session_id='answer-session',
            is_correct=True,
        )

        self.assertIsNone(changed_status)
        self.assertEqual(learned_word.status, LearnedWordStatus.NEW)
        self.assertEqual(learned_word.review_count, 5)

    async def test_keeps_answer_when_learned_word_is_missing(self) -> None:
        session = self.make_session()
        session.scalar.return_value = None
        service = VocabularyRepetitionAnalyticsService(session)

        changed_status = await service.record_answer(
            user_id=42,
            word_id=7,
            session_id='answer-session',
            is_correct=True,
        )

        self.assertIsNone(changed_status)
        session.add.assert_called_once()
        session.flush.assert_awaited_once_with()
        added_answer = session.add.call_args.args[0]
        self.assertEqual(added_answer.word_status, LearnedWordStatus.NEW)
        session.scalars.assert_not_awaited()


class VocabularyRepetitionStatusTest(unittest.TestCase):
    def test_status_transitions(self) -> None:
        cases = (
            (
                LearnedWordStatus.NEW,
                [True, True, True],
                LearnedWordStatus.FAMILIAR,
            ),
            (
                LearnedWordStatus.NEW,
                [True, True],
                LearnedWordStatus.NEW,
            ),
            (
                LearnedWordStatus.FAMILIAR,
                [False, False, True],
                LearnedWordStatus.NEW,
            ),
            (
                LearnedWordStatus.FAMILIAR,
                [True, True, True],
                LearnedWordStatus.LEARNED,
            ),
            (
                LearnedWordStatus.FAMILIAR,
                [True, False, True],
                LearnedWordStatus.FAMILIAR,
            ),
            (
                LearnedWordStatus.LEARNED,
                [False, False, False],
                LearnedWordStatus.LEARNED,
            ),
        )

        for current_status, recent_answers, expected_status in cases:
            with self.subTest(
                current_status=current_status,
                recent_answers=recent_answers,
            ):
                status = VocabularyRepetitionAnalyticsService._get_next_status(
                    current_status,
                    recent_answers,
                )
                self.assertEqual(status, expected_status)


class VocabularyRepetitionTaskTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        'worker.analytics.vocabulary.tasks.'
        'send_word_status_changed_notification.kiq',
        new_callable=AsyncMock,
    )
    @patch(
        'worker.analytics.vocabulary.tasks.VocabularyRepetitionAnalyticsService',
    )
    @patch('worker.analytics.vocabulary.tasks.async_session_factory')
    async def test_publishes_when_status_changes(
        self,
        session_factory: MagicMock,
        service_class: MagicMock,
        enqueue_notification: AsyncMock,
    ) -> None:
        session = MagicMock(spec=AsyncSession)
        session.scalar = AsyncMock(return_value='example')
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session_context
        service = service_class.return_value
        service.record_answer = AsyncMock(
            return_value=LearnedWordStatus.FAMILIAR,
        )

        await record_word_repetition.original_func(
            user_id=42,
            word_id=7,
            session_id='session',
            is_correct=True,
        )

        service.record_answer.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            session_id='session',
            is_correct=True,
        )
        session.commit.assert_awaited_once_with()
        session.rollback.assert_not_awaited()
        enqueue_notification.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            status='familiar',
        )

    @patch(
        'worker.analytics.vocabulary.tasks.'
        'send_word_status_changed_notification.kiq',
        new_callable=AsyncMock,
    )
    @patch(
        'worker.analytics.vocabulary.tasks.VocabularyRepetitionAnalyticsService',
    )
    @patch('worker.analytics.vocabulary.tasks.async_session_factory')
    async def test_does_not_publish_when_status_is_unchanged(
        self,
        session_factory: MagicMock,
        service_class: MagicMock,
        enqueue_notification: AsyncMock,
    ) -> None:
        session = MagicMock(spec=AsyncSession)
        session.scalar = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session_context
        service_class.return_value.record_answer = AsyncMock(return_value=None)

        await record_word_repetition.original_func(
            user_id=42,
            word_id=7,
            session_id='session',
            is_correct=False,
        )

        session.commit.assert_awaited_once_with()
        session.scalar.assert_not_awaited()
        enqueue_notification.assert_not_awaited()
