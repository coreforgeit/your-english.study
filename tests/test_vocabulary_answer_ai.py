import unittest
from unittest.mock import AsyncMock, patch

from ai.schemas import VocabularyAnswerCheckResult
from api.services.vocabulary_answer import VocabularyAnswerService
from db.models import WordEn, WordRu
from enums import AnswerLanguage, VocabularyAnswerVerdict


class VocabularyAnswerAICheckTest(unittest.IsolatedAsyncioTestCase):
    async def test_checks_english_to_russian_translation(self):
        session = AsyncMock()
        session.get.return_value = WordEn(
            word='assignment',
            part_of_speech='noun',
            translations=[WordRu(word='задание')],
        )
        ai_result = VocabularyAnswerCheckResult(
            verdict=VocabularyAnswerVerdict.CORRECT_WITH_MINOR_ISSUE,
            correct_answers=['задание', 'задача'],
            comment='Небольшая опечатка в окончании.',
        )

        with patch(
            'api.services.vocabulary_answer.check_vocabulary_answer',
            AsyncMock(return_value=ai_result),
        ) as ai_check:
            result = await VocabularyAnswerService(session).check_text_answer_ai(
                word_id=7,
                answer_language=AnswerLanguage.RU,
                answer='заданиее',
            )

        self.assertIsNotNone(result)
        self.assertTrue(result.is_correct)
        self.assertFalse(result.has_typo)
        self.assertIsNone(result.typo)
        self.assertEqual(result.correct_answer, ['задание', 'задача'])
        self.assertEqual(result.comment, 'Небольшая опечатка в окончании.')
        ai_check.assert_awaited_once_with(
            source_text='assignment',
            answer='заданиее',
            source_language='en',
            target_language='ru',
            part_of_speech='noun',
        )

    async def test_checks_russian_to_english_translation(self):
        session = AsyncMock()
        session.get.return_value = WordEn(
            word='assignment',
            part_of_speech='noun',
            translations=[WordRu(word='задание')],
        )
        ai_result = VocabularyAnswerCheckResult(
            verdict=VocabularyAnswerVerdict.INCORRECT,
            correct_answers=['assignment', 'task'],
            comment=None,
        )

        with patch(
            'api.services.vocabulary_answer.check_vocabulary_answer',
            AsyncMock(return_value=ai_result),
        ) as ai_check:
            result = await VocabularyAnswerService(session).check_text_answer_ai(
                word_id=7,
                answer_language=AnswerLanguage.EN,
                answer='holiday',
            )

        self.assertIsNotNone(result)
        self.assertFalse(result.is_correct)
        self.assertFalse(result.has_typo)
        self.assertEqual(result.correct_answer, ['assignment', 'task'])
        self.assertIsNone(result.comment)
        ai_check.assert_awaited_once_with(
            source_text='задание',
            answer='holiday',
            source_language='ru',
            target_language='en',
            part_of_speech='noun',
        )


if __name__ == '__main__':
    unittest.main()
