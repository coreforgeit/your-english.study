import unittest
from unittest.mock import AsyncMock, patch

from api.dependencies import CurrentTelegramUser
from api.parsers import ParsedVocabularyAnswerRequest
from api.routers.vocabulary import answer_word
from api.schemas.vocabulary import VocabularyWordAnswerRequest
from api.services.vocabulary_answer import (
    AnswerCheckResult,
    AudioAnswerFile,
    VocabularyAnswerService,
)
from enums import AnswerType


def make_parsed_request(payload: dict) -> ParsedVocabularyAnswerRequest:
    return ParsedVocabularyAnswerRequest(
        payload=VocabularyWordAnswerRequest.model_validate(payload),
        audio_file=None,
    )


class VocabularyAnswerTest(unittest.IsolatedAsyncioTestCase):
    def test_skip_defaults_to_false(self):
        payload = VocabularyWordAnswerRequest.model_validate(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'text_answer': 'ответ',
            },
        )

        self.assertFalse(payload.skip)

    async def test_skip_returns_correct_answer_without_checking(self):
        parsed_request = make_parsed_request(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'skip': True,
            },
        )
        current_user = CurrentTelegramUser(id=42, session_id='session')
        answer_service = VocabularyAnswerService(AsyncMock())
        answer_service.get_correct_answer = AsyncMock(
            return_value='правильный ответ',
        )
        answer_service.check_text_answer = AsyncMock()
        enqueue_repetition = AsyncMock()

        with (
            patch(
                'api.routers.vocabulary.VocabularyAnswerService',
                return_value=answer_service,
            ),
            patch(
                'api.routers.vocabulary.record_word_repetition.kiq',
                enqueue_repetition,
            ),
        ):
            response = await answer_word(
                parsed_request,
                current_user,
                AsyncMock(),
            )

        self.assertEqual(
            response.model_dump(),
            {
                'data': {
                    'success': True,
                    'answer': '',
                    'correct_answer': 'правильный ответ',
                    'is_correct': False,
                    'skip': True,
                    'has_typo': False,
                    'typo': None,
                    'comment': None,
                },
            },
        )
        answer_service.get_correct_answer.assert_awaited_once()
        answer_service.check_text_answer.assert_not_awaited()
        enqueue_repetition.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            is_correct=False,
            session_id='session',
        )

    async def test_text_answer_uses_common_check_pipeline(self):
        parsed_request = make_parsed_request(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'text_answer': '  ответ  ',
            },
        )
        current_user = CurrentTelegramUser(id=42, session_id='session')
        local_check_result = AnswerCheckResult(
            is_correct=True,
            has_typo=True,
            typo={
                'index': 5,
                'type': 'extra',
                'expected': None,
                'actual': 'т',
            },
            correct_answer='ответ',
        )
        answer_service = VocabularyAnswerService(AsyncMock())
        answer_service.check_text_answer = AsyncMock(
            return_value=local_check_result,
        )
        answer_service.check_text_answer_ai = AsyncMock()
        enqueue_repetition = AsyncMock()

        with (
            patch(
                'api.routers.vocabulary.VocabularyAnswerService',
                return_value=answer_service,
            ),
            patch(
                'api.routers.vocabulary.record_word_repetition.kiq',
                enqueue_repetition,
            ),
        ):
            response = await answer_word(
                parsed_request,
                current_user,
                AsyncMock(),
            )

        self.assertEqual(response.data.answer, 'ответ')
        self.assertTrue(response.data.is_correct)
        self.assertFalse(response.data.skip)
        self.assertTrue(response.data.has_typo)
        self.assertEqual(response.data.typo.actual, 'т')
        self.assertIsNone(response.data.comment)
        answer_service.check_text_answer.assert_awaited_once_with(
            word_id=7,
            answer_language='ru',
            answer='ответ',
        )
        answer_service.check_text_answer_ai.assert_not_awaited()
        enqueue_repetition.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            is_correct=True,
            session_id='session',
        )

    async def test_incorrect_local_answer_is_checked_by_ai(self):
        parsed_request = make_parsed_request(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'text_answer': 'близко',
            },
        )
        current_user = CurrentTelegramUser(id=42, session_id='session')
        local_check_result = AnswerCheckResult(
            is_correct=False,
            correct_answer='закрыто',
        )
        ai_check_result = AnswerCheckResult(
            is_correct=True,
            correct_answer='закрыто',
            comment='У слова close несколько значений; «близко» — корректный перевод.',
        )
        answer_service = VocabularyAnswerService(AsyncMock())
        answer_service.check_text_answer = AsyncMock(
            return_value=local_check_result,
        )
        answer_service.check_text_answer_ai = AsyncMock(
            return_value=ai_check_result,
        )
        enqueue_repetition = AsyncMock()

        with (
            patch(
                'api.routers.vocabulary.VocabularyAnswerService',
                return_value=answer_service,
            ),
            patch(
                'api.routers.vocabulary.record_word_repetition.kiq',
                enqueue_repetition,
            ),
        ):
            response = await answer_word(
                parsed_request,
                current_user,
                AsyncMock(),
            )

        self.assertTrue(response.data.is_correct)
        self.assertFalse(response.data.has_typo)
        self.assertIsNone(response.data.typo)
        self.assertEqual(response.data.comment, ai_check_result.comment)
        answer_service.check_text_answer.assert_awaited_once_with(
            word_id=7,
            answer_language='ru',
            answer='близко',
        )
        answer_service.check_text_answer_ai.assert_awaited_once_with(
            word_id=7,
            answer_language='ru',
            answer='близко',
        )
        enqueue_repetition.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            is_correct=True,
            session_id='session',
        )

    async def test_audio_answer_replaces_text_answer(self):
        payload = VocabularyWordAnswerRequest(
            word_id=7,
            answer_type=AnswerType.TEXT,
            answer_language='ru',
            text_answer='текст',
        )
        audio_file = AudioAnswerFile(
            content=b'audio',
            filename='answer.webm',
            content_type='audio/webm',
        )
        answer_service = VocabularyAnswerService(AsyncMock())

        with patch.object(
            answer_service,
            '_transcribe_audio_answer',
            AsyncMock(return_value='аудио'),
        ) as transcribe:
            answer, answer_type = await answer_service._resolve_answer(
                payload,
                audio_file,
            )

        self.assertEqual(answer, 'аудио')
        self.assertEqual(answer_type, AnswerType.AUDIO)
        transcribe.assert_awaited_once_with(payload, audio_file)

if __name__ == '__main__':
    unittest.main()
