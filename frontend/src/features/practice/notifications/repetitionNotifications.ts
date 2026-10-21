import type { NotificationMessage } from '@/shared/api/notifications';

export function buildRepetitionProgressNotification(
  remainingWords: number,
): NotificationMessage | null {
  if (!Number.isInteger(remainingWords) || remainingWords <= 0 || remainingWords % 10 !== 0) {
    return null;
  }

  return {
    type: 'repetition_words_remaining',
    text: `Осталось повторить слов: ${remainingWords}.`,
  };
}
