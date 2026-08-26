from enum import StrEnum, unique


@unique
class RedisKey(StrEnum):
    TELEGRAM_SESSION = 'telegram-session'


@unique
class RedisChannel(StrEnum):
    USER_NOTIFICATIONS = 'user-notifications'
