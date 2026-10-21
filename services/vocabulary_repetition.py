import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from db.models import LearnedWord, WordEn
from enums import LearnedWordStatus, WordStatus
from services.repetition_goal import RepetitionGoalCounter


class VocabularyRepetitionService:
    def __init__(
        self,
        session: AsyncSession,
        counter: RepetitionGoalCounter | None = None,
    ) -> None:
        self.session = session
        self.counter = counter if counter is not None else RepetitionGoalCounter(session)

    async def get_due_word_ids(self, user_id: int) -> list[int]:
        remaining = await self.counter.get_remaining(user_id)
        if remaining == 0:
            return []

        limit = self.counter.DAILY_LIMIT if remaining is None else remaining
        statement = self._build_due_word_ids_statement(user_id).limit(limit)
        result = await self.session.scalars(statement)
        word_ids = list(result.all())
        if remaining is None:
            remaining = await self.counter.initialize(user_id, len(word_ids))
        else:
            # Пока выполнялся SQL, воркер мог уменьшить дневной остаток.
            current_remaining = await self.counter.get_remaining(user_id)
            if current_remaining is not None:
                remaining = current_remaining
        return word_ids[:remaining]

    async def has_due_words(self, user_id: int) -> bool:
        if await self.counter.get_remaining(user_id) == 0:
            return False
        statement = self._build_due_word_ids_statement(user_id)
        word_id = await self.session.scalar(statement.limit(1))
        return word_id is not None

    def _build_due_word_ids_statement(
        self,
        user_id: int,
    ) -> Select[tuple[int]]:
        return (
            sa.select(LearnedWord.word_id)
            .join(LearnedWord.word)
            .where(
                LearnedWord.user_id == user_id,
                WordEn.status == WordStatus.ALLOWED,
                LearnedWord.status.in_(
                    (
                        LearnedWordStatus.NEW,
                        LearnedWordStatus.FAMILIAR,
                    ),
                ),
                sa.or_(
                    LearnedWord.last_reviewed_at.is_(None),
                    LearnedWord.last_reviewed_at
                    < sa.func.now() - sa.text("INTERVAL '3 days'"),
                ),
            )
            .order_by(
                LearnedWord.review_count.asc(),
                LearnedWord.last_reviewed_at.desc().nulls_first(),
                LearnedWord.id.asc(),
            )
        )
