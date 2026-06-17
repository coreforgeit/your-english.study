from enum import StrEnum


class WordCountry(StrEnum):
    US = 'us'
    GB = 'gb'
    BOTH = 'both'


class WordStatus(StrEnum):
    ALLOWED = 'allowed'
    FORBIDDEN = 'forbidden'
