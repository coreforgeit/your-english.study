from enum import StrEnum


class SpeechVoice(StrEnum):
    """Встроенные голоса OpenAI Speech API."""

    ALLOY = 'alloy'
    ASH = 'ash'
    BALLAD = 'ballad'
    CORAL = 'coral'
    ECHO = 'echo'
    FABLE = 'fable'
    NOVA = 'nova'
    ONYX = 'onyx'
    SAGE = 'sage'
    SHIMMER = 'shimmer'
    VERSE = 'verse'
    MARIN = 'marin'
    CEDAR = 'cedar'


class SpeechModel(StrEnum):
    """Модели OpenAI для преобразования текста в речь."""

    GPT_4O_MINI_TTS = 'gpt-4o-mini-tts'
    TTS_1 = 'tts-1'
    TTS_1_HD = 'tts-1-hd'

    @property
    def supports_instructions(self) -> bool:
        return self is SpeechModel.GPT_4O_MINI_TTS

    def supports_voice(self, voice: SpeechVoice) -> bool:
        if self is SpeechModel.GPT_4O_MINI_TTS:
            return True

        return voice in {
            SpeechVoice.ALLOY,
            SpeechVoice.ASH,
            SpeechVoice.CORAL,
            SpeechVoice.ECHO,
            SpeechVoice.FABLE,
            SpeechVoice.NOVA,
            SpeechVoice.ONYX,
            SpeechVoice.SAGE,
            SpeechVoice.SHIMMER,
        }


class TranscriptionModel(StrEnum):
    GPT_4O_TRANSCRIBE = 'gpt-4o-transcribe'
    GPT_4O_MINI_TRANSCRIBE = 'gpt-4o-mini-transcribe'
    WHISPER_1 = 'whisper-1'


class TextModel(StrEnum):
    """Основные текстовые модели. Цены указаны за 1 млн токенов."""

    # Сложный анализ и профессиональные задачи — $5 вход / $30 выход.
    GPT_5_6_SOL = 'gpt-5.6-sol'
    # Баланс качества и стоимости — $2.50 вход / $15 выход.
    GPT_5_6_TERRA = 'gpt-5.6-terra'
    # Массовые задачи новой линейки — $1 вход / $6 выход.
    GPT_5_6_LUNA = 'gpt-5.6-luna'
    # Простая классификация и извлечение данных — $0.20 вход / $1.25 выход.
    GPT_5_4_NANO = 'gpt-5.4-nano'
    # Недорогие задачи по точному промпту — $0.25 вход / $2 выход.
    GPT_5_MINI = 'gpt-5-mini'
    # Саммари и простая классификация — $0.05 вход / $0.40 выход.
    GPT_5_NANO = 'gpt-5-nano'
    # Перевод и короткие структурированные задачи — $0.15 вход / $0.60 выход.
    GPT_4O_MINI = 'gpt-4o-mini'

    @property
    def supports_reasoning(self) -> bool:
        return self is not TextModel.GPT_4O_MINI
