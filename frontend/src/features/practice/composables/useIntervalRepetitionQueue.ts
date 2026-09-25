import { fetchIntervalRepetitionWordIds } from '@/features/practice/api/practiceApi';
import { buildRepetitionProgressNotification } from '@/features/practice/notifications/repetitionNotifications';
import { ApiError } from '@/shared/api/errors';
import { authenticatedSession, type AuthenticatedSession } from '@/shared/auth/session';
import { useNotificationCenter } from '@/shared/notifications/useNotificationCenter';

type QueueVisit = {
  readonly owner: AuthenticatedSession | null;
  wordIds: number[];
  loaded: boolean;
  loadPromise: Promise<void> | null;
};

// Одна очередь на активную страницу повторения, без копий в браузерном хранилище.
let activeVisit: QueueVisit | null = null;

function removeLegacyCache() {
  try {
    localStorage.removeItem('practice:interval-repetition-word-ids');
  } catch {
    // Старый кэш никогда не читается, даже если браузер запрещает его удаление.
  }
  try {
    sessionStorage.removeItem('practice:interval-repetitions-requested');
  } catch {
    // Недоступность хранилища не мешает очереди работать в памяти.
  }
}

export function useIntervalRepetitionQueue() {
  const { addNotification } = useNotificationCenter();

  function beginVisit(): QueueVisit {
    removeLegacyCache();
    if (activeVisit) endVisit(activeVisit);
    activeVisit = {
      owner: authenticatedSession.value,
      wordIds: [],
      loaded: false,
      loadPromise: null,
    };
    return activeVisit;
  }

  function endVisit(visit: QueueVisit) {
    visit.wordIds = [];
    visit.loaded = false;
    if (activeVisit === visit) activeVisit = null;
  }

  function assertCurrent(visit: QueueVisit) {
    if (activeVisit !== visit || visit.owner !== authenticatedSession.value) {
      throw new ApiError('aborted', 'Страница повторения или пользователь уже изменились');
    }
  }

  async function loadOnce(visit: QueueVisit): Promise<void> {
    assertCurrent(visit);
    if (visit.loadPromise) return visit.loadPromise;
    if (visit.loaded) return;

    const promise = (async () => {
      const wordIds = await fetchIntervalRepetitionWordIds();
      assertCurrent(visit);
      visit.wordIds = [...new Set(wordIds)];
      visit.loaded = true;
    })();
    visit.loadPromise = promise;

    try {
      await promise;
    } finally {
      // У старого запроса свой объект визита: новую очередь он не изменит.
      visit.loadPromise = null;
    }
  }

  function getRandomWordId(visit: QueueVisit): number | null {
    assertCurrent(visit);
    if (!visit.wordIds.length) return null;
    return visit.wordIds[Math.floor(Math.random() * visit.wordIds.length)] ?? null;
  }

  function removeWordId(visit: QueueVisit, wordId: number) {
    assertCurrent(visit);
    const nextWordIds = visit.wordIds.filter((id) => id !== wordId);
    if (nextWordIds.length === visit.wordIds.length) return;
    visit.wordIds = nextWordIds;

    const notification = buildRepetitionProgressNotification(nextWordIds.length);
    if (notification) addNotification(notification);
  }

  return { beginVisit, endVisit, assertCurrent, loadOnce, getRandomWordId, removeWordId };
}
