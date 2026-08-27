from taskiq.kicker import AsyncKicker

from enums import WorkerTaskName
from task_queue.broker import broker


send_daily_word_learning_reminder = AsyncKicker(
    WorkerTaskName.DAILY_WORD_LEARNING_REMINDER,
    broker,
    {},
)
record_word_repetition = AsyncKicker(
    WorkerTaskName.RECORD_WORD_REPETITION,
    broker,
    {},
)
record_learned_word = AsyncKicker(
    WorkerTaskName.RECORD_LEARNED_WORD,
    broker,
    {},
)
review_word = AsyncKicker(
    WorkerTaskName.REVIEW_WORD,
    broker,
    {},
)
save_text_model_usage = AsyncKicker(
    WorkerTaskName.SAVE_TEXT_MODEL_USAGE,
    broker,
    {},
)
