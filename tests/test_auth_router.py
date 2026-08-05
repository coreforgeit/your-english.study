import unittest
from unittest.mock import patch

from fastapi import Response

from api.dependencies import get_current_telegram_user
from api.routers.auth_tg import auth_tg
from api.schemas.auth_tg import TelegramAuthRequest
from core.config import settings


class FakeSessionService:
    def __init__(self, user_id: int | None = None):
        self.user_id = user_id
        self.created_for: int | None = None
        self.read_session_id: str | None = None

    async def create(self, user_id: int) -> str:
        self.created_for = user_id
        return 'test-session'

    async def get_user_id(self, session_id: str) -> int | None:
        self.read_session_id = session_id
        return self.user_id

    @staticmethod
    def get_session_id(session_token: str) -> str:
        return f'analytics-{session_token}'


class TelegramAuthRouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_debug_mode_skips_telegram_validation(self):
        payload = TelegramAuthRequest(init_data='')
        response = Response()
        sessions = FakeSessionService()

        with patch.object(settings, 'debug', True):
            result = await auth_tg(payload, response, None, sessions)

        self.assertTrue(result)
        self.assertEqual(sessions.created_for, 524275902)
        self.assertIn('tg_session=test-session', response.headers['set-cookie'])
        self.assertIn('HttpOnly', response.headers['set-cookie'])

    async def test_auth_reuses_active_session_for_same_user(self):
        payload = TelegramAuthRequest(init_data='')
        response = Response()
        sessions = FakeSessionService(user_id=524275902)

        with patch.object(settings, 'debug', True):
            result = await auth_tg(payload, response, 'active-session', sessions)

        self.assertTrue(result)
        self.assertEqual(sessions.read_session_id, 'active-session')
        self.assertIsNone(sessions.created_for)
        self.assertIn('tg_session=active-session', response.headers['set-cookie'])

    async def test_current_user_comes_from_session(self):
        sessions = FakeSessionService(user_id=524275902)

        user = await get_current_telegram_user('test-session', sessions)

        self.assertEqual(user.id, 524275902)
        self.assertEqual(user.session_id, 'analytics-test-session')
