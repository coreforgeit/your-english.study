import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LearnedWord, WordRepetitionAnswer
from enums import AnswerLanguage, LearnedWordStatus


logger = logging.getLogger(__name__)


class VocabularyRepetitionAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_answer(
        self,
        *,
        user_id: int,
        word_id: int,
        session_id: str,
        is_correct: bool,
    ) -> None:

        self.session.add(
            WordRepetitionAnswer(
                user_id=user_id,
                word_id=word_id,
                session_id=session_id,
                is_correct=is_correct,
            ),
        )
        await self.session.flush()

        learned_word = await self.session.scalar(
            sa.select(LearnedWord)
            .where(
                LearnedWord.user_id == user_id,
                LearnedWord.word_id == word_id,
            )
            .with_for_update(),
        )
        if learned_word is None:
            logger.warning(f'Аналитика повторения: изучаемое слово не найдено, user_id={user_id} word_id={word_id}')
            return None

        learned_word.review_count += 1
        learned_word.last_reviewed_at = datetime.now(UTC)
        if learned_word.status == LearnedWordStatus.LEARNED:
            return

        recent_answers_result = await self.session.scalars(
            sa.select(WordRepetitionAnswer.is_correct)
            .where(
                WordRepetitionAnswer.user_id == user_id,
                WordRepetitionAnswer.word_id == word_id,
            )
            .order_by(
                WordRepetitionAnswer.created_at.desc(),
            )
            .limit(3),
        )
        recent_answers = list(recent_answers_result.all())
        next_status = self._get_next_status(
            learned_word.status,
            recent_answers,
        )
        if next_status != learned_word.status:
            previous_status = learned_word.status
            learned_word.status = next_status
            logger.info(
                f'Статус изучаемого слова изменён: user_id={user_id} '
                f'word_id={word_id} status={previous_status.value} '
                f'new_status={next_status.value}',
            )

    @staticmethod
    def _get_next_status(
        current_status: LearnedWordStatus,
        recent_answers: list[bool],
    ) -> LearnedWordStatus:
        last_three_are_correct = (
            len(recent_answers) >= 3
            and all(recent_answers[:3])
        )
        last_two_are_incorrect = (
            len(recent_answers) >= 2
            and not any(recent_answers[:2])
        )

        if current_status == LearnedWordStatus.NEW and last_three_are_correct:
            return LearnedWordStatus.FAMILIAR

        if current_status == LearnedWordStatus.FAMILIAR:
            if last_two_are_incorrect:
                return LearnedWordStatus.NEW
            if last_three_are_correct:
                return LearnedWordStatus.LEARNED

        return current_status
