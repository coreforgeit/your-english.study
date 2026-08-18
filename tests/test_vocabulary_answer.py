import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from starlette.requests import Request

from api.dependencies import CurrentTelegramUser
from api.routers.vocabulary import answer_word
from api.schemas.vocabulary import VocabularyWordAnswerRequest
from api.services.vocabulary import AnswerCheckResult
from api.services.vocabulary_answer import AudioAnswerFile, VocabularyAnswerService
from enums import AnswerType


def make_json_request(payload: dict) -> Request:
    body = json.dumps(payload).encode()

    async def receive():
        return {
            'type': 'http.request',
            'body': body,
            'more_body': False,
        }

    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'headers': [(b'content-type', b'application/json')],
        },
        receive,
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
        request = make_json_request(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'skip': True,
            },
        )
        current_user = CurrentTelegramUser(id=42, session_id='session')
        service = Mock()
        service.get_correct_answer = AsyncMock(return_value='правильный ответ')
        service.check_text_answer = AsyncMock()
        answer_service = VocabularyAnswerService(
            AsyncMock(),
            vocabulary_service=service,
        )
        enqueue_repetition = AsyncMock()

        with (
            patch(
                'api.routers.vocabulary.VocabularyAnswerService',
                return_value=answer_service,
            ),
            patch.object(
                answer_service,
                '_enqueue_repetition_record',
                enqueue_repetition,
            ),
        ):
            response = await answer_word(request, current_user, AsyncMock())

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
                },
            },
        )
        service.get_correct_answer.assert_awaited_once()
        service.check_text_answer.assert_not_awaited()
        enqueue_repetition.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            is_correct=False,
            session_id='session',
        )

    async def test_text_answer_uses_common_check_pipeline(self):
        request = make_json_request(
            {
                'word_id': 7,
                'answer_type': 'text',
                'answer_language': 'ru',
                'text_answer': '  ответ  ',
            },
        )
        current_user = CurrentTelegramUser(id=42, session_id='session')
        check_result = AnswerCheckResult(
            is_correct=True,
            correct_answer='ответ',
        )
        service = Mock()
        service.check_text_answer = AsyncMock(return_value=check_result)
        service.save_answer_error = AsyncMock()
        answer_service = VocabularyAnswerService(
            AsyncMock(),
            vocabulary_service=service,
        )
        enqueue_repetition = AsyncMock()

        with (
            patch(
                'api.routers.vocabulary.VocabularyAnswerService',
                return_value=answer_service,
            ),
            patch.object(
                answer_service,
                '_enqueue_repetition_record',
                enqueue_repetition,
            ),
        ):
            response = await answer_word(request, current_user, AsyncMock())

        self.assertEqual(response.data.answer, 'ответ')
        self.assertTrue(response.data.is_correct)
        self.assertFalse(response.data.skip)
        service.check_text_answer.assert_awaited_once_with(
            word_id=7,
            answer_language='ru',
            answer='ответ',
        )
        service.save_answer_error.assert_awaited_once()
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
