from enum import StrEnum


class TranscriptionModel(StrEnum):
    GPT_4O_TRANSCRIBE = 'gpt-4o-transcribe'
    GPT_4O_MINI_TRANSCRIBE = 'gpt-4o-mini-transcribe'
    WHISPER_1 = 'whisper-1'


class TextModel(StrEnum):
    """Основные текстовые модели. Цены за 1 млн токенов на 20.07.2026."""

    # Максимальное качество для сложного анализа и профессиональных задач — $5 / $30.
    GPT_5_6_SOL = 'gpt-5.6-sol'
    # Баланс качества и стоимости для сложных прикладных задач — $2.50 / $15.
    GPT_5_6_TERRA = 'gpt-5.6-terra'
    # Массовые задачи, где важно сохранить качество новой линейки — $1 / $6.
    GPT_5_6_LUNA = 'gpt-5.6-luna'
    # Простая классификация и извлечение данных с reasoning — $0.20 / $1.25.
    GPT_5_4_NANO = 'gpt-5.4-nano'
    # Недорогие задачи по точному промпту со средним запасом качества — $0.25 / $2.
    GPT_5_MINI = 'gpt-5-mini'
    # Саммари и простая классификация с минимальной стоимостью — $0.05 / $0.40.
    GPT_5_NANO = 'gpt-5-nano'
    # Перевод и короткие структурированные задачи без reasoning — $0.15 / $0.60.
    GPT_4O_MINI = 'gpt-4o-mini'

    @property
    def supports_reasoning(self) -> bool:
        return self is not TextModel.GPT_4O_MINI
