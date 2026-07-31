from enum import StrEnum


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
