from enum import StrEnum


class TranscriptionModel(StrEnum):
    GPT_4O_TRANSCRIBE = 'gpt-4o-transcribe'
    GPT_4O_MINI_TRANSCRIBE = 'gpt-4o-mini-transcribe'
    WHISPER_1 = 'whisper-1'
