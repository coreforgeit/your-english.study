import { ref } from 'vue';
import { z } from 'zod';

import { authorizedFetch, BACKEND_URL } from '@/shared/api/client';

const WORD_IDS_STORAGE_KEY = 'practice:interval-repetition-word-ids';
const REQUESTED_IN_SESSION_STORAGE_KEY = 'practice:interval-repetitions-requested';

const intervalRepetitionsResponseSchema = z.object({
  data: z.array(z.number().int().positive()),
});

function readStoredWordIds(): number[] {
  try {
    const storedValue = localStorage.getItem(WORD_IDS_STORAGE_KEY);
    if (!storedValue) {
      return [];
    }

    return intervalRepetitionsResponseSchema.shape.data.parse(JSON.parse(storedValue));
  } catch {
    try {
      localStorage.removeItem(WORD_IDS_STORAGE_KEY);
    } catch {
      // Ignore cleanup failures when browser storage is unavailable.
    }

    return [];
  }
}

function wasRequestedInCurrentSession(): boolean {
  try {
    return sessionStorage.getItem(REQUESTED_IN_SESSION_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function useIntervalRepetitionQueue() {
  const wordIds = ref<number[]>(readStoredWordIds());
  const hasRequested = ref(wasRequestedInCurrentSession());
  let loadPromise: Promise<void> | null = null;

  function saveWordIds() {
    try {
      localStorage.setItem(WORD_IDS_STORAGE_KEY, JSON.stringify(wordIds.value));
    } catch {
      // The queue remains available in memory if browser storage is unavailable.
    }
  }

  function replaceWordIds(nextWordIds: number[]) {
    wordIds.value = [...new Set(nextWordIds)];
    saveWordIds();
  }

  function markAsRequested() {
    hasRequested.value = true;

    try {
      sessionStorage.setItem(REQUESTED_IN_SESSION_STORAGE_KEY, 'true');
    } catch {
      // The request flag remains available in memory if browser storage is unavailable.
    }
  }

  async function load(force = false) {
    if (loadPromise) {
      return loadPromise;
    }

    if (!force && hasRequested.value) {
      return;
    }

    markAsRequested();
    replaceWordIds([]);

    loadPromise = (async () => {
      const response = await authorizedFetch(
        `${BACKEND_URL}/api/telegram-app/words/interval-repetitions`,
      );

      if (!response.ok) {
        throw new Error(
          `Не удалось загрузить слова для интервального повторения: ${response.status}`,
        );
      }

      const { data } = intervalRepetitionsResponseSchema.parse(await response.json());
      replaceWordIds(data);
    })();

    try {
      await loadPromise;
    } finally {
      loadPromise = null;
    }
  }

  async function loadOnce() {
    await load();
  }

  async function reload() {
    await load(true);
  }

  function getRandomWordId(): number | null {
    if (wordIds.value.length === 0) {
      return null;
    }

    const randomIndex = Math.floor(Math.random() * wordIds.value.length);
    return wordIds.value[randomIndex] ?? null;
  }

  function removeWordId(wordId: number) {
    const nextWordIds = wordIds.value.filter((storedWordId) => storedWordId !== wordId);
    if (nextWordIds.length === wordIds.value.length) {
      return;
    }

    wordIds.value = nextWordIds;
    saveWordIds();
  }

  return {
    getRandomWordId,
    loadOnce,
    reload,
    removeWordId,
  };
}
