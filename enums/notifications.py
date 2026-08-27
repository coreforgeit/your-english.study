from enum import StrEnum, unique


@unique
class NotificationType(StrEnum):
    FIVE_NEW_WORDS_TODAY = 'five_new_words_today'
    TEN_NEW_WORDS_TODAY = 'ten_new_words_today'
    WORD_STATUS_CHANGED = 'word_status_changed'
    WORD_LEARNED = 'word_learned'
