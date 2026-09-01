import type { NotificationMessage } from '@/shared/api/notifications';

export function buildRepetitionProgressNotification(
  remainingWords: number,
): NotificationMessage | null {
  if (!Number.isInteger(remainingWords) || remainingWords < 0 || remainingWords % 10 !== 0) {
    return null;
  }

  if (remainingWords === 0) {
    return {
      type: 'repetitions_completed',
      text: 'Успех на сегодня — повторения закончены!',
    };
  }

  return {
    type: 'repetition_words_remaining',
    text: `Осталось повторить слов: ${remainingWords}.`,
  };
}
