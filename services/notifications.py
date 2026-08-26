from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from enums import LearnedWordStatus, RedisChannel


class UserNotification(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: Literal['word_status_changed'] = 'word_status_changed'
    word: str = Field(min_length=1, max_length=255)
    status: LearnedWordStatus


def user_notifications_channel(user_id: int) -> str:
    return f'{RedisChannel.USER_NOTIFICATIONS}:{user_id}'
