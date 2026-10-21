import unittest
from unittest.mock import AsyncMock, MagicMock

from services import VocabularyRepetitionService
from services.repetition_goal import RepetitionGoalCounter


class VocabularyRepetitionServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.counter = MagicMock(spec=RepetitionGoalCounter)
        self.counter.DAILY_LIMIT = 30
        self.counter.get_remaining = AsyncMock(return_value=None)
        self.counter.initialize = AsyncMock(side_effect=lambda user_id, count: count)

    async def test_returns_overdue_word_ids_in_requested_order(self) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result
        service = VocabularyRepetitionService(session, counter=self.counter)

        word_ids = await service.get_due_word_ids(user_id=42)

        self.assertEqual(word_ids, [7, 11])
        statement = session.scalars.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('learned_words.user_id = 42', compiled_statement)
        self.assertIn('JOIN words_en', compiled_statement)
        self.assertIn("words_en.status = 'allowed'", compiled_statement)
        self.assertIn('LIMIT 30', compiled_statement)
        self.counter.initialize.assert_awaited_once_with(42, 2)
        self.assertIn(
            "learned_words.status IN ('new', 'familiar')",
            compiled_statement,
        )
        self.assertIn(
            'learned_words.last_reviewed_at IS NULL',
            compiled_statement,
        )
        self.assertIn(
            "learned_words.last_reviewed_at < now() - INTERVAL '3 days'",
            compiled_statement,
        )
        self.assertIn(
            'ORDER BY learned_words.review_count ASC, '
            'learned_words.last_reviewed_at DESC NULLS FIRST, '
            'learned_words.id ASC',
            compiled_statement,
        )

    async def test_checks_only_one_due_word_for_worker(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 7
        service = VocabularyRepetitionService(session, counter=self.counter)

        has_due_words = await service.has_due_words(user_id=42)

        self.assertTrue(has_due_words)
        statement = session.scalar.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('learned_words.user_id = 42', compiled_statement)
        self.assertIn('LIMIT 1', compiled_statement)

    async def test_returns_false_when_there_are_no_due_words(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None
        service = VocabularyRepetitionService(session, counter=self.counter)

        has_due_words = await service.has_due_words(user_id=42)

        self.assertFalse(has_due_words)
        session.scalar.assert_awaited_once()

    async def test_existing_zero_returns_empty_without_querying_words(self) -> None:
        self.counter.get_remaining.return_value = 0
        session = AsyncMock()
        service = VocabularyRepetitionService(session, counter=self.counter)

        self.assertEqual(await service.get_due_word_ids(42), [])
        self.assertFalse(await service.has_due_words(42))

        session.scalars.assert_not_awaited()
        session.scalar.assert_not_awaited()
        self.counter.initialize.assert_not_awaited()

    async def test_uses_remaining_count_without_resetting_goal(self) -> None:
        self.counter.get_remaining.return_value = 2
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result

        word_ids = await VocabularyRepetitionService(
            session, counter=self.counter,
        ).get_due_word_ids(42)

        self.assertEqual(word_ids, [7, 11])
        statement = session.scalars.await_args.args[0]
        self.assertIn('LIMIT 2', str(statement.compile(
            compile_kwargs={'literal_binds': True},
        )))
        self.counter.initialize.assert_not_awaited()

    async def test_empty_first_list_initializes_zero(self) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.scalars.return_value = result

        self.assertEqual(await VocabularyRepetitionService(
            session, counter=self.counter,
        ).get_due_word_ids(42), [])
        self.counter.initialize.assert_awaited_once_with(42, 0)

    async def test_worker_can_finish_goal_while_words_are_being_selected(self) -> None:
        self.counter.get_remaining.side_effect = [2, 0]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result

        self.assertEqual(await VocabularyRepetitionService(
            session, counter=self.counter,
        ).get_due_word_ids(42), [])

    async def test_concurrent_initialization_does_not_replace_existing_remainder(self) -> None:
        self.counter.initialize.side_effect = None
        self.counter.initialize.return_value = 1
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result

        self.assertEqual(await VocabularyRepetitionService(
            session, counter=self.counter,
        ).get_due_word_ids(42), [7])
