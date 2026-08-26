import hashlib
import json
import unittest
from unittest.mock import AsyncMock, Mock

from api.services.session import SESSION_TTL_SECONDS, SessionService
from db.models import UserSession


class SessionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_stores_hashed_session_key(self):
        redis = AsyncMock()
        db_session = Mock()
        sessions = SessionService(redis)

        session_id = await sessions.create(42, 3, db_session)

        expected_hash = hashlib.sha256(session_id.encode()).hexdigest()
        redis.set.assert_awaited_once_with(
            f'telegram-session:{expected_hash}',
            json.dumps(
                {'user_id': 42, 'language_level': 3},
                separators=(',', ':'),
            ),
            ex=SESSION_TTL_SECONDS,
        )
        self.assertNotIn(session_id, redis.set.await_args.args[0])

        saved_session = db_session.add.call_args.args[0]
        self.assertIsInstance(saved_session, UserSession)
        self.assertEqual(saved_session.session_id, expected_hash)
        self.assertEqual(saved_session.user_id, 42)

    async def test_get_user_renews_session_ttl(self):
        redis = AsyncMock()
        redis.getex.return_value = json.dumps(
            {'user_id': 42, 'language_level': 2},
        )
        sessions = SessionService(redis)

        session_data = await sessions.get('test-session')

        expected_hash = hashlib.sha256(b'test-session').hexdigest()
        redis.getex.assert_awaited_once_with(
            f'telegram-session:{expected_hash}',
            ex=SESSION_TTL_SECONDS,
        )
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data.user_id, 42)
        self.assertEqual(session_data.language_level, 2)

    def test_session_id_is_safe_token_hash(self):
        session_id = SessionService.get_session_id('test-session')

        self.assertEqual(session_id, hashlib.sha256(b'test-session').hexdigest())
        self.assertNotEqual(session_id, 'test-session')

    async def test_missing_session_returns_none(self):
        redis = AsyncMock()
        redis.getex.return_value = None
        sessions = SessionService(redis)

        self.assertIsNone(await sessions.get('missing-session'))

    async def test_invalid_session_is_deleted(self):
        redis = AsyncMock()
        redis.getex.return_value = '42'
        sessions = SessionService(redis)

        self.assertIsNone(await sessions.get('invalid-session'))

        expected_hash = hashlib.sha256(b'invalid-session').hexdigest()
        redis.delete.assert_awaited_once_with(
            f'telegram-session:{expected_hash}',
        )
