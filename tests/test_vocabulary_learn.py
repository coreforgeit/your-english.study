import unittest
from unittest.mock import AsyncMock, Mock

from api.schemas.vocabulary import VocabularyWordsRequest
from api.services.vocabulary import VocabularyService


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

if __name__ == '__main__':
    unittest.main()
