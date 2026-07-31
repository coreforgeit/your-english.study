import logging
from time import perf_counter
from typing import BinaryIO

from openai import AsyncOpenAI, OpenAIError

from ai.audio import AudioSilenceTrimmer
from ai.client import get_openai_client
from ai.errors import AudioTranscriptionError
from ai.prompts import get_transcription_prompt
from ai.schemas import AudioTranscriptionResult
from enums import AnswerLanguage, TranscriptionModel


logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        silence_trimmer: AudioSilenceTrimmer | None = None,
    ) -> None:
        self.client = client or get_openai_client()
        self.silence_trimmer = silence_trimmer or AudioSilenceTrimmer()

    async def transcribe_audio(
        self,
        audio: bytes | BinaryIO,
        *,
        filename: str = 'audio.webm',
        content_type: str = 'audio/webm',
        language: str | None = None,
        trim_silence: bool = True,
    ) -> AudioTranscriptionResult:

        if trim_silence:
            trim_started_at = perf_counter()
            file_payload = await self.silence_trimmer.trim(
                audio=audio,
                filename=filename,
                content_type=content_type,
            )
            trim_duration_ms = (perf_counter() - trim_started_at) * 1000
        else:
            file_payload = self._build_file_payload(
                audio=audio,
                filename=filename,
                content_type=content_type,
            )
            trim_duration_ms = 0.0

        transcription_model = self._get_transcription_model(language)
        transcription_params = {
            'model': transcription_model.value,
            'file': file_payload,
        }
        if language is not None:
            transcription_params['language'] = language

        prompt = get_transcription_prompt(language)
        if prompt is not None:
            transcription_params['prompt'] = prompt

        try:
            transcription_started_at = perf_counter()
            response = await self.client.audio.transcriptions.create(
                **transcription_params,
            )
            transcription_duration_ms = (perf_counter() - transcription_started_at) * 1000

            # logger.info(f'transcription_params: {transcription_params.get("model")} {transcription_params.get("language")}')
            # logger.info(f'text: {response.text} {response.usage}')
        except OpenAIError as exc:
            logger.exception('OpenAI audio transcription failed')
            raise AudioTranscriptionError('Audio transcription failed') from exc

        return AudioTranscriptionResult(
            text=response.text,
            model=transcription_model.value,
            trim_duration_ms=trim_duration_ms,
            transcription_duration_ms=transcription_duration_ms,
        )

    async def _comparison_models(self, file_payload, language, filename):
        models = (
            TranscriptionModel.GPT_4O_TRANSCRIBE,
            TranscriptionModel.GPT_4O_MINI_TRANSCRIBE,
        )
        response = None
        logger.info(f'---')
        for model in models:
            transcription_params = {
                'model': model.value,
                'file': file_payload,
            }
            if language:
                transcription_params['language'] = language

            prompt = get_transcription_prompt(language)
            if prompt is not None:
                transcription_params['prompt'] = prompt

            try:
                transcription_started_at = perf_counter()
                response = await self.client.audio.transcriptions.create(
                    **transcription_params,
                )
                transcription_duration_ms = (perf_counter() - transcription_started_at) * 1000

                logger.info(f'model: {model.value}')
                logger.info(f'text: {response.text} | {transcription_duration_ms} | {response.usage.input_token_details}')
            except OpenAIError as exc:
                logger.exception('OpenAI audio transcription failed')
                raise AudioTranscriptionError('Audio transcription failed') from exc
        logger.info(f'---')
        return response

    @staticmethod
    def _get_transcription_model(
        language: str | None,
    ) -> TranscriptionModel:
        if language == AnswerLanguage.RU:
            return TranscriptionModel.GPT_4O_MINI_TRANSCRIBE

        return TranscriptionModel.GPT_4O_TRANSCRIBE

    @staticmethod
    def _build_file_payload(
        audio: bytes | BinaryIO,
        *,
        filename: str,
        content_type: str,
    ) -> bytes | tuple[str, bytes, str] | BinaryIO:
        if isinstance(audio, bytes):
            return (filename, audio, content_type)

        return audio
