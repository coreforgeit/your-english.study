import logging

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.telegram_app import AnswerLanguage, TelegramWordsRequest
from db.models import LearnedWord, Word
from db.models.enums import WordStatus


logger = logging.getLogger(__name__)


class TelegramAppService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_learned_word_for_user(
        self,
        user_id: int,
        payload: TelegramWordsRequest,
    ) -> Word | None:
        learned_words_stmt = sa.select(LearnedWord.word_id).where(
            LearnedWord.user_id == user_id,
        )
        return await self._select_word(
            payload=payload,
            extra_filters=[Word.id.in_(learned_words_stmt)],
        )

    async def get_new_word_for_user(
        self,
        user_id: int,
        payload: TelegramWordsRequest,
    ) -> Word | None:
        learned_words_stmt = sa.select(LearnedWord.word_id).where(
            LearnedWord.user_id == user_id,
        )
        word = await self._select_word(
            payload=payload,
            extra_filters=[Word.id.not_in(learned_words_stmt)],
        )
        if word is None:
            return None

        stmt = (
            psql.insert(LearnedWord)
            .values(user_id=user_id, word_id=word.id)
            .on_conflict_do_nothing(
                index_elements=[LearnedWord.user_id, LearnedWord.word_id],
            )
        )
        await self.session.execute(stmt)
        logger.info('Learned word saved: user_id=%s word_id=%s', user_id, word.id)
        return word

    async def check_text_answer(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
        answer: str,
    ) -> bool | None:
        word = await self.session.get(Word, word_id)
        if word is None:
            logger.info('Answer check failed: word not found word_id=%s', word_id)
            return None

        if answer_language == AnswerLanguage.EN:
            correct_answer = word.word
        else:
            correct_answer = word.translation

        is_correct = (
            self._normalize_answer(answer) == self._normalize_answer(correct_answer)
        )
        logger.info(
            'Answer checked: word_id=%s answer_language=%s is_correct=%s',
            word_id,
            answer_language,
            is_correct,
        )
        return is_correct

    async def _select_word(
        self,
        payload: TelegramWordsRequest,
        extra_filters: list[sa.ColumnElement[bool]] | None = None,
    ) -> Word | None:
        stmt = sa.select(Word).where(Word.status == WordStatus.ALLOWED)
        if payload.level is not None:
            stmt = stmt.where(Word.level == payload.level)

        if extra_filters:
            stmt = stmt.where(*extra_filters)

        stmt = stmt.order_by(sa.func.random()).limit(1)

        logger.info('Selecting word: level=%s', payload.level)
        result = await self.session.execute(stmt)
        word = result.scalar_one_or_none()
        logger.info('Selected word: word_id=%s', getattr(word, 'id', None))
        return word

    @staticmethod
    def _normalize_answer(value: str) -> str:
        return value.strip().casefold()

# alembic revision --autogenerate -m "learning_words"
