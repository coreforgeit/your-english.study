from dataclasses import dataclass
import logging

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.vocabulary import VocabularyRepeatWordRequest
from db.models import LanguageLevel, LearnedWord, WordEn
from enums import AnswerLanguage, LearnedWordStatus, WordStatus


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VocabularyRepeatWord:
    word: WordEn
    answer_language: AnswerLanguage


class VocabularyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mark_word_for_manual_review(
        self,
        word_id: int,
    ) -> WordEn | None:
        word = await self.session.get(WordEn, word_id)
        if word is None:
            return None

        word.status = WordStatus.MANUAL_REVIEW
        await self.session.flush()
        return word

    async def get_learned_word_for_user(
        self,
        user_id: int,
        payload: VocabularyRepeatWordRequest,
    ) -> VocabularyRepeatWord | None:
        stmt = (
            sa.select(LearnedWord)
            .join(LearnedWord.word)
            .options(
                selectinload(LearnedWord.word).selectinload(
                    WordEn.language_level,
                ),
                selectinload(LearnedWord.word).selectinload(
                    WordEn.translations,
                ),
            )
            .where(
                LearnedWord.user_id == user_id,
                WordEn.status == WordStatus.ALLOWED,
            )
            .order_by(
                LearnedWord.review_count,
                sa.func.random(),
            )
            .limit(1)
        )
        if payload.word_id is not None:
            stmt = stmt.where(WordEn.id == payload.word_id)
        else:
            stmt = stmt.where(
                LearnedWord.status.in_(
                    (
                        LearnedWordStatus.NEW,
                        LearnedWordStatus.FAMILIAR,
                    ),
                ),
            )

        learned_word = await self.session.scalar(stmt)
        if learned_word is None:
            return None

        answer_language = (
            AnswerLanguage.RU
            if learned_word.status == LearnedWordStatus.NEW
            else AnswerLanguage.EN
        )
        return VocabularyRepeatWord(
            word=learned_word.word,
            answer_language=answer_language,
        )

    async def get_new_word_for_user(
        self,
        user_id: int,
        session_id: str,
        language_level_grade: int | None,
    ) -> WordEn | None:
        logger.info(f'language_level_grade: {language_level_grade}')
        learned_words_stmt = sa.select(LearnedWord.word_id).where(
            LearnedWord.user_id == user_id,
        )
        word = await self._select_word(
            language_level_grade=language_level_grade,
            extra_filters=[WordEn.id.not_in(learned_words_stmt)],
        )
        if word is None:
            return None

        stmt = (
            psql.insert(LearnedWord)
            .values(
                user_id=user_id,
                word_id=word.id,
                session_id=session_id,
            )
            .on_conflict_do_nothing(
                index_elements=[LearnedWord.user_id, LearnedWord.word_id],
            )
        )
        await self.session.execute(stmt)
        logger.info(f'Выученное слово сохранено: user_id={user_id}, word_id={word.id}')
        return word

    async def _select_word(
        self,
        language_level_grade: int | None = None,
        extra_filters: list[sa.ColumnElement[bool]] | None = None,
    ) -> WordEn | None:
        stmt = (
            sa.select(WordEn)
            .options(
                selectinload(WordEn.language_level),
                selectinload(WordEn.translations),
            )
            .where(WordEn.status == WordStatus.ALLOWED)
        )
        if language_level_grade is not None:
            maximum_grade = min(language_level_grade + 1, 6)
            stmt = stmt.join(WordEn.language_level).where(
                LanguageLevel.grade <= maximum_grade,
            )

        if extra_filters:
            stmt = stmt.where(*extra_filters)

        stmt = stmt.order_by(sa.func.random()).limit(1)

        logger.info('Выбираем слово: language_level_grade=%s', language_level_grade)
        result = await self.session.execute(stmt)
        word = result.scalar_one_or_none()
        logger.info(f'Выбрано слово: word_id={getattr(word, "id", None)} level={getattr(word, "level_id", None)}')
        return word

