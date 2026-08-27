from enum import StrEnum


class WorkerTaskName(StrEnum):
    CHECK_NEW_WORDS_MILESTONE_NOTIFICATION = (
        'worker.notifications.tasks:check_new_words_milestone_notification'
    )
    DAILY_WORD_LEARNING_REMINDER = (
        'worker.reminders.tasks:send_daily_word_learning_reminder'
    )
    RECORD_WORD_REPETITION = (
        'worker.analytics.vocabulary.tasks:record_word_repetition'
    )
    RECORD_LEARNED_WORD = 'worker.vocabulary.tasks:record_learned_word'
    REVIEW_WORD = 'worker.vocabulary.tasks:review_word'
    SAVE_TEXT_MODEL_USAGE = 'worker.usage.tasks:save_text_model_usage'
    SEND_WORD_STATUS_CHANGED_NOTIFICATION = (
        'worker.notifications.tasks:send_word_status_changed_notification'
    )
