import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from starlette.requests import Request

from api.dependencies import CurrentTelegramUser
from api.routers.vocabulary import answer_word
from api.schemas.vocabulary import VocabularyWordAnswerRequest


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
                'answer': 'ответ',
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
        enqueue_repetition = AsyncMock()

        with (
            patch('api.routers.vocabulary.VocabularyService', return_value=service),
            patch(
                'api.routers.vocabulary._enqueue_word_repetition_record',
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


if __name__ == '__main__':
    unittest.main()
