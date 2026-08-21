import unittest
from unittest.mock import AsyncMock, MagicMock

from services import VocabularyRepetitionService


class VocabularyRepetitionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_all_due_word_ids_in_stable_order(self) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result
        service = VocabularyRepetitionService(
            session,
            repetition_intervals=[0, 1],
        )

        word_ids = await service.get_due_word_ids(user_id=42)

        self.assertEqual(word_ids, [7, 11])
        statement = session.scalars.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('learned_words.user_id = 42', compiled_statement)
        self.assertIn(
            "learned_words.status IN ('new', 'familiar')",
            compiled_statement,
        )
        self.assertIn(
            'ORDER BY learned_words.created_at, learned_words.id',
            compiled_statement,
        )

    async def test_checks_only_one_due_word_for_worker(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 7
        service = VocabularyRepetitionService(
            session,
            repetition_intervals=[0, 1],
        )

        has_due_words = await service.has_due_words(user_id=42)

        self.assertTrue(has_due_words)
        statement = session.scalar.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('learned_words.user_id = 42', compiled_statement)
        self.assertIn('LIMIT 1', compiled_statement)

    async def test_returns_empty_results_when_intervals_are_not_configured(
        self,
    ) -> None:
        session = AsyncMock()
        service = VocabularyRepetitionService(
            session,
            repetition_intervals=[],
        )

        word_ids = await service.get_due_word_ids(user_id=42)
        has_due_words = await service.has_due_words(user_id=42)

        self.assertEqual(word_ids, [])
        self.assertFalse(has_due_words)
        session.scalars.assert_not_awaited()
        session.scalar.assert_not_awaited()
