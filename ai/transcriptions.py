import logging
from typing import BinaryIO

from openai import AsyncOpenAI, OpenAIError

from ai.audio import AudioSilenceTrimmer
from ai.client import get_openai_client
from ai.errors import AudioTranscriptionError
from ai.schemas import AudioTranscriptionResult
from core.config import settings


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
            file_payload = await self.silence_trimmer.trim(
                audio=audio,
                filename=filename,
                content_type=content_type,
            )
        else:
            file_payload = self._build_file_payload(
                audio=audio,
                filename=filename,
                content_type=content_type,
            )

        transcription_params = {
            'model': settings.open_ai_transcription_model,
            'file': file_payload,
        }
        if language is not None:
            transcription_params['language'] = language

        try:
            response = await self.client.audio.transcriptions.create(
                **transcription_params,
            )
        except OpenAIError as exc:
            logger.exception('OpenAI audio transcription failed')
            raise AudioTranscriptionError('Audio transcription failed') from exc

        return AudioTranscriptionResult(
            text=response.text,
            model=settings.open_ai_transcription_model,
        )

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
