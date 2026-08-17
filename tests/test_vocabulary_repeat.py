import unittest
from unittest.mock import AsyncMock

from api.schemas.vocabulary import VocabularyRepeatWordRequest
from api.services.vocabulary import VocabularyService


class VocabularyRepeatTest(unittest.IsolatedAsyncioTestCase):
    def test_word_id_is_optional(self):
        payload = VocabularyRepeatWordRequest()

        self.assertIsNone(payload.word_id)

    async def test_requested_word_is_limited_to_current_user_learned_words(self):
        session = AsyncMock()
        session.scalar.return_value = None
        service = VocabularyService(session)

        await service.get_learned_word_for_user(
            user_id=42,
            payload=VocabularyRepeatWordRequest(word_id=17),
        )

        statement = session.scalar.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )

        self.assertIn('learned_words.user_id = 42', compiled_statement)
        self.assertIn('words_en.id = 17', compiled_statement)


if __name__ == '__main__':
    unittest.main()
