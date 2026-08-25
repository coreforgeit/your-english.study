import logging

from openai import AsyncOpenAI, OpenAIError

from ai.client import get_openai_client
from ai.errors import SpeechGenerationError
from enums import SpeechModel, SpeechVoice


logger = logging.getLogger(__name__)


class TextToSpeechService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self.client = client or get_openai_client()

    async def synthesize(
        self,
        text: str,
        *,
        model: SpeechModel,
        voice: SpeechVoice,
        prompt: str | None = None,
    ) -> bytes:
        if not text.strip():
            raise ValueError('Text must not be empty')

        if not model.supports_voice(voice):
            raise ValueError(
                f'Voice {voice.value!r} is not supported by model {model.value!r}',
            )

        if prompt and not model.supports_instructions:
            raise ValueError(
                f'Model {model.value!r} does not support speech instructions',
            )

        try:
            if prompt:
                response = await self.client.audio.speech.create(
                    input=text,
                    model=model.value,
                    voice=voice.value,
                    instructions=prompt,
                    response_format='mp3',
                )
            else:
                response = await self.client.audio.speech.create(
                    input=text,
                    model=model.value,
                    voice=voice.value,
                    response_format='mp3',
                )
        except OpenAIError as exc:
            logger.exception(
                f'OpenAI не смог преобразовать текст в аудио: '
                f'model={model.value}, voice={voice.value}',
            )
            raise SpeechGenerationError('Speech generation failed') from exc

        return response.content
