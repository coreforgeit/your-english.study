import { fetchRepeatWord } from '@/features/practice/api/practiceApi';
import { useIntervalRepetitionQueue } from '@/features/practice/composables/useIntervalRepetitionQueue';

export class EmptyIntervalRepetitionQueueError extends Error {
  constructor() {
    super('Сейчас нет слов для интервального повторения');
    this.name = 'EmptyIntervalRepetitionQueueError';
  }
}

export function useRepeatSession() {
  const queue = useIntervalRepetitionQueue();

  async function preloadIntervalRepetitions() {
    await queue.loadOnce();
  }

  async function requestNextWord(options?: { reloadIntervalRepetitions?: boolean }) {
    const reloadIntervalRepetitions = options?.reloadIntervalRepetitions === true;

    if (reloadIntervalRepetitions) {
      await queue.reload();
    } else {
      try {
        await queue.loadOnce();
      } catch (error) {
        // Обычное повторение может продолжиться: тогда слово выберет бэкенд.
        console.error('[interval-repetitions:error]', error);
      }
    }

    const wordId = queue.getRandomWordId();
    if (reloadIntervalRepetitions && wordId === null) {
      throw new EmptyIntervalRepetitionQueueError();
    }

    // Если очередь пуста при обычном переходе, выбор слова оставляем бэкенду.
    const wordData = await fetchRepeatWord(wordId);
    if (wordId !== null) {
      queue.removeWordId(wordId);
    }

    return wordData;
  }

  return {
    preloadIntervalRepetitions,
    requestNextWord,
  };
}
