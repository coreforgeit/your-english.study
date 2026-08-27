from pydantic import BaseModel, ConfigDict, Field

from enums import NotificationType, RedisChannel


NOTIFICATION_TEXTS: dict[NotificationType, str] = {
    NotificationType.FIVE_NEW_WORDS_TODAY: (
        'Уже 5 новых слов, отлично! Мы рекомендуем изучать не больше '
        '10 слов в день.'
    ),
    NotificationType.TEN_NEW_WORDS_TODAY: (
        'Ты узнал уже 10 новых слов, пора перейти к повторению.'
    ),
    NotificationType.WORD_STATUS_CHANGED: (
        'Статус слова «{word}» изменён: {status}.'
    ),
    NotificationType.WORD_LEARNED: 'Слово «{word}» выучено.',
}


class UserNotification(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: NotificationType
    text: str = Field(min_length=1, max_length=500)


def build_notification(
    notification_type: NotificationType,
    **context: str,
) -> UserNotification:
    return UserNotification(
        type=notification_type,
        text=NOTIFICATION_TEXTS[notification_type].format(**context),
    )


def user_notifications_channel(user_id: int) -> str:
    return f'{RedisChannel.USER_NOTIFICATIONS}:{user_id}'
