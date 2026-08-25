import unittest
from unittest.mock import AsyncMock, Mock

from openai import OpenAIError

from ai.errors import SpeechGenerationError
from ai.speech import TextToSpeechService
from enums import SpeechModel, SpeechVoice


class TextToSpeechServiceTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _client(audio: bytes = b'audio') -> Mock:
        client = Mock()
        client.audio.speech.create = AsyncMock(
            return_value=Mock(content=audio),
        )
        return client

    async def test_synthesizes_mp3_with_prompt(self) -> None:
        client = self._client()
        service = TextToSpeechService(client=client)

        result = await service.synthesize(
            'Привет',
            model=SpeechModel.GPT_4O_MINI_TTS,
            voice=SpeechVoice.MARIN,
            prompt='Говори спокойно.',
        )

        self.assertEqual(result, b'audio')
        client.audio.speech.create.assert_awaited_once_with(
            input='Привет',
            model='gpt-4o-mini-tts',
            voice='marin',
            instructions='Говори спокойно.',
            response_format='mp3',
        )

    async def test_synthesizes_with_legacy_model_without_prompt(self) -> None:
        client = self._client()
        service = TextToSpeechService(client=client)

        await service.synthesize(
            'Hello',
            model=SpeechModel.TTS_1,
            voice=SpeechVoice.ALLOY,
        )

        client.audio.speech.create.assert_awaited_once_with(
            input='Hello',
            model='tts-1',
            voice='alloy',
            response_format='mp3',
        )

    async def test_rejects_empty_text(self) -> None:
        client = self._client()
        service = TextToSpeechService(client=client)

        with self.assertRaisesRegex(ValueError, 'Text must not be empty'):
            await service.synthesize(
                '  ',
                model=SpeechModel.GPT_4O_MINI_TTS,
                voice=SpeechVoice.CEDAR,
            )

        client.audio.speech.create.assert_not_awaited()

    async def test_rejects_unsupported_legacy_voice(self) -> None:
        client = self._client()
        service = TextToSpeechService(client=client)

        with self.assertRaisesRegex(ValueError, 'is not supported'):
            await service.synthesize(
                'Hello',
                model=SpeechModel.TTS_1_HD,
                voice=SpeechVoice.MARIN,
            )

        client.audio.speech.create.assert_not_awaited()

    async def test_rejects_prompt_for_legacy_model(self) -> None:
        client = self._client()
        service = TextToSpeechService(client=client)

        with self.assertRaisesRegex(ValueError, 'does not support'):
            await service.synthesize(
                'Hello',
                model=SpeechModel.TTS_1,
                voice=SpeechVoice.ALLOY,
                prompt='Speak slowly.',
            )

        client.audio.speech.create.assert_not_awaited()

    async def test_wraps_openai_error(self) -> None:
        client = self._client()
        client.audio.speech.create.side_effect = OpenAIError('API failed')
        service = TextToSpeechService(client=client)

        with self.assertRaises(SpeechGenerationError):
            await service.synthesize(
                'Привет',
                model=SpeechModel.GPT_4O_MINI_TTS,
                voice=SpeechVoice.CORAL,
            )


if __name__ == '__main__':
    unittest.main()
