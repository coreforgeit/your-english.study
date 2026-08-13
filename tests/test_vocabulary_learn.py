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

    async def test_uses_one_grade_above_session_level_when_level_is_missing(self):
        session = self._session()
        service = VocabularyService(session)

        await service._select_word(
            payload=VocabularyWordsRequest(),
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
            payload=VocabularyWordsRequest(),
            language_level_grade=6,
        )

        statement = session.execute.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn('language_levels.grade <= 6', compiled_statement)

    async def test_explicit_level_has_priority_over_session_grade(self):
        session = self._session()
        service = VocabularyService(session)

        await service._select_word(
            payload=VocabularyWordsRequest(level='B1'),
            language_level_grade=2,
        )

        statement = session.execute.await_args.args[0]
        compiled_statement = str(
            statement.compile(compile_kwargs={'literal_binds': True}),
        )
        self.assertIn("language_levels.name = 'B1'", compiled_statement)
        self.assertNotIn('language_levels.grade <=', compiled_statement)


if __name__ == '__main__':
    unittest.main()
