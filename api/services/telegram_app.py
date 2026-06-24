import logging
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.telegram_app import AnswerLanguage, TelegramWordsRequest
from db.models import AnswerError, LearnedWord, Word
from db.models.enums import WordStatus


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnswerCheckResult:
    is_correct: bool
    has_typo: bool = False
    typo: dict[str, int | str | None] | None = None
    correct_answer: str | None = None


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
        logger.info(f'Выученное слово сохранено: user_id={user_id}, word_id={word.id}')
        return word

    async def check_text_answer(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
        answer: str,
    ) -> AnswerCheckResult | None:
        word = await self.session.get(Word, word_id)
        if word is None:
            logger.info(f'Проверка ответа: слово не найдено word_id={word_id}')
            return None

        if answer_language == AnswerLanguage.EN:
            correct_answer = word.word
        else:
            correct_answer = word.translation

        check_result = self._check_answer(answer=answer, correct_answer=correct_answer)
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
        logger.info(
            f'Ошибка ответа сохранена: user_id={user_id}, word_id={word_id}, '
            f'is_correct={check_result.is_correct}, has_typo={check_result.has_typo}'
        )

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
        payload: TelegramWordsRequest,
        extra_filters: list[sa.ColumnElement[bool]] | None = None,
    ) -> Word | None:
        stmt = sa.select(Word).where(Word.status == WordStatus.ALLOWED)
        logger.info(f'payload: {payload}')
        if payload.level is not None:
            stmt = stmt.where(Word.level == payload.level)

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
