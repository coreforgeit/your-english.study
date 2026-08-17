from enum import StrEnum


class ReminderKey(StrEnum):
    DAILY_WORD_LEARNING = 'daily_word_learning'

    def for_user(self, user_id: int) -> str:
        return f'{self.value}:{user_id}'
