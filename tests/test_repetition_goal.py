import asyncio
import os
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from redis.asyncio import Redis

from services.notifications import UserNotification, user_notifications_channel
from services.repetition_goal import RepetitionGoalCounter


class RepetitionGoalCounterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.session = AsyncMock()
        self.redis = AsyncMock()
        self.counter = RepetitionGoalCounter(self.session, redis=self.redis)

    async def test_missing_counter_and_zero_are_distinct(self) -> None:
        self.redis.hget.side_effect = [None, '0', '12']
        self.assertIsNone(await self.counter.get_remaining(42))
        self.assertEqual(await self.counter.get_remaining(42), 0)
        self.assertEqual(await self.counter.get_remaining(42), 12)

    async def test_initialization_expires_at_local_midnight(self) -> None:
        cases = (
            ('Asia/Tbilisi', datetime(2026, 10, 21, 18, 0, tzinfo=UTC),
             datetime(2026, 10, 21, 20, 0, tzinfo=UTC)),
            # В Берлине эти дни длятся 23 и 25 часов из-за перевода часов.
            ('Europe/Berlin', datetime(2026, 3, 28, 23, 0, tzinfo=UTC),
             datetime(2026, 3, 29, 22, 0, tzinfo=UTC)),
            ('Europe/Berlin', datetime(2026, 10, 24, 22, 0, tzinfo=UTC),
             datetime(2026, 10, 25, 23, 0, tzinfo=UTC)),
            (None, datetime(2026, 10, 21, 18, 0, tzinfo=UTC),
             datetime(2026, 10, 22, 0, 0, tzinfo=UTC)),
            ('Unknown/Timezone', datetime(2026, 10, 21, 18, 0, tzinfo=UTC),
             datetime(2026, 10, 22, 0, 0, tzinfo=UTC)),
        )
        for timezone_value, now, expected_expiration in cases:
            with self.subTest(timezone=timezone_value, now=now):
                self.session.scalar.return_value = timezone_value
                self.redis.eval.return_value = 7
                with patch('services.repetition_goal.datetime', wraps=datetime) as clock:
                    clock.now.return_value = now
                    self.assertEqual(await self.counter.initialize(42, 7), 7)

                self.assertEqual(
                    self.redis.eval.await_args.args[-1],
                    int(expected_expiration.timestamp()),
                )

    async def test_initialization_uses_existing_remainder(self) -> None:
        self.session.scalar.return_value = 'UTC'
        self.redis.eval.return_value = 3
        self.assertEqual(await self.counter.initialize(42, 30), 3)

    async def test_initialization_rejects_counts_outside_daily_limit(self) -> None:
        for count in (-1, 31):
            with self.subTest(count=count), self.assertRaises(ValueError):
                await self.counter.initialize(42, count)
        self.redis.eval.assert_not_awaited()

    async def test_decrement_carries_delivery_id_and_completion_event(self) -> None:
        self.redis.eval.return_value = 0
        self.assertEqual(await self.counter.decrement(42, task_id='delivery'), 0)

        arguments = self.redis.eval.await_args.args
        self.assertEqual(arguments[3], 'task:delivery')
        self.assertEqual(arguments[4], user_notifications_channel(42))
        notification = UserNotification.model_validate_json(arguments[5])
        self.assertEqual(notification.type, 'repetitions_completed')
        self.assertIn('Цель выполнена', notification.text)

    async def test_decrement_does_not_create_missing_counter(self) -> None:
        self.redis.eval.return_value = -1
        self.assertIsNone(await self.counter.decrement(42, task_id='delivery'))


@unittest.skipUnless(os.environ.get('TEST_REDIS_URL'), 'Не задан TEST_REDIS_URL')
class RepetitionGoalRedisTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.redis = Redis.from_url(os.environ['TEST_REDIS_URL'], decode_responses=True)
        self.session = AsyncMock()
        self.session.scalar.return_value = 'Asia/Tbilisi'
        self.counter = RepetitionGoalCounter(self.session, redis=self.redis)
        self.key = f'test:repetition-goal:{uuid4().hex}'
        self.counter._key = lambda user_id: self.key
        self.user_id = int(uuid4().hex[:12], 16)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(user_notifications_channel(self.user_id))
        await self.pubsub.get_message(timeout=1)

    async def asyncTearDown(self) -> None:
        await self.pubsub.aclose()
        await self.redis.delete(self.key)
        await self.redis.aclose()

    async def test_initialization_and_concurrent_decrements_preserve_zero_and_expiry(self) -> None:
        self.assertEqual(await self.counter.initialize(self.user_id, 30), 30)
        expires_at = await self.redis.expiretime(self.key)

        await asyncio.gather(*(
            self.counter.decrement(self.user_id, task_id=f'answer-{index}')
            for index in range(29)
        ))
        self.assertEqual(await self.counter.get_remaining(self.user_id), 1)
        self.assertEqual(await self.counter.initialize(self.user_id, 30), 1)
        self.assertEqual(await self.redis.expiretime(self.key), expires_at)

        # Повторная доставка той же задачи не уменьшает остаток второй раз.
        self.assertEqual(await self.counter.decrement(self.user_id, task_id='answer-0'), 1)
        self.assertIsNone(await self.pubsub.get_message(timeout=0.05))

        await asyncio.gather(*(
            self.counter.decrement(self.user_id, task_id=f'final-{index}')
            for index in range(10)
        ))
        self.assertEqual(await self.counter.get_remaining(self.user_id), 0)
        self.assertEqual(await self.counter.initialize(self.user_id, 30), 0)
        self.assertEqual(await self.redis.expiretime(self.key), expires_at)

        message = await self.pubsub.get_message(timeout=1)
        notification = UserNotification.model_validate_json(message['data'])
        self.assertEqual(notification.type, 'repetitions_completed')
        self.assertIsNone(await self.pubsub.get_message(timeout=0.05))

    async def test_missing_and_expired_goals_can_be_initialized_again(self) -> None:
        self.assertIsNone(await self.counter.decrement(self.user_id, task_id='missing'))
        self.assertFalse(await self.redis.exists(self.key))
        self.assertEqual(await self.counter.initialize(self.user_id, 0), 0)
        self.assertEqual(await self.counter.get_remaining(self.user_id), 0)

        await self.redis.expireat(self.key, int(datetime.now(UTC).timestamp()) - 1)
        self.assertIsNone(await self.counter.get_remaining(self.user_id))
        self.assertEqual(await self.counter.initialize(self.user_id, 5), 5)

    async def test_zero_goal_does_not_decrement_or_repeat_completion_event(self) -> None:
        await self.counter.initialize(self.user_id, 0)
        self.assertEqual(await self.counter.decrement(self.user_id, task_id='after-zero'), 0)
        self.assertIsNone(await self.pubsub.get_message(timeout=0.05))

    async def test_parallel_initialization_uses_one_goal(self) -> None:
        results = await asyncio.gather(*(
            self.counter.initialize(self.user_id, count) for count in (5, 10, 30)
        ))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(await self.counter.get_remaining(self.user_id), results[0])
