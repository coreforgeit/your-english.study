import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from db.models import LearnedWord
from enums import LearnedWordStatus


class VocabularyRepetitionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_due_word_ids(self, user_id: int) -> list[int]:
        statement = self._build_due_word_ids_statement(user_id)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def has_due_words(self, user_id: int) -> bool:
        statement = self._build_due_word_ids_statement(user_id)
        word_id = await self.session.scalar(statement.limit(1))
        return word_id is not None

    def _build_due_word_ids_statement(
        self,
        user_id: int,
    ) -> Select[tuple[int]]:
        return (
            sa.select(LearnedWord.word_id)
            .where(
                LearnedWord.user_id == user_id,
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
