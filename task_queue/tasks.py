from taskiq.kicker import AsyncKicker

from enums import WorkerTaskName
from task_queue.broker import broker


send_daily_word_learning_reminder = AsyncKicker(
    WorkerTaskName.DAILY_WORD_LEARNING_REMINDER.value,
    broker,
    {},
)
record_word_repetition = AsyncKicker(
    WorkerTaskName.RECORD_WORD_REPETITION.value,
    broker,
    {},
)
review_word = AsyncKicker(
    WorkerTaskName.REVIEW_WORD.value,
    broker,
    {},
)
save_text_model_usage = AsyncKicker(
    WorkerTaskName.SAVE_TEXT_MODEL_USAGE.value,
    broker,
    {},
)
