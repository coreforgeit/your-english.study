import unittest
from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from core.config import settings as app_settings
from enums import AppLaunchMode, ReminderKey
from worker.reminders.tasks import (
    DailyWordLearningReminder,
    ReminderSettingsSnapshot,
    send_daily_word_learning_reminder,
)


class ReminderTimeTest(unittest.TestCase):
    def test_builds_repeat_app_url_and_preserves_existing_query(self) -> None:
        with patch.object(
            app_settings,
            'app_url',
            'https://app.example.test/?source=telegram&mode=learn',
        ):
            result = DailyWordLearningReminder._get_app_launch_url(
                AppLaunchMode.REPEAT,
            )

        self.assertEqual(
            result,
            'https://app.example.test/?source=telegram&mode=repeat',
        )

    def test_uses_today_when_reminder_time_is_still_ahead(self) -> None:
        result = DailyWordLearningReminder._get_next_run_at_utc(
            time(20, 0),
            ZoneInfo('Europe/Berlin'),
            now_utc=datetime(2026, 1, 15, 17, 0, tzinfo=UTC),
        )

        self.assertEqual(
            result,
            datetime(2026, 1, 15, 19, 0, tzinfo=UTC),
        )

    def test_uses_next_day_when_reminder_time_has_passed(self) -> None:
        result = DailyWordLearningReminder._get_next_run_at_utc(
            time(20, 0),
            ZoneInfo('Europe/Berlin'),
            now_utc=datetime(2026, 1, 15, 20, 0, tzinfo=UTC),
        )

        self.assertEqual(
            result,
            datetime(2026, 1, 16, 19, 0, tzinfo=UTC),
        )


class ReminderSchedulingTest(unittest.IsolatedAsyncioTestCase):
    @patch('worker.reminders.tasks.scheduler')
    @patch.object(
        DailyWordLearningReminder,
        '_get_settings',
        new_callable=AsyncMock,
    )
    async def test_creates_replaceable_daily_job(
        self,
        get_settings: AsyncMock,
        scheduler: MagicMock,
    ) -> None:
        get_settings.return_value = ReminderSettingsSnapshot(
            reminders_enabled=True,
            reminder_time=time(20, 0),
            timezone='Europe/Berlin',
        )

        await send_daily_word_learning_reminder.original_func(user_id=42)

        call = scheduler.add_job.call_args
        self.assertIs(
            call.args[0],
            DailyWordLearningReminder.run_scheduled,
        )
        self.assertEqual(call.kwargs['id'], 'daily_word_learning:42')
        self.assertEqual(call.kwargs['kwargs'], {'user_id': 42})
        self.assertTrue(call.kwargs['replace_existing'])
        self.assertTrue(call.kwargs['coalesce'])
        self.assertEqual(call.kwargs['max_instances'], 1)

    @patch('worker.reminders.tasks.scheduler')
    @patch.object(
        DailyWordLearningReminder,
        '_get_settings',
        new_callable=AsyncMock,
    )
    async def test_removes_existing_job_when_reminders_are_disabled(
        self,
        get_settings: AsyncMock,
        scheduler: MagicMock,
    ) -> None:
        get_settings.return_value = ReminderSettingsSnapshot(
            reminders_enabled=False,
            reminder_time=time(20, 0),
            timezone='UTC',
        )
        scheduler.get_job.return_value = object()

        await send_daily_word_learning_reminder.original_func(user_id=42)

        scheduler.remove_job.assert_called_once_with(
            ReminderKey.DAILY_WORD_LEARNING.for_user(42),
        )
        scheduler.add_job.assert_not_called()

    @patch('worker.reminders.tasks.scheduler')
    async def test_does_not_schedule_with_null_settings(
        self,
        scheduler: MagicMock,
    ) -> None:
        null_settings = (
            ReminderSettingsSnapshot(None, time(20, 0), 'UTC'),
            ReminderSettingsSnapshot(True, None, 'UTC'),
            ReminderSettingsSnapshot(True, time(20, 0), None),
        )

        for user_settings in null_settings:
            with self.subTest(user_settings=user_settings):
                scheduler.reset_mock()
                scheduler.get_job.return_value = object()

                is_scheduled = await DailyWordLearningReminder(42).schedule(
                    user_settings,
                )

                self.assertFalse(is_scheduled)
                scheduler.remove_job.assert_called_once_with(
                    ReminderKey.DAILY_WORD_LEARNING.for_user(42),
                )
                scheduler.add_job.assert_not_called()

    @patch(
        'worker.reminders.tasks.DailyWordLearningReminder.schedule',
        new_callable=AsyncMock,
    )
    @patch(
        'worker.reminders.tasks.DailyWordLearningReminder._get_all_settings',
        new_callable=AsyncMock,
    )
    @patch('worker.reminders.tasks.scheduler')
    async def test_rebuilds_all_user_reminders_and_removes_stale_jobs(
        self,
        scheduler: MagicMock,
        get_all_settings: AsyncMock,
        schedule_reminder: AsyncMock,
    ) -> None:
        user_settings = {
            42: ReminderSettingsSnapshot(True, time(20, 0), 'UTC'),
            43: ReminderSettingsSnapshot(False, time(21, 0), 'UTC'),
        }
        get_all_settings.return_value = user_settings
        schedule_reminder.side_effect = [True, False]
        stale_reminder = MagicMock(id='daily_word_learning:100')
        unrelated_job = MagicMock(id='another_job:100')
        scheduler.get_jobs.return_value = [stale_reminder, unrelated_job]

        await DailyWordLearningReminder.rebuild_all()

        scheduler.remove_job.assert_called_once_with(stale_reminder.id)
        self.assertEqual(schedule_reminder.await_count, 2)
        schedule_reminder.assert_any_await(user_settings[42])
        schedule_reminder.assert_any_await(user_settings[43])


class ReminderExecutionTest(unittest.IsolatedAsyncioTestCase):
    @patch('worker.reminders.tasks.scheduler')
    @patch('worker.reminders.tasks.Bot')
    @patch.object(
        DailyWordLearningReminder,
        '_has_due_words',
        new_callable=AsyncMock,
    )
    @patch.object(
        DailyWordLearningReminder,
        '_get_settings',
        new_callable=AsyncMock,
    )
    async def test_rechecks_disabled_settings_before_sending(
        self,
        get_settings: AsyncMock,
        has_due_words: AsyncMock,
        bot_class: MagicMock,
        scheduler: MagicMock,
    ) -> None:
        get_settings.return_value = ReminderSettingsSnapshot(
            reminders_enabled=False,
            reminder_time=time(20, 0),
            timezone='UTC',
        )
        scheduler.get_job.return_value = object()

        await DailyWordLearningReminder(42).send()

        scheduler.remove_job.assert_called_once_with(
            ReminderKey.DAILY_WORD_LEARNING.for_user(42),
        )
        has_due_words.assert_not_awaited()
        bot_class.assert_not_called()

    @patch('worker.reminders.tasks.Bot')
    @patch.object(
        DailyWordLearningReminder,
        '_has_due_words',
        new_callable=AsyncMock,
    )
    @patch.object(
        DailyWordLearningReminder,
        '_get_settings',
        new_callable=AsyncMock,
    )
    async def test_rechecks_settings_and_sends_production_message(
        self,
        get_settings: AsyncMock,
        has_due_words: AsyncMock,
        bot_class: MagicMock,
    ) -> None:
        get_settings.return_value = ReminderSettingsSnapshot(
            reminders_enabled=True,
            reminder_time=time(20, 0),
            timezone='UTC',
        )
        has_due_words.return_value = True
        bot = bot_class.return_value
        bot.__aenter__ = AsyncMock(return_value=bot)
        bot.__aexit__ = AsyncMock(return_value=False)
        bot.send_message = AsyncMock()

        await DailyWordLearningReminder(42).send()

        bot_class.assert_called_once_with(token=app_settings.bot_token)
        send_message_call = bot.send_message.await_args
        self.assertEqual(send_message_call.kwargs['chat_id'], 42)
        self.assertEqual(
            send_message_call.kwargs['text'],
            'Пора повторить изученные слова.',
        )
        button = send_message_call.kwargs['reply_markup'].inline_keyboard[0][0]
        self.assertEqual(button.text, 'Начать повторение')
        self.assertEqual(
            button.web_app.url,
            f'{app_settings.app_url}?mode=repeat',
        )

    @patch('worker.reminders.tasks.Bot')
    @patch.object(
        DailyWordLearningReminder,
        '_has_due_words',
        new_callable=AsyncMock,
    )
    @patch.object(
        DailyWordLearningReminder,
        '_get_settings',
        new_callable=AsyncMock,
    )
    async def test_skips_message_when_no_words_are_due(
        self,
        get_settings: AsyncMock,
        has_due_words: AsyncMock,
        bot_class: MagicMock,
    ) -> None:
        get_settings.return_value = ReminderSettingsSnapshot(
            reminders_enabled=True,
            reminder_time=time(20, 0),
            timezone='UTC',
        )
        has_due_words.return_value = False

        await DailyWordLearningReminder(42).send()

        has_due_words.assert_awaited_once_with()
        bot_class.assert_not_called()
