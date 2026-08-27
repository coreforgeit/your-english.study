import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from api.dependencies import CurrentTelegramUser
from api.routers.vocabulary import learn_word
from api.schemas.vocabulary import VocabularyWordsRequest
from api.services.vocabulary import VocabularyService
from core.config import settings


class VocabularyLearnTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _session() -> AsyncMock:
        session = AsyncMock()
        result = Mock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        return session

    def test_request_does_not_define_level(self):
        self.assertNotIn('level', VocabularyWordsRequest.model_fields)

    async def test_uses_one_grade_above_session_level(self):
        session = self._session()
        service = VocabularyService(session)

        await service._select_word(
            language_level_grade=2,
        )

        statement = session.execute.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('language_levels.grade <= 3', compiled_statement)

    async def test_uses_configured_grade_offset(self):
        session = self._session()
        service = VocabularyService(session)

        with patch.object(
            settings,
            'vocabulary_learning_grade_offset',
            2,
        ):
            await service._select_word(language_level_grade=2)

        statement = session.execute.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('language_levels.grade <= 4', compiled_statement)

    async def test_grade_upper_bound_does_not_exceed_six(self):
        session = self._session()
        service = VocabularyService(session)

        await service._select_word(
            language_level_grade=6,
        )

        statement = session.execute.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('language_levels.grade <= 6', compiled_statement)

    async def test_api_does_not_save_selected_word(self):
        session = AsyncMock()
        service = VocabularyService(session)
        selected_word = SimpleNamespace(id=7)
        service._select_word = AsyncMock(return_value=selected_word)

        result = await service.get_new_word_for_user(
            user_id=42,
            language_level_grade=2,
        )

        self.assertIs(result, selected_word)
        session.execute.assert_not_awaited()

    async def test_sends_selected_word_to_worker(self):
        word = SimpleNamespace(
            id=7,
            word='assignment',
            pronunciation=None,
            translation_words=['задание'],
            part_of_speech='noun',
            level='B1',
            audio_url=None,
        )
        service = Mock()
        service.get_new_word_for_user = AsyncMock(return_value=word)
        enqueue_learned_word = AsyncMock()
        current_user = CurrentTelegramUser(
            id=42,
            session_id='session',
            language_level=2,
        )

        with (
            patch(
                'api.routers.vocabulary.VocabularyService',
                return_value=service,
            ),
            patch(
                'api.routers.vocabulary.record_learned_word.kiq',
                enqueue_learned_word,
            ),
        ):
            response = await learn_word(
                VocabularyWordsRequest(),
                current_user,
                AsyncMock(),
            )

        self.assertEqual(response.data.id, 7)
        service.get_new_word_for_user.assert_awaited_once_with(
            user_id=42,
            language_level_grade=2,
        )
        enqueue_learned_word.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            session_id='session',
        )

if __name__ == '__main__':
    unittest.main()
