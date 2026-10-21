import asyncio
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from taskiq.kicker import AsyncKicker
from taskiq.receiver import Receiver
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exchange import Exchange
from taskiq_aio_pika.queue import Queue

from api.dependencies import CurrentTelegramUser
from api.parsers import ParsedVocabularyAnswerRequest
from api.routers.vocabulary import answer_word, get_interval_repetitions
from api.schemas.vocabulary import VocabularyWordAnswerRequest
from db.models import LearnedWord, User, UserSettings, WordEn, WordRepetitionAnswer, WordRu
from db.models.base import Base
from enums import WorkerTaskName
from services.repetition_goal import RepetitionGoalCounter


@unittest.skipUnless(
    all(os.environ.get(name) for name in (
        'TEST_DATABASE_URL', 'TEST_REDIS_URL', 'TEST_RABBITMQ_URL',
    )),
    'Не заданы адреса тестовых PostgreSQL, Redis и RabbitMQ',
)
class VocabularyRepetitionPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Реализация worker импортируется только в интеграционном тесте.
        from worker.analytics.vocabulary.tasks import record_word_repetition

        suffix = uuid4().hex
        self.schema = f'test_repetition_{suffix}'
        self.engine = create_async_engine(
            os.environ['TEST_DATABASE_URL'],
            execution_options={'schema_translate_map': {None: self.schema}},
        )
        self.addAsyncCleanup(self.engine.dispose)
        async with self.engine.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(self.schema))
            await connection.run_sync(Base.metadata.create_all)
        self.addAsyncCleanup(self._drop_schema)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        self.redis = Redis.from_url(os.environ['TEST_REDIS_URL'], decode_responses=True)
        self.addAsyncCleanup(self.redis.aclose)
        self.user = CurrentTelegramUser(id=int(suffix[:12], 16), session_id=suffix)
        self.addAsyncCleanup(self._delete_counter)
        for target, value in (
            ('services.repetition_goal.RepetitionGoalCounter._redis_client', self.redis),
            ('worker.analytics.vocabulary.tasks.async_session_factory', self.sessions),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        exchange = Exchange(name=f'test-repetition-{suffix}')
        queue = Queue(name=f'test-repetition-{suffix}')
        dead_letter_queue = Queue(name=f'test-repetition-dead-{suffix}')
        self.producer = AioPikaBroker(
            os.environ['TEST_RABBITMQ_URL'], exchange=exchange,
            task_queues=[queue], dead_letter_queue=dead_letter_queue,
        )
        self.consumer = AioPikaBroker(
            os.environ['TEST_RABBITMQ_URL'], exchange=exchange,
            task_queues=[queue], dead_letter_queue=dead_letter_queue,
        )
        self.consumer.is_worker_process = True
        self.worker_task = self.consumer.task(
            task_name=WorkerTaskName.RECORD_WORD_REPETITION.value,
        )(record_word_repetition.original_func)
        for broker in (self.producer, self.consumer):
            self.addAsyncCleanup(broker.shutdown)
            await broker.startup()
        self.addAsyncCleanup(
            self._delete_broker_resources, queue.name, dead_letter_queue.name, exchange.name,
        )
        self.receiver = Receiver(self.consumer, max_async_tasks=1)
        self.messages = self.consumer.listen()
        self.addAsyncCleanup(self._close_messages)
        kicker_patch = patch('api.routers.vocabulary.record_word_repetition', AsyncKicker(
            WorkerTaskName.RECORD_WORD_REPETITION.value, self.producer, {},
        ))
        kicker_patch.start()
        self.addCleanup(kicker_patch.stop)

        async with self.sessions() as session:
            session.add(User(id=self.user.id, full_name='Тест повторения'))
            await session.flush()
            session.add(UserSettings(user_id=self.user.id, timezone='Asia/Tbilisi'))
            words = [WordEn(word=f'pipeline-{suffix}-{index}', translations=[WordRu(word='слово')])
                     for index in range(40)]
            session.add_all(words)
            await session.flush()
            session.add_all(LearnedWord(
                user_id=self.user.id, word_id=word.id, session_id=suffix,
            ) for word in words)
            await session.commit()

    async def _drop_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(sa.schema.DropSchema(self.schema, cascade=True))

    async def _delete_counter(self) -> None:
        await self.redis.delete(RepetitionGoalCounter._key(self.user.id))

    async def _close_messages(self) -> None:
        await self.messages.aclose()

    async def _delete_broker_resources(
        self, queue_name: str, dead_letter_queue_name: str, exchange_name: str,
    ) -> None:
        channel = self.consumer.write_channel
        await channel.queue_delete(queue_name)
        await channel.queue_delete(dead_letter_queue_name)
        await channel.exchange_delete(exchange_name)

    async def _request_words(self) -> list[int]:
        async with self.sessions() as session:
            response = await get_interval_repetitions(current_user=self.user, session=session)
            return response.data

    async def _answer(self, word_id: int):
        async with self.sessions() as session:
            return await answer_word(
                parsed_request=ParsedVocabularyAnswerRequest(
                    payload=VocabularyWordAnswerRequest(
                        word_id=word_id, answer_type='text',
                        answer_language='ru', text_answer='слово',
                    ),
                    audio_file=None,
                ),
                current_user=self.user,
                session=session,
            )

    async def _consume_answer(self, word_id: int) -> None:
        message = await asyncio.wait_for(anext(self.messages), timeout=10)
        task_message = self.consumer.formatter.loads(message.data)
        self.assertEqual(task_message.task_name, WorkerTaskName.RECORD_WORD_REPETITION.value)
        self.assertEqual(task_message.kwargs['word_id'], word_id)
        self.assertEqual(task_message.kwargs['user_id'], self.user.id)
        self.assertTrue(task_message.kwargs['is_correct'])
        result = await self.receiver.run_task(self.worker_task.original_func, task_message)
        self.assertFalse(result.is_err, repr(result.error))
        await message.ack()

    async def test_thirty_words_ten_answers_leave_twenty_without_reviewed_words(self) -> None:
        word_ids = await self._request_words()
        self.assertEqual(len(word_ids), 30)
        async with self.sessions() as session:
            counter = RepetitionGoalCounter(session)
            self.assertEqual(await counter.get_remaining(self.user.id), 30)

        for index, word_id in enumerate(word_ids[:10], start=1):
            response = await self._answer(word_id)
            self.assertTrue(response.data.is_correct)
            await self._consume_answer(word_id)

            async with self.sessions() as session:
                learned_word = await session.scalar(sa.select(LearnedWord).where(
                    LearnedWord.user_id == self.user.id, LearnedWord.word_id == word_id,
                ))
                self.assertEqual(learned_word.review_count, 1)
                self.assertIsNotNone(learned_word.last_reviewed_at)
                self.assertEqual(await RepetitionGoalCounter(session).get_remaining(self.user.id), 30 - index)

        remaining_ids = await self._request_words()
        self.assertEqual(len(remaining_ids), 20)
        self.assertTrue(set(remaining_ids).isdisjoint(word_ids[:10]))
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(sa.select(sa.func.count()).select_from(
                WordRepetitionAnswer,
            )), 10)

    async def test_api_returns_before_delayed_worker_saves_progress(self) -> None:
        word_id = (await self._request_words())[0]
        # Consumer ещё не запущен: API должен завершиться после публикации задачи.
        response = await asyncio.wait_for(self._answer(word_id), timeout=2)
        self.assertTrue(response.data.success)
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(sa.select(sa.func.count()).select_from(
                WordRepetitionAnswer,
            )), 0)
            learned_word = await session.scalar(sa.select(LearnedWord).where(
                LearnedWord.user_id == self.user.id, LearnedWord.word_id == word_id,
            ))
            self.assertEqual(learned_word.review_count, 0)
            self.assertIsNone(learned_word.last_reviewed_at)
            self.assertEqual(await RepetitionGoalCounter(session).get_remaining(self.user.id), 30)

        await self._consume_answer(word_id)

        remaining_ids = await self._request_words()
        self.assertEqual(len(remaining_ids), 29)
        self.assertNotIn(word_id, remaining_ids)
