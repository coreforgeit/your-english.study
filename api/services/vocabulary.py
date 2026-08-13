import logging
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.vocabulary import VocabularyRepeatWordRequest, VocabularyWordsRequest
from core.config import settings
from db.models import LanguageLevel, LearnedWord, WordEn, WordEnSynonym
from enums import AnswerLanguage, LearnedWordStatus, WordStatus


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnswerCheckResult:
    is_correct: bool
    has_typo: bool = False
    typo: dict[str, int | str | None] | None = None
    correct_answer: str | None = None


class VocabularyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_learned_word_for_user(
        self,
        user_id: int,
        payload: VocabularyRepeatWordRequest,
    ) -> WordEn | None:
        stmt = (
            sa.select(WordEn)
            .join(LearnedWord, LearnedWord.word_id == WordEn.id)
            .options(
                selectinload(WordEn.language_level),
                selectinload(WordEn.translations),
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
        elif payload.level is not None:
            stmt = stmt.join(WordEn.language_level).where(
                LanguageLevel.name == _normalize_level(payload.level),
            )

        return await self.session.scalar(stmt)

    async def get_interval_repetition_word_ids(self, user_id: int) -> list[int]:
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
            for interval in settings.vocabulary_repetition_intervals
        ]

        if not repetition_conditions:
            return []

        stmt = (
            sa.select(LearnedWord.word_id)
            .where(
                LearnedWord.user_id == user_id,
                LearnedWord.status == LearnedWordStatus.NEW,
                sa.or_(*repetition_conditions),
            )
            .order_by(LearnedWord.created_at, LearnedWord.id)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_new_word_for_user(
        self,
        user_id: int,
        session_id: str,
        payload: VocabularyWordsRequest,
    ) -> WordEn | None:
        learned_words_stmt = sa.select(LearnedWord.word_id).where(
            LearnedWord.user_id == user_id,
        )
        word = await self._select_word(
            payload=payload,
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

    async def check_text_answer(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
        answer: str,
    ) -> AnswerCheckResult | None:
        word = await self.session.get(
            WordEn,
            word_id,
            options=(
                selectinload(WordEn.translations),
                selectinload(WordEn.synonym_links).selectinload(
                    WordEnSynonym.synonym_word_en,
                ),
                selectinload(WordEn.synonym_of_links).selectinload(
                    WordEnSynonym.word_en,
                ),
            ),
        )
        if word is None:
            logger.info(f'Проверка ответа: слово не найдено word_id={word_id}')
            return None

        if answer_language == AnswerLanguage.EN:
            check_result = self._check_english_answer(answer=answer, word=word)
            correct_answer = check_result.correct_answer
        else:
            check_result = self._check_translation_answer(answer=answer, word=word)
            correct_answer = check_result.correct_answer

        check_result = AnswerCheckResult(
            is_correct=check_result.is_correct,
            has_typo=check_result.has_typo,
            typo=check_result.typo,
            correct_answer=correct_answer,
        )
        logger.info(
            f'Ответ проверен: word_id={word_id}, '
            f'answer_language={answer_language}, '
            f'is_correct={check_result.is_correct}, '
            f'has_typo={check_result.has_typo}'
        )
        return check_result

    async def get_correct_answer(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
    ) -> str | None:
        word = await self.session.get(
            WordEn,
            word_id,
            options=(selectinload(WordEn.translations),),
        )
        if word is None:
            return None

        if answer_language == AnswerLanguage.EN:
            return word.word

        return word.translation

    async def save_answer_error(
        self,
        *,
        user_id: int,
        word_id: int,
        answer_type: str,
        answer_language: str,
        user_answer: str,
        check_result: AnswerCheckResult,
    ) -> None:
        if check_result.is_correct and not check_result.has_typo:
            return

        typo = check_result.typo or {}
        # self.session.add(
        #     AnswerError(
        #         user_id=user_id,
        #         word_id=word_id,
        #         answer_type=answer_type,
        #         answer_language=answer_language,
        #         user_answer=user_answer,
        #         correct_answer=check_result.correct_answer or '',
        #         is_correct=check_result.is_correct,
        #         has_typo=check_result.has_typo,
        #         typo_type=typo.get('type'),
        #         typo_index=typo.get('index'),
        #         expected=typo.get('expected'),
        #         actual=typo.get('actual'),
        #     ),
        # )
        # logger.info(
        #     f'Ошибка ответа сохранена: user_id={user_id}, word_id={word_id}, '
        #     f'is_correct={check_result.is_correct}, has_typo={check_result.has_typo}'
        # )

    def _check_answer(self, *, answer: str, correct_answer: str) -> AnswerCheckResult:
        normalized_answer = self._normalize_answer(answer)
        answer_variants = self._get_correct_answer_variants(correct_answer)

        for variant in answer_variants:
            normalized_variant = self._normalize_answer(variant)
            if normalized_answer == normalized_variant:
                return AnswerCheckResult(is_correct=True)

            typo = self._find_one_letter_typo(
                answer=normalized_answer,
                correct_answer=normalized_variant,
            )
            if typo is not None:
                return AnswerCheckResult(
                    is_correct=True,
                    has_typo=True,
                    typo=typo,
                )

        return AnswerCheckResult(is_correct=False)

    def _get_correct_answer_variants(self, correct_answer: str) -> list[str]:
        if not self._has_answer_separator(correct_answer):
            return [correct_answer]

        variants = [
            self._remove_punctuation(part).strip()
            for part in re.split(r'[,;/]+', correct_answer)
        ]
        variants = [variant for variant in variants if variant]
        if not variants:
            return [correct_answer]

        if all(len(variant.split()) == 1 for variant in variants):
            return variants

        return [correct_answer]

    def _find_one_letter_typo(
        self,
        *,
        answer: str,
        correct_answer: str,
    ) -> dict[str, int | str | None] | None:
        if len(answer) <= 3 or len(correct_answer) <= 3:
            return None

        if self._levenshtein_distance(answer, correct_answer) != 1:
            return None

        index = 0
        while (
            index < len(answer)
            and index < len(correct_answer)
            and answer[index] == correct_answer[index]
        ):
            index += 1

        if len(answer) == len(correct_answer):
            return {
                'index': index,
                'type': 'replace',
                'expected': correct_answer[index],
                'actual': answer[index],
            }

        if len(answer) < len(correct_answer):
            return {
                'index': index,
                'type': 'missing',
                'expected': correct_answer[index],
                'actual': None,
            }

        return {
            'index': index,
            'type': 'extra',
            'expected': None,
            'actual': answer[index],
        }

    @staticmethod
    def _has_answer_separator(value: str) -> bool:
        return any(separator in value for separator in (',', ';', '/'))

    @staticmethod
    def _remove_punctuation(value: str) -> str:
        return re.sub(r'[^\w\s-]+', ' ', value)

    @staticmethod
    def _levenshtein_distance(left: str, right: str) -> int:
        if left == right:
            return 0

        if len(left) < len(right):
            left, right = right, left

        previous_row = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current_row = [left_index]
            for right_index, right_char in enumerate(right, start=1):
                insert_cost = current_row[right_index - 1] + 1
                delete_cost = previous_row[right_index] + 1
                replace_cost = previous_row[right_index - 1] + (
                    left_char != right_char
                )
                current_row.append(min(insert_cost, delete_cost, replace_cost))

            previous_row = current_row

        return previous_row[-1]

    async def _select_word(
        self,
        payload: VocabularyWordsRequest,
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
        logger.info(f'payload: {payload}')
        if payload.level is not None:
            stmt = stmt.join(WordEn.language_level).where(
                LanguageLevel.name == _normalize_level(payload.level),
            )

        if extra_filters:
            stmt = stmt.where(*extra_filters)

        stmt = stmt.order_by(sa.func.random()).limit(1)
        # stmt = stmt.order_by(sa.func.random()).limit(1)

        logger.info(f'Выбираем слово: level={payload.level}')
        result = await self.session.execute(stmt)
        word = result.scalar_one_or_none()
        logger.info(f'Выбрано слово: word_id={getattr(word, "id", None)}')
        return word

    @staticmethod
    def _normalize_answer(value: str) -> str:
        return ' '.join(value.strip().casefold().replace('\u0451', '\u0435').split())

    def _check_english_answer(self, *, answer: str, word: WordEn) -> AnswerCheckResult:
        for correct_answer in self._get_english_answer_candidates(word):
            check_result = self._check_answer(answer=answer, correct_answer=correct_answer)
            if check_result.is_correct:
                return AnswerCheckResult(
                    is_correct=check_result.is_correct,
                    has_typo=check_result.has_typo,
                    typo=check_result.typo,
                    correct_answer=correct_answer,
                )

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=word.word,
        )

    @staticmethod
    def _get_english_answer_candidates(word: WordEn) -> list[str]:
        candidates = [
            word.word,
            *(
                link.synonym_word_en.word
                for link in word.synonym_links
                if link.synonym_word_en is not None
            ),
            *(
                link.word_en.word
                for link in word.synonym_of_links
                if link.word_en is not None
            ),
        ]
        return list(dict.fromkeys(candidates))

    def _check_translation_answer(self, *, answer: str, word: WordEn) -> AnswerCheckResult:
        for translation in word.translations:
            check_result = self._check_answer(answer=answer, correct_answer=translation.word)
            if check_result.is_correct:
                return AnswerCheckResult(
                    is_correct=check_result.is_correct,
                    has_typo=check_result.has_typo,
                    typo=check_result.typo,
                    correct_answer=translation.word,
                )

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=word.translation,
        )


def _normalize_level(level: str) -> str:
    return level.strip().upper()
