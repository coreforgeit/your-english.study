import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from api.services.vocabulary import VocabularyService
from db.models import WordEn
from enums import WordStatus


class VocabularyManualReviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_changes_word_status_to_manual_review(self) -> None:
        session = AsyncMock()
        word = SimpleNamespace(id=17, status=WordStatus.ALLOWED)
        session.get.return_value = word
        service = VocabularyService(session)

        result = await service.mark_word_for_manual_review(word_id=17)

        self.assertIs(result, word)
        self.assertEqual(word.status, WordStatus.MANUAL_REVIEW)
        session.get.assert_awaited_once_with(WordEn, 17)
        session.flush.assert_awaited_once_with()

    async def test_does_not_flush_when_word_is_not_found(self) -> None:
        session = AsyncMock()
        session.get.return_value = None
        service = VocabularyService(session)

        result = await service.mark_word_for_manual_review(word_id=17)

        self.assertIsNone(result)
        session.flush.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
