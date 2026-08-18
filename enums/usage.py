from enum import StrEnum


class AIRequestInitiator(StrEnum):
    SYSTEM = 'system'
    USER = 'user'


class AIRequestScenario(StrEnum):
    WORD_REVIEW = 'word_review'
    WORD_ANSWER_CHECK = 'word_answer_check'
