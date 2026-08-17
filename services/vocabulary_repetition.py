from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from core.config import settings
from db.models import LearnedWord
from enums import LearnedWordStatus


class VocabularyRepetitionService:
    def __init__(
        self,
        session: AsyncSession,
        repetition_intervals: Sequence[int] | None = None,
    ) -> None:
        self.session = session
        self.repetition_intervals = tuple(
            settings.vocabulary_repetition_intervals
            if repetition_intervals is None
            else repetition_intervals
        )

    async def get_due_word_ids(self, user_id: int) -> list[int]:
        statement = self._build_due_word_ids_statement(user_id)
        if statement is None:
            return []

        result = await self.session.scalars(
            statement.order_by(LearnedWord.created_at, LearnedWord.id),
        )
        return list(result.all())

    async def has_due_words(self, user_id: int) -> bool:
        statement = self._build_due_word_ids_statement(user_id)
        if statement is None:
            return False

        word_id = await self.session.scalar(statement.limit(1))
        return word_id is not None

    def _build_due_word_ids_statement(
        self,
        user_id: int,
    ) -> Select[tuple[int]] | None:
        created_date = sa.cast(LearnedWord.created_at, sa.Date)
        last_reviewed_date = sa.cast(LearnedWord.last_reviewed_at, sa.Date)
        repetition_conditions = [
            sa.and_(
                created_date + interval <= sa.func.current_date(),
                sa.or_(
                    LearnedWord.last_reviewed_at.is_(None),
                    last_reviewed_date < created_date + interval,
                ),
            )
            for interval in self.repetition_intervals
        ]

        if not repetition_conditions:
            return None

        return sa.select(LearnedWord.word_id).where(
            LearnedWord.user_id == user_id,
            LearnedWord.status == LearnedWordStatus.NEW,
            sa.or_(*repetition_conditions),
        )
