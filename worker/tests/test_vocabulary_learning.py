import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WordEn
from enums import TextModel, WordStatus
from worker.vocabulary.learning_service import (
    LearnedWordRecordResult,
    VocabularyLearningService,
)
from worker.vocabulary.tasks import record_learned_word


class VocabularyLearningServiceTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_session() -> MagicMock:
        session = MagicMock(spec=AsyncSession)
        session.scalar = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    async def test_records_word_and_marks_it_for_review(self) -> None:
        session = self.make_session()
        word = WordEn(
            word='assignment',
            is_reviewed=False,
            status=WordStatus.ALLOWED,
        )
        session.scalar.return_value = word
        insert_result = MagicMock()
        insert_result.scalar_one_or_none.return_value = 101
        session.execute.return_value = insert_result
        service = VocabularyLearningService(session)

        result = await service.record_learned_word(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        self.assertTrue(result.created)
        self.assertTrue(result.needs_review)
        self.assertEqual(word.status, WordStatus.CHECKING)
        session.execute.assert_awaited_once()
        insert_statement = session.execute.await_args.args[0]
        self.assertIn(
            'ON CONFLICT (user_id, word_id) DO NOTHING',
            str(insert_statement.compile()),
        )
        self.assertIn(
            'RETURNING learned_words.id',
            str(insert_statement.compile()),
        )
        session.flush.assert_awaited_once_with()

    async def test_reviewed_word_does_not_need_review(self) -> None:
        session = self.make_session()
        word = WordEn(
            word='assignment',
            is_reviewed=True,
            status=WordStatus.ALLOWED,
        )
        session.scalar.return_value = word
        insert_result = MagicMock()
        insert_result.scalar_one_or_none.return_value = 101
        session.execute.return_value = insert_result
        service = VocabularyLearningService(session)

        result = await service.record_learned_word(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        self.assertTrue(result.created)
        self.assertFalse(result.needs_review)
        self.assertEqual(word.status, WordStatus.ALLOWED)

    async def test_reports_existing_learned_word(self) -> None:
        session = self.make_session()
        session.scalar.return_value = WordEn(
            word='assignment',
            is_reviewed=True,
            status=WordStatus.ALLOWED,
        )
        insert_result = MagicMock()
        insert_result.scalar_one_or_none.return_value = None
        session.execute.return_value = insert_result

        result = await VocabularyLearningService(session).record_learned_word(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        self.assertFalse(result.created)


class VocabularyLearningTaskTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        'worker.vocabulary.tasks.check_new_words_milestone_notification.kiq',
        new_callable=AsyncMock,
    )
    @patch('worker.vocabulary.tasks.review_word.kiq', new_callable=AsyncMock)
    @patch('worker.vocabulary.tasks.VocabularyLearningService')
    @patch('worker.vocabulary.tasks.async_session_factory')
    async def test_sends_unreviewed_word_to_review_task(
        self,
        session_factory: MagicMock,
        service_class: MagicMock,
        enqueue_review: AsyncMock,
        enqueue_notification_check: AsyncMock,
    ) -> None:
        session = MagicMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session_context
        service_class.return_value.record_learned_word = AsyncMock(
            return_value=LearnedWordRecordResult(
                created=True,
                needs_review=True,
            ),
        )

        await record_learned_word.original_func(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        service_class.return_value.record_learned_word.assert_awaited_once_with(
            user_id=42,
            word_id=7,
            session_id='session',
        )
        enqueue_review.assert_awaited_once_with(
            word_id=7,
            model=TextModel.GPT_4O_MINI.value,
            session_id='session',
        )
        session.commit.assert_awaited_once_with()
        session.rollback.assert_not_awaited()
        enqueue_notification_check.assert_awaited_once_with(user_id=42)

    @patch(
        'worker.vocabulary.tasks.check_new_words_milestone_notification.kiq',
        new_callable=AsyncMock,
    )
    @patch('worker.vocabulary.tasks.review_word.kiq', new_callable=AsyncMock)
    @patch('worker.vocabulary.tasks.VocabularyLearningService')
    @patch('worker.vocabulary.tasks.async_session_factory')
    async def test_does_not_review_already_reviewed_word(
        self,
        session_factory: MagicMock,
        service_class: MagicMock,
        enqueue_review: AsyncMock,
        enqueue_notification_check: AsyncMock,
    ) -> None:
        session = MagicMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session_context
        service_class.return_value.record_learned_word = AsyncMock(
            return_value=LearnedWordRecordResult(
                created=True,
                needs_review=False,
            ),
        )

        await record_learned_word.original_func(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        enqueue_review.assert_not_awaited()
        enqueue_notification_check.assert_awaited_once_with(user_id=42)
        session.commit.assert_awaited_once_with()
        session.rollback.assert_not_awaited()

    @patch(
        'worker.vocabulary.tasks.check_new_words_milestone_notification.kiq',
        new_callable=AsyncMock,
    )
    @patch('worker.vocabulary.tasks.review_word.kiq', new_callable=AsyncMock)
    @patch('worker.vocabulary.tasks.VocabularyLearningService')
    @patch('worker.vocabulary.tasks.async_session_factory')
    async def test_does_not_check_milestone_for_existing_word(
        self,
        session_factory: MagicMock,
        service_class: MagicMock,
        enqueue_review: AsyncMock,
        enqueue_notification_check: AsyncMock,
    ) -> None:
        session = MagicMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session_context
        service_class.return_value.record_learned_word = AsyncMock(
            return_value=LearnedWordRecordResult(
                created=False,
                needs_review=False,
            ),
        )

        await record_learned_word.original_func(
            user_id=42,
            word_id=7,
            session_id='session',
        )

        enqueue_review.assert_not_awaited()
        enqueue_notification_check.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
