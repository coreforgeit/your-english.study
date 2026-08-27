from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LearnedWord, WordEn
from enums import WordStatus


@dataclass(frozen=True, slots=True)
class LearnedWordRecordResult:
    created: bool
    needs_review: bool


class VocabularyLearningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_learned_word(
        self,
        *,
        user_id: int,
        word_id: int,
        session_id: str,
    ) -> LearnedWordRecordResult:
        word = await self.session.scalar(
            select(WordEn)
            .where(WordEn.id == word_id)
            .with_for_update(),
        )
        if word is None:
            raise LookupError(f'Слово {word_id} не найдено')

        insert_result = await self.session.execute(
            psql.insert(LearnedWord)
            .values(
                user_id=user_id,
                word_id=word_id,
                session_id=session_id,
            )
            .on_conflict_do_nothing(
                index_elements=[LearnedWord.user_id, LearnedWord.word_id],
            )
            .returning(LearnedWord.id),
        )
        created = insert_result.scalar_one_or_none() is not None

        needs_review = not word.is_reviewed
        if needs_review:
            word.status = WordStatus.CHECKING

        await self.session.flush()
        return LearnedWordRecordResult(
            created=created,
            needs_review=needs_review,
        )
