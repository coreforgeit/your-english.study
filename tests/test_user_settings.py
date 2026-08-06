import unittest
from unittest.mock import AsyncMock, Mock

from pydantic import ValidationError

from api.dependencies import CurrentTelegramUser
from api.routers.user_settings import get_user_settings, update_user_settings
from api.schemas.user_settings import UserSettingsUpdate
from db.models import User, UserSettings


class UserSettingsTest(unittest.IsolatedAsyncioTestCase):
    async def test_user_creation_ensures_settings_exist(self):
        session = AsyncMock()
        user_result = Mock()
        user_result.scalar_one.return_value = 42
        session.execute.side_effect = [user_result, Mock()]

        user_id = await User.add_or_update(
            session=session,
            user_id=42,
            full_name='Test User',
            username='test',
        )

        self.assertEqual(user_id, 42)
        self.assertEqual(session.execute.await_count, 2)
        settings_insert = session.execute.await_args_list[1].args[0]
        self.assertEqual(settings_insert.compile().params['user_id'], 42)

    async def test_get_returns_user_settings(self):
        session = AsyncMock()
        session.scalar.return_value = UserSettings(user_id=42, timezone='UTC')
        current_user = CurrentTelegramUser(id=42, session_id='session')

        response = await get_user_settings(current_user, session)

        self.assertEqual(response.model_dump(), {'data': {'timezone': 'UTC'}})

    async def test_patch_accepts_empty_partial_update(self):
        session = AsyncMock()
        session.scalar.return_value = UserSettings(user_id=42, timezone='UTC')
        current_user = CurrentTelegramUser(id=42, session_id='session')

        response = await update_user_settings(
            UserSettingsUpdate(),
            current_user,
            session,
        )

        self.assertEqual(response.model_dump(), {'data': {'timezone': 'UTC'}})

    async def test_patch_updates_timezone(self):
        session = AsyncMock()
        settings = UserSettings(user_id=42, timezone='UTC')
        session.scalar.return_value = settings
        current_user = CurrentTelegramUser(id=42, session_id='session')

        response = await update_user_settings(
            UserSettingsUpdate(timezone='Europe/Berlin'),
            current_user,
            session,
        )

        self.assertEqual(settings.timezone, 'Europe/Berlin')
        self.assertEqual(
            response.model_dump(),
            {'data': {'timezone': 'Europe/Berlin'}},
        )

    def test_patch_rejects_unknown_settings(self):
        with self.assertRaises(ValidationError):
            UserSettingsUpdate.model_validate({'unknown': True})

    def test_patch_rejects_null_timezone(self):
        with self.assertRaises(ValidationError):
            UserSettingsUpdate.model_validate({'timezone': None})

    def test_user_relation_is_one_to_one(self):
        self.assertFalse(User.settings.property.uselist)
        self.assertTrue(UserSettings.__table__.c.user_id.unique)
