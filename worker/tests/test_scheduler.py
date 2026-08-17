import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from worker.scheduler import start_scheduler


class SchedulerLifecycleTest(unittest.IsolatedAsyncioTestCase):
    @patch('worker.scheduler._scheduler_initializers')
    @patch('worker.scheduler.scheduler')
    async def test_initializes_jobs_before_resuming_scheduler(
        self,
        scheduler: MagicMock,
        initializers: MagicMock,
    ) -> None:
        events: list[str] = []
        initializer = AsyncMock(
            side_effect=lambda: events.append('initialized'),
        )
        initializers.__iter__.return_value = iter([initializer])
        scheduler.start.side_effect = lambda **_: events.append('started')
        scheduler.resume.side_effect = lambda: events.append('resumed')
        scheduler.running = False

        await start_scheduler(MagicMock())

        self.assertEqual(events, ['started', 'initialized', 'resumed'])
        scheduler.start.assert_called_once_with(paused=True)
        initializer.assert_awaited_once_with()

