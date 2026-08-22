import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from api.schemas.vocabulary import (
    VocabularyRepeatWordData,
    VocabularyRepeatWordRequest,
    WordRead,
)
from api.services.vocabulary import VocabularyService
from enums import AnswerLanguage, LearnedWordStatus


class VocabularyRepeatTest(unittest.IsolatedAsyncioTestCase):
    def test_repeat_response_accepts_dumped_translations_field(self):
        word = WordRead(
            id=148,
            word='apartment',
            pronunciation='/əˈpɑːt.mənt/',
            translations=['квартира'],
            part_of_speech='noun',
            level='A1',
            audio_url=None,
        )

        response_data = VocabularyRepeatWordData(
            **word.model_dump(),
            answer_language='ru',
        )

        self.assertEqual(response_data.translations, ['квартира'])
        self.assertEqual(response_data.answer_language, AnswerLanguage.RU)

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
        self.assertNotIn('learned_words.status IN', compiled_statement)

    async def test_automatic_selection_excludes_learned_words(self):
        session = AsyncMock()
        session.scalar.return_value = None
        service = VocabularyService(session)

        await service.get_learned_word_for_user(
            user_id=42,
            payload=VocabularyRepeatWordRequest(),
        )

        statement = session.scalar.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )

        self.assertIn(
            "learned_words.status IN ('new', 'familiar')",
            compiled_statement,
        )

    async def test_new_word_requires_russian_answer(self):
        session = AsyncMock()
        word = object()
        session.scalar.return_value = SimpleNamespace(
            word=word,
            status=LearnedWordStatus.NEW,
        )
        service = VocabularyService(session)

        result = await service.get_learned_word_for_user(
            user_id=42,
            payload=VocabularyRepeatWordRequest(),
        )

        self.assertIs(result.word, word)
        self.assertEqual(result.answer_language, AnswerLanguage.RU)

    async def test_familiar_word_requires_english_answer(self):
        session = AsyncMock()
        word = object()
        session.scalar.return_value = SimpleNamespace(
            word=word,
            status=LearnedWordStatus.FAMILIAR,
        )
        service = VocabularyService(session)

        result = await service.get_learned_word_for_user(
            user_id=42,
            payload=VocabularyRepeatWordRequest(),
        )

        self.assertIs(result.word, word)
        self.assertEqual(result.answer_language, AnswerLanguage.EN)


if __name__ == '__main__':
    unittest.main()
