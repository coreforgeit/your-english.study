import logging
import re
import unicodedata
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.errors import AudioTranscriptionError, VocabularyAnswerCheckError
from ai.transcriptions import AudioTranscriptionService
from ai.vocabulary_answers import check_vocabulary_answer
from api.schemas.vocabulary import VocabularyWordAnswerRequest
from db.models import WordEn, WordEnSynonym
from enums import AnswerLanguage, AnswerType, VocabularyAnswerVerdict


logger = logging.getLogger(__name__)
MAX_CORRECT_ANSWERS = 3


class VocabularyAnswerRequiredError(Exception):
    pass


class VocabularyAnswerWordNotFoundError(Exception):
    pass


class VocabularyAnswerTranscriptionError(Exception):
    pass


class VocabularyAnswerAICheckError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AudioAnswerFile:
    content: bytes
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class AnswerCheckResult:
    is_correct: bool
    has_typo: bool = False
    typo: dict[str, int | str | None] | None = None
    correct_answer: list[str] = field(default_factory=list)
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class VocabularyAnswerResult:
    answer: str
    check_result: AnswerCheckResult
    skip: bool


class VocabularyAnswerService:

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.transcription_service = AudioTranscriptionService()

    async def process(
        self,
        *,
        payload: VocabularyWordAnswerRequest,
        audio_file: AudioAnswerFile | None,
        user_id: int,
    ) -> VocabularyAnswerResult:
        total_started_at = perf_counter()
        # получаем текст ответа и тип
        answer, answer_type = await self._resolve_answer(payload, audio_file)
        answer_lookup_started_at = perf_counter()

        if payload.skip:
            check_result = await self._get_skipped_answer_result(payload)
        else:
            check_result = await self._check_answer(
                payload=payload,
                answer=answer,
            )

        answer_lookup_duration_ms = (
            perf_counter() - answer_lookup_started_at
        ) * 1000
        total_duration_ms = (perf_counter() - total_started_at) * 1000
        logger.info(
            'Ответ обработан: user_id=%s word_id=%s answer_type=%s skip=%s '
            'check_ms=%.2f total_ms=%.2f answer=%r',
            user_id,
            payload.word_id,
            answer_type,
            payload.skip,
            answer_lookup_duration_ms,
            total_duration_ms,
            answer,
        )
        return VocabularyAnswerResult(
            answer=answer,
            check_result=check_result,
            skip=payload.skip,
        )

    async def _get_skipped_answer_result(
        self,
        payload: VocabularyWordAnswerRequest,
    ) -> AnswerCheckResult:
        """
        Извлекает из базы правильный ответ, при пропуске
        """
        correct_answers = await self.get_correct_answers(
            word_id=payload.word_id,
            answer_language=payload.answer_language,
        )
        if correct_answers is None:
            raise VocabularyAnswerWordNotFoundError

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=correct_answers,
        )

    async def _check_answer(
        self,
        *,
        payload: VocabularyWordAnswerRequest,
        answer: str,
    ) -> AnswerCheckResult:
        check_result = await self.check_text_answer(
            word_id=payload.word_id,
            answer_language=payload.answer_language,
            answer=answer,
        )
        if check_result is None:
            logger.info(f'Ответ отклонён: слово не найдено word_id={payload.word_id}')
            raise VocabularyAnswerWordNotFoundError

        if check_result.is_correct:
            return check_result

        try:
            check_result = await self.check_text_answer_ai(
                word_id=payload.word_id,
                answer_language=payload.answer_language,
                answer=answer,
            )
            logger.info(f'Полный ответ AI при проверке слова: {check_result}')
        except VocabularyAnswerCheckError as exc:
            logger.exception(f'Ошибка AI-проверки ответа: word_id={payload.word_id}\n {exc}')
            raise VocabularyAnswerAICheckError from exc

        if check_result is None:
            logger.info(f'Ответ отклонён: слово не найдено word_id={payload.word_id}')
            raise VocabularyAnswerWordNotFoundError

        return check_result

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
        else:
            check_result = self._check_translation_answer(answer=answer, word=word)

        logger.info(
            f'Ответ проверен: word_id={word_id}, '
            f'answer_language={answer_language}, '
            f'is_correct={check_result.is_correct}, '
            f'has_typo={check_result.has_typo}\n'
            f'Полный ответ: {check_result}',
        )
        return check_result

    async def check_text_answer_ai(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
        answer: str,
    ) -> AnswerCheckResult | None:
        word = await self.session.get(
            WordEn,
            word_id,
            options=(selectinload(WordEn.translations),),
        )
        if word is None:
            logger.info(f'AI-проверка ответа: слово не найдено word_id={word_id}')
            return None

        if answer_language == AnswerLanguage.EN:
            source_text = word.translation
            source_language = AnswerLanguage.RU
        else:
            source_text = word.word
            source_language = AnswerLanguage.EN

        ai_result = await check_vocabulary_answer(
            source_text=source_text,
            answer=answer,
            source_language=source_language.value,
            target_language=answer_language.value,
            part_of_speech=word.part_of_speech,
        )
        check_result = AnswerCheckResult(
            is_correct=ai_result.verdict != VocabularyAnswerVerdict.INCORRECT,
            correct_answer=self._limit_correct_answers(
                ai_result.correct_answers,
            ),
            comment=ai_result.comment.strip() if ai_result.comment else None,
        )
        logger.info(
            f'Ответ проверен через AI: word_id={word_id} '
            f'answer_language={answer_language} verdict={ai_result.verdict} '
            f'comment={check_result.comment!r}',
        )
        return check_result

    async def get_correct_answers(
        self,
        word_id: int,
        answer_language: AnswerLanguage,
    ) -> list[str] | None:
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
            return None

        if answer_language == AnswerLanguage.EN:
            correct_answers = self._get_english_answer_candidates(word)
        else:
            correct_answers = self._get_translation_answer_candidates(word)

        return self._limit_correct_answers(correct_answers)

    def _compare_answer(
        self,
        *,
        answer: str,
        correct_answer: str,
    ) -> AnswerCheckResult:
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

    @staticmethod
    def _normalize_answer(value: str) -> str:
        return ' '.join(value.strip().casefold().replace('\u0451', '\u0435').split())

    def _check_english_answer(
        self,
        *,
        answer: str,
        word: WordEn,
    ) -> AnswerCheckResult:
        correct_answers = self._get_english_answer_candidates(word)
        for correct_answer in correct_answers:
            check_result = self._compare_answer(
                answer=answer,
                correct_answer=correct_answer,
            )
            if check_result.is_correct:
                return AnswerCheckResult(
                    is_correct=check_result.is_correct,
                    has_typo=check_result.has_typo,
                    typo=check_result.typo,
                    correct_answer=self._limit_correct_answers(
                        [correct_answer, *correct_answers],
                    ),
                )

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=self._limit_correct_answers(correct_answers),
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

    def _check_translation_answer(
        self,
        *,
        answer: str,
        word: WordEn,
    ) -> AnswerCheckResult:
        correct_answers = self._get_translation_answer_candidates(word)
        for correct_answer in correct_answers:
            check_result = self._compare_answer(
                answer=answer,
                correct_answer=correct_answer,
            )
            if check_result.is_correct:
                return AnswerCheckResult(
                    is_correct=check_result.is_correct,
                    has_typo=check_result.has_typo,
                    typo=check_result.typo,
                    correct_answer=self._limit_correct_answers(
                        [correct_answer, *correct_answers],
                    ),
                )

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=self._limit_correct_answers(correct_answers),
        )

    @staticmethod
    def _get_translation_answer_candidates(word: WordEn) -> list[str]:
        return [translation.word for translation in word.translations]

    @staticmethod
    def _limit_correct_answers(correct_answers: list[str]) -> list[str]:
        unique_answers: list[str] = []
        normalized_answers: set[str] = set()
        for answer in correct_answers:
            clean_answer = answer.strip()
            normalized_answer = clean_answer.casefold()
            if not clean_answer or normalized_answer in normalized_answers:
                continue

            normalized_answers.add(normalized_answer)
            unique_answers.append(clean_answer)
            if len(unique_answers) == MAX_CORRECT_ANSWERS:
                break

        return unique_answers

    async def _resolve_answer(
        self,
        payload: VocabularyWordAnswerRequest,
        audio_file: AudioAnswerFile | None,
    ) -> tuple[str, AnswerType]:
        if audio_file is not None:
            answer = await self._transcribe_audio_answer(payload, audio_file)
            return answer, AnswerType.AUDIO

        if payload.text_answer is not None:
            answer = payload.text_answer.strip()
            if answer or payload.skip:
                return answer, AnswerType.TEXT

        if payload.skip:
            return '', AnswerType.TEXT

        raise VocabularyAnswerRequiredError

    async def _transcribe_audio_answer(
        self,
        payload: VocabularyWordAnswerRequest,
        audio_file: AudioAnswerFile,
    ) -> str:
        try:
            transcription = await self.transcription_service.transcribe_audio(
                audio=audio_file.content,
                filename=audio_file.filename,
                content_type=audio_file.content_type,
                language=payload.answer_language,
                trim_silence=False,
            )
        except AudioTranscriptionError as exc:
            logger.exception(
                'Ошибка расшифровки аудио: word_id=%s',
                payload.word_id,
            )
            raise VocabularyAnswerTranscriptionError from exc

        answer = self._postprocess_transcribed_answer(transcription.text)
        logger.info(
            'Аудио расшифровано: word_id=%s raw=%r answer=%r '
            'trim_ms=%.2f transcription_ms=%.2f',
            payload.word_id,
            transcription.text,
            answer,
            transcription.trim_duration_ms,
            transcription.transcription_duration_ms,
        )
        return answer

    @staticmethod
    def _postprocess_transcribed_answer(value: str) -> str:
        without_punctuation = ''.join(
            char
            for char in value
            if not unicodedata.category(char).startswith('P')
        )
        return ' '.join(without_punctuation.lower().split())
