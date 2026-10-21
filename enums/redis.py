from enum import StrEnum, unique


@unique
class RedisKey(StrEnum):
    TELEGRAM_SESSION = 'telegram-session'
    REPETITION_GOAL = 'repetition-goal'


@unique
class RedisChannel(StrEnum):
    USER_NOTIFICATIONS = 'user-notifications'
