from enum import StrEnum, unique


@unique
class RedisKey(StrEnum):
    TELEGRAM_SESSION = 'telegram-session'

