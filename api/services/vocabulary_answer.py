import logging
import unicodedata
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from ai.errors import AudioTranscriptionError, VocabularyAnswerCheckError
from ai.transcriptions import AudioTranscriptionService
from api.schemas.vocabulary import VocabularyWordAnswerRequest
from api.services.vocabulary import AnswerCheckResult, VocabularyService
from enums import AnswerType
from task_queue.tasks import record_word_repetition


logger = logging.getLogger(__name__)


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
class VocabularyAnswerResult:
    answer: str
    check_result: AnswerCheckResult
    skip: bool


class VocabularyAnswerService:
    def __init__(
        self,
        session: AsyncSession,
        vocabulary_service: VocabularyService | None = None,
        transcription_service: AudioTranscriptionService | None = None,
    ) -> None:
        self.vocabulary_service = (
            vocabulary_service
            if vocabulary_service is not None
            else VocabularyService(session)
        )
        self.transcription_service = (
            transcription_service
            if transcription_service is not None
            else AudioTranscriptionService()
        )

    async def process(
        self,
        *,
        payload: VocabularyWordAnswerRequest,
        audio_file: AudioAnswerFile | None,
        user_id: int,
        session_id: str,
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
                answer_type=answer_type,
                user_id=user_id,
            )

        answer_lookup_duration_ms = (
            perf_counter() - answer_lookup_started_at
        ) * 1000
        await self._enqueue_repetition_record(
            user_id=user_id,
            word_id=payload.word_id,
            is_correct=check_result.is_correct,
            session_id=session_id,
        )

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
        correct_answer = await self.vocabulary_service.get_correct_answer(
            word_id=payload.word_id,
            answer_language=payload.answer_language,
        )
        if correct_answer is None:
            raise VocabularyAnswerWordNotFoundError

        return AnswerCheckResult(
            is_correct=False,
            correct_answer=correct_answer,
        )

    async def _check_answer(
        self,
        *,
        payload: VocabularyWordAnswerRequest,
        answer: str,
        answer_type: AnswerType,
        user_id: int,
    ) -> AnswerCheckResult:
        # check_result = await self.vocabulary_service.check_text_answer(
        #     word_id=payload.word_id,
        #     answer_language=payload.answer_language,
        #     answer=answer,
        # )
        try:
            check_result = await self.vocabulary_service.check_text_answer_ai(
                word_id=payload.word_id,
                answer_language=payload.answer_language,
                answer=answer,
            )
            logger.info(
                'Полный ответ AI при проверке слова: %r',
                check_result,
            )
        except VocabularyAnswerCheckError as exc:
            logger.exception(
                'Ошибка AI-проверки ответа: word_id=%s',
                payload.word_id,
            )
            raise VocabularyAnswerAICheckError from exc

        if check_result is None:
            logger.info(
                'Ответ отклонён: слово не найдено word_id=%s',
                payload.word_id,
            )
            raise VocabularyAnswerWordNotFoundError

        await self.vocabulary_service.save_answer_error(
            user_id=user_id,
            word_id=payload.word_id,
            answer_type=answer_type,
            answer_language=payload.answer_language,
            user_answer=answer,
            check_result=check_result,
        )
        return check_result

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

    @staticmethod
    async def _enqueue_repetition_record(
        *,
        user_id: int,
        word_id: int,
        is_correct: bool,
        session_id: str,
    ) -> None:
        try:
            await record_word_repetition.kiq(
                user_id=user_id,
                word_id=word_id,
                is_correct=is_correct,
                session_id=session_id,
            )
        except Exception:
            logger.exception(
                'Не удалось отправить запись повторения в воркер: '
                'user_id=%s word_id=%s',
                user_id,
                word_id,
            )
