import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.telegram_app import TelegramWordsMode, TelegramWordsRequest
from db.models import UserWord, Word
from db.models.enums import WordCountry, WordStatus


class TelegramAppService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_words(self, payload: TelegramWordsRequest) -> list[Word]:
        if payload.mode == TelegramWordsMode.LEARN:
            return await self._get_new_word(payload)

        return await self._get_repeat_words(payload)

    async def _get_new_word(self, payload: TelegramWordsRequest) -> list[Word]:
        stmt = sa.select(Word).where(Word.status == WordStatus.ALLOWED)
        stmt = self._apply_word_filters(stmt, payload)

        if payload.user_id is not None:
            learned_words_stmt = sa.select(UserWord.word_id).where(
                UserWord.user_id == payload.user_id,
            )
            stmt = stmt.where(Word.id.not_in(learned_words_stmt))

        stmt = stmt.order_by(sa.func.random()).limit(1)

        result = await self.session.execute(stmt)
        word = result.scalar_one_or_none()
        if word is None:
            return []

        if payload.user_id is not None:
            user_word_stmt = (
                psql.insert(UserWord)
                .values(user_id=payload.user_id, word_id=word.id)
                .on_conflict_do_nothing(
                    index_elements=[UserWord.user_id, UserWord.word_id],
                )
            )
            await self.session.execute(user_word_stmt)

        return [word]

    async def _get_repeat_words(self, payload: TelegramWordsRequest) -> list[Word]:
        if payload.user_id is None:
            return []

        stmt = (
            sa.select(Word)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(UserWord.user_id == payload.user_id)
            .where(Word.status == WordStatus.ALLOWED)
        )
        stmt = self._apply_word_filters(stmt, payload)
        stmt = stmt.order_by(Word.id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _apply_word_filters(
        self,
        stmt: sa.Select[tuple[Word]],
        payload: TelegramWordsRequest,
    ) -> sa.Select[tuple[Word]]:
        if payload.level is not None:
            stmt = stmt.where(Word.level == payload.level)

        if payload.country is not None:
            stmt = stmt.where(
                Word.country.in_([payload.country.value, WordCountry.BOTH.value]),
            )

        return stmt
