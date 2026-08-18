import unittest

from task_queue.tasks import (
    record_word_repetition as record_word_repetition_message,
    review_word as review_word_message,
    save_text_model_usage as save_text_model_usage_message,
    send_daily_word_learning_reminder as reminder_message,
)
from worker.reminders.tasks import send_daily_word_learning_reminder
from worker.usage.tasks import save_text_model_usage
from worker.vocabulary.tasks import record_word_repetition, review_word


class WorkerTaskContractTest(unittest.TestCase):
    def test_rabbit_messages_match_registered_worker_tasks(self) -> None:
        task_pairs = (
            (reminder_message, send_daily_word_learning_reminder),
            (record_word_repetition_message, record_word_repetition),
            (review_word_message, review_word),
            (save_text_model_usage_message, save_text_model_usage),
        )

        for message, worker_task in task_pairs:
            with self.subTest(task_name=message.task_name):
                self.assertEqual(message.task_name, worker_task.task_name)
