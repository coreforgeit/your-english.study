import unittest
from unittest.mock import AsyncMock, MagicMock

from services import VocabularyRepetitionService


class VocabularyRepetitionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_overdue_word_ids_in_requested_order(self) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [7, 11]
        session.scalars.return_value = result
        service = VocabularyRepetitionService(session)

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
        service = VocabularyRepetitionService(session)

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
        service = VocabularyRepetitionService(session)

        has_due_words = await service.has_due_words(user_id=42)

        self.assertFalse(has_due_words)
        session.scalar.assert_awaited_once()
