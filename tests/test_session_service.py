import hashlib
import unittest
from unittest.mock import AsyncMock

from api.services.session import SESSION_TTL_SECONDS, SessionService


class SessionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_stores_hashed_session_key(self):
        redis = AsyncMock()
        sessions = SessionService(redis)

        session_id = await sessions.create(42)

        expected_hash = hashlib.sha256(session_id.encode()).hexdigest()
        redis.set.assert_awaited_once_with(
            f'telegram-session:{expected_hash}',
            '42',
            ex=SESSION_TTL_SECONDS,
        )
        self.assertNotIn(session_id, redis.set.await_args.args[0])

    async def test_get_user_renews_session_ttl(self):
        redis = AsyncMock()
        redis.getex.return_value = '42'
        sessions = SessionService(redis)

        user_id = await sessions.get_user_id('test-session')

        expected_hash = hashlib.sha256(b'test-session').hexdigest()
        redis.getex.assert_awaited_once_with(
            f'telegram-session:{expected_hash}',
            ex=SESSION_TTL_SECONDS,
        )
        self.assertEqual(user_id, 42)

    def test_session_id_is_safe_token_hash(self):
        session_id = SessionService.get_session_id('test-session')

        self.assertEqual(session_id, hashlib.sha256(b'test-session').hexdigest())
        self.assertNotEqual(session_id, 'test-session')

    async def test_missing_session_returns_none(self):
        redis = AsyncMock()
        redis.getex.return_value = None
        sessions = SessionService(redis)

        self.assertIsNone(await sessions.get_user_id('missing-session'))
