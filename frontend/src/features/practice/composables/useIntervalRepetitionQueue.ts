import { ref } from 'vue';
import { z } from 'zod';

import { fetchIntervalRepetitionWordIds } from '@/features/practice/api/practiceApi';

const WORD_IDS_STORAGE_KEY = 'practice:interval-repetition-word-ids';
const REQUESTED_IN_SESSION_STORAGE_KEY = 'practice:interval-repetitions-requested';
const storedWordIdsSchema = z.array(z.number().int().positive());

function readStoredWordIds(): number[] {
  try {
    const storedValue = localStorage.getItem(WORD_IDS_STORAGE_KEY);
    return storedValue ? storedWordIdsSchema.parse(JSON.parse(storedValue)) : [];
  } catch {
    try {
      localStorage.removeItem(WORD_IDS_STORAGE_KEY);
    } catch {
      // Хранилище может быть недоступно внутри некоторых WebView.
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
      // Очередь продолжит работать в памяти до закрытия приложения.
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
      // Флаг останется доступен в памяти текущей вкладки.
    }
  }

  async function load(force = false) {
    if (loadPromise) {
      return loadPromise;
    }

    if (!force && hasRequested.value) {
      return;
    }

    loadPromise = (async () => {
      const nextWordIds = await fetchIntervalRepetitionWordIds();
      replaceWordIds(nextWordIds);
      markAsRequested();
    })();

    try {
      await loadPromise;
    } finally {
      loadPromise = null;
    }
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
    if (nextWordIds.length !== wordIds.value.length) {
      replaceWordIds(nextWordIds);
    }
  }

  return {
    getRandomWordId,
    loadOnce: () => load(),
    reload: () => load(true),
    removeWordId,
  };
}
