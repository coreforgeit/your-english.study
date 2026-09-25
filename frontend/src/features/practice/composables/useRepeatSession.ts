import { onUnmounted, watch } from 'vue';
import { fetchRepeatWord } from '@/features/practice/api/practiceApi';
import { useIntervalRepetitionQueue } from '@/features/practice/composables/useIntervalRepetitionQueue';
import { ApiError } from '@/shared/api/errors';
import { authenticatedSession } from '@/shared/auth/session';
import type { PracticeMode } from '@/shared/practice';

export class EmptyIntervalRepetitionQueueError extends Error {
  constructor() {
    super('Сейчас нет слов для интервального повторения');
    this.name = 'EmptyIntervalRepetitionQueueError';
  }
}

export function useRepeatSession(mode: () => PracticeMode) {
  const queue = useIntervalRepetitionQueue();
  let visit: ReturnType<typeof queue.beginVisit> | null = null;

  function closeVisit() {
    if (visit) queue.endVisit(visit);
    visit = null;
  }

  // Vue может переиспользовать PracticeView при переходах learn ↔ repeat.
  watch([mode, authenticatedSession], ([nextMode]) => {
    closeVisit();
    if (nextMode === 'repeat') visit = queue.beginVisit();
  }, { immediate: true, flush: 'sync' });
  onUnmounted(closeVisit);

  function currentVisit() {
    if (!visit) throw new ApiError('aborted', 'Страница повторения уже закрыта');
    queue.assertCurrent(visit);
    return visit;
  }

  async function preloadIntervalRepetitions() {
    await queue.loadOnce(currentVisit());
  }

  async function requestNextWord(options?: { requireIntervalRepetitions?: boolean }) {
    const targetVisit = currentVisit();
    try {
      await queue.loadOnce(targetVisit);
    } catch (error) {
      queue.assertCurrent(targetVisit);
      if (options?.requireIntervalRepetitions) throw error;
      // При ошибке загрузки обычное повторение может доверить выбор слова бэку.
      console.error('Не удалось загрузить очередь повторений:', error);
    }

    const wordId = queue.getRandomWordId(targetVisit);
    if (options?.requireIntervalRepetitions && wordId === null) {
      throw new EmptyIntervalRepetitionQueueError();
    }

    const wordData = await fetchRepeatWord(wordId);
    queue.assertCurrent(targetVisit);
    if (wordId !== null) queue.removeWordId(targetVisit, wordId);
    return wordData;
  }

  return { preloadIntervalRepetitions, requestNextWord };
}
