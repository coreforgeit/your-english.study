import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Response

from api.dependencies import get_current_telegram_user
from api.routers.auth_tg import auth_tg
from api.schemas.auth_tg import TelegramAuthRequest
from api.schemas.session import SessionData
from core.config import settings


class FakeSessionService:
    def __init__(self, session_data: SessionData | None = None):
        self.session_data = session_data
        self.created_for: int | None = None
        self.created_language_level: int | None = None
        self.read_session_id: str | None = None

    async def create(
        self,
        user_id: int,
        language_level: int | None,
    ) -> str:
        self.created_for = user_id
        self.created_language_level = language_level
        return 'test-session'

    async def get(self, session_id: str) -> SessionData | None:
        self.read_session_id = session_id
        return self.session_data

    @staticmethod
    def get_session_id(session_token: str) -> str:
        return f'analytics-{session_token}'


class TelegramAuthRouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_debug_mode_skips_telegram_validation(self):
        payload = TelegramAuthRequest(init_data='')
        response = Response()
        sessions = FakeSessionService()
        db_session = AsyncMock()
        db_session.scalar.return_value = 3

        with patch.object(settings, 'debug', True):
            result = await auth_tg(
                payload,
                response,
                None,
                sessions,
                db_session,
            )

        self.assertTrue(result)
        self.assertEqual(sessions.created_for, 524275902)
        self.assertEqual(sessions.created_language_level, 3)
        self.assertIn('tg_session=test-session', response.headers['set-cookie'])
        self.assertIn('HttpOnly', response.headers['set-cookie'])

    async def test_auth_reuses_active_session_for_same_user(self):
        payload = TelegramAuthRequest(init_data='')
        response = Response()
        sessions = FakeSessionService(
            SessionData(user_id=524275902, language_level=2),
        )
        db_session = AsyncMock()

        with patch.object(settings, 'debug', True):
            result = await auth_tg(
                payload,
                response,
                'active-session',
                sessions,
                db_session,
            )

        self.assertTrue(result)
        self.assertEqual(sessions.read_session_id, 'active-session')
        self.assertIsNone(sessions.created_for)
        db_session.scalar.assert_not_awaited()
        self.assertIn('tg_session=active-session', response.headers['set-cookie'])

    async def test_current_user_comes_from_session(self):
        sessions = FakeSessionService(
            SessionData(user_id=524275902, language_level=5),
        )

        user = await get_current_telegram_user('test-session', sessions)

        self.assertEqual(user.id, 524275902)
        self.assertEqual(user.session_id, 'analytics-test-session')
        self.assertEqual(user.language_level, 5)

    async def test_missing_session_returns_401(self):
        sessions = FakeSessionService()

        with self.assertRaises(HTTPException) as error:
            await get_current_telegram_user('missing-session', sessions)

        self.assertEqual(error.exception.status_code, 401)
