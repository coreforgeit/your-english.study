from enum import StrEnum


class WordCountry(StrEnum):
    US = 'us'
    GB = 'gb'
    BOTH = 'both'


class WordStatus(StrEnum):
    ALLOWED = 'allowed'
    CHECKING = 'checking'
    FORBIDDEN = 'forbidden'


class WordSource(StrEnum):
    BASE = 'base'
    GPT = 'gpt'
    ADMIN = 'admin'
    USER = 'user'


class LearnedWordStatus(StrEnum):
    NEW = 'new'
    LEARNED = 'learned'


class AnswerType(StrEnum):
    TEXT = 'text'
    AUDIO = 'audio'


class AnswerLanguage(StrEnum):
    EN = 'en'
    RU = 'ru'


class VocabularyAnswerVerdict(StrEnum):
    INCORRECT = 'incorrect'
    CORRECT = 'correct'
    CORRECT_WITH_MINOR_ISSUE = 'correct_with_minor_issue'
