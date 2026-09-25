import { computed, onUnmounted, ref, watch } from 'vue';
import { fetchLearnWord, sendPracticeAnswer, sendWordToManualReview } from '@/features/practice/api/practiceApi';
import { ApiError, getApiErrorMessage } from '@/shared/api/client';
import { EmptyIntervalRepetitionQueueError, useRepeatSession } from '@/features/practice/composables/useRepeatSession';
import { restoreLearnSessionWord, restoreRepeatSessionState, saveLearnSessionWord, saveRepeatSessionState } from '@/features/practice/practiceStorage';
import { useAudioRecorder } from '@/shared/audio/useAudioRecorder';
import { APP_LIMITS } from '@/shared/limits';
import type { DisplayDirection, PracticeMode, PracticeState, VoiceAnswerDialogState } from '@/shared/practice';

function createPracticeState(displayDirection: DisplayDirection): PracticeState {
  return {
    word: null,
    displayDirection,
    showAnswer: false,
    answerSubmitted: false,
    answerText: '',
    answerStatus: null,
    answerSkipped: false,
    answerTypo: null,
    submittedAnswer: '',
    correctAnswers: [],
    answerComment: null,
    recordedAudio: null,
  };
}


export function usePracticeSession(mode: () => PracticeMode, options?: { autoStartRepeat?: boolean }) {
  const selectedMode = computed(mode);
  const wordPracticeLimits = APP_LIMITS.wordPractice;
  const isLoading = ref(false);
  const isSendingAnswer = ref(false);
  const manualReviewLoadingWordId = ref<number | null>(null);
  const manuallyReviewedWordIds = ref<Set<number>>(new Set());
  const requestError = ref<string | null>(null);
  const answerError = ref<string | null>(null);
  const errorMessage = ref<string | null>(null);
  // Временный диагностический отчёт для ошибок голосового ответа.
  const answerDebugReport = ref<string | null>(null);
  const repeatState = ref<PracticeState>(createPracticeState('en-ru'));
  const learnState = ref<PracticeState>(createPracticeState('en-ru'));
  const showLearnStartDialog = ref(false);
  const showRepeatStartDialog = ref(false);
  const voiceAnswerDialogState = ref<VoiceAnswerDialogState>('hidden');
  const repeatSession = useRepeatSession(mode);

  let wordRequestSequence = 0;
  let isUnmounted = false;
  let answerRequestSequence = 0;
  let activeAnswerRequestId: number | null = null;
  let voiceAnswerTimeout: ReturnType<typeof setTimeout> | null = null;


  const recorder = useAudioRecorder(wordPracticeLimits.recording);
  const { isRecording, isStartingRecording, recordingAnalyser, stopRecording } = recorder;
  const currentState = computed(() => (selectedMode.value === 'learn' ? learnState.value : repeatState.value));
  const currentWord = computed(() => currentState.value.word);


  const storedLearn = restoreLearnSessionWord();
  if (storedLearn) {
    Object.assign(learnState.value, storedLearn, { answerSubmitted: true });
  }
  repeatState.value = restoreRepeatSessionState() ?? repeatState.value;

  watch(selectedMode, (nextMode) => {
    wordRequestSequence += 1;
    isLoading.value = false;
    invalidateActiveAnswerRequest();
    showLearnStartDialog.value = nextMode === 'learn' && !learnState.value.word;
    showRepeatStartDialog.value = nextMode === 'repeat' && !repeatState.value.word;
    if (nextMode === 'repeat') void loadIntervalRepetitions();
  }, { flush: 'sync' });
  showLearnStartDialog.value = selectedMode.value === 'learn' && !learnState.value.word;
  showRepeatStartDialog.value = selectedMode.value === 'repeat' && !repeatState.value.word && !options?.autoStartRepeat;

  if (selectedMode.value === 'repeat' && !options?.autoStartRepeat) void loadIntervalRepetitions();
  watch(repeatState, (state) => saveRepeatSessionState(state), { deep: true });

  function getAnswerLanguage(displayDirection: DisplayDirection) {
    return displayDirection === 'en-ru' ? 'ru' : 'en';
  }


  function getWordNotFoundMessage() {
    return 'У нас сложности с поиском слова для вас, попробуйте позже';
  }

  function showError(message: string) {
    errorMessage.value = message;
  }

  function clearError() {
    errorMessage.value = null;
  }

  async function loadIntervalRepetitions() {
    try {
      await repeatSession.preloadIntervalRepetitions();
    } catch (error) {
      if (!(error instanceof ApiError && error.kind === 'aborted')) {
        console.error('Не удалось загрузить очередь повторений:', error);
      }
    }
  }

  async function startLearning() {
    showLearnStartDialog.value = false;
    await requestWord();
  }

  async function startRepeating() {
    showRepeatStartDialog.value = false;
    await requestWord();
  }

  async function sendCurrentWordToManualReview() {
    const wordId = currentWord.value?.id;
    if (wordId === null || wordId === undefined || manualReviewLoadingWordId.value !== null) {
      return;
    }

    clearError();
    manualReviewLoadingWordId.value = wordId;

    try {
      await sendWordToManualReview(wordId);
      manuallyReviewedWordIds.value = new Set(manuallyReviewedWordIds.value).add(wordId);
    } catch (error) {
      showError(getApiErrorMessage(error, 'Не удалось отправить слово на ручную проверку'));
    } finally {
      manualReviewLoadingWordId.value = null;
    }
  }

  async function requestWord(options?: { requireIntervalRepetitions?: boolean }) {
    if (isUnmounted) return;
    const requestId = ++wordRequestSequence;
    invalidateActiveAnswerRequest();
    const nextMode = selectedMode.value;
    clearError();
    requestError.value = null;
    isLoading.value = true;
    const nextDisplayDirection: DisplayDirection = 'en-ru';
    const targetState = nextMode === 'learn' ? learnState.value : repeatState.value;

    try {
      // Очередью повторений по-прежнему управляет useRepeatSession.
      const data = nextMode === 'repeat'
        ? await repeatSession.requestNextWord(options)
        : await fetchLearnWord();

      if (isUnmounted || requestId !== wordRequestSequence) return;
      targetState.word = data;
      targetState.displayDirection =
        nextMode === 'repeat' && targetState.word.answerLanguage !== null
          ? targetState.word.answerLanguage === 'ru'
            ? 'en-ru'
            : 'ru-en'
          : nextDisplayDirection;
      targetState.showAnswer = false;
      targetState.answerStatus = null;
      targetState.answerSkipped = false;
      targetState.answerTypo = null;
      targetState.submittedAnswer = '';
      targetState.correctAnswers = [];
      targetState.answerComment = null;
      targetState.answerText = '';
      targetState.recordedAudio = null;
      targetState.answerSubmitted = nextMode === 'learn';

      if (nextMode === 'learn') {
        saveLearnSessionWord(targetState.word, nextDisplayDirection);
      }
    } catch (error) {
      if (isUnmounted || requestId !== wordRequestSequence) return;
      if (error instanceof ApiError && error.kind === 'aborted') return;
      if (error instanceof EmptyIntervalRepetitionQueueError) {
        requestError.value = error.message;
      } else if (error instanceof ApiError && error.kind === 'http' && error.status === 404) {
        requestError.value = getWordNotFoundMessage();
      } else {
        requestError.value = getApiErrorMessage(error);
      }
      showError(requestError.value);
      console.error('Не удалось загрузить слово:', error);
    } finally {
      if (requestId === wordRequestSequence) isLoading.value = false;
    }
  }

  function clearVoiceAnswerTimeout() {
    if (voiceAnswerTimeout === null) {
      return;
    }

    clearTimeout(voiceAnswerTimeout);
    voiceAnswerTimeout = null;
  }

  function hideVoiceAnswerDialog() {
    clearVoiceAnswerTimeout();
    voiceAnswerDialogState.value = 'hidden';
    answerDebugReport.value = null;
  }

  function showVoiceAnswerChecking(requestId: number, debugPrefix: string) {
    clearVoiceAnswerTimeout();
    answerDebugReport.value = null;
    voiceAnswerDialogState.value = 'checking';
    voiceAnswerTimeout = setTimeout(() => {
      voiceAnswerTimeout = null;
      if (activeAnswerRequestId === requestId && voiceAnswerDialogState.value === 'checking') {
        answerDebugReport.value = `${debugPrefix} · timeout>${wordPracticeLimits.voiceAnswerTimeoutMs}ms`;
        voiceAnswerDialogState.value = 'error';
      }
    }, wordPracticeLimits.voiceAnswerTimeoutMs);
  }

  function showVoiceAnswerError(requestId: number, debugReport: string) {
    if (activeAnswerRequestId !== requestId) {
      return;
    }

    clearVoiceAnswerTimeout();
    answerDebugReport.value = debugReport;
    voiceAnswerDialogState.value = 'error';
  }

  function shortenDebugValue(value: string, maximumLength = 160) {
    const normalizedValue = value.replace(/\s+/g, ' ').trim();
    return normalizedValue.length > maximumLength
      ? `${normalizedValue.slice(0, maximumLength - 1)}…`
      : normalizedValue;
  }

  function invalidateActiveAnswerRequest() {
    answerRequestSequence += 1;
    activeAnswerRequestId = null;
    isSendingAnswer.value = false;
    hideVoiceAnswerDialog();
  }

  async function submitAnswer(
    targetState = currentState.value,
    options?: { skip?: boolean },
  ) {
    const wordId = targetState.word?.id;
    const textAnswer = targetState.answerText.trim();
    const recordedAudio = targetState.recordedAudio;
    const hasAudio = recordedAudio !== null;
    const skip = options?.skip === true;
    const targetAnswerLanguage = getAnswerLanguage(targetState.displayDirection);

    answerError.value = null;
    clearError();

    if (!wordId) {
      answerError.value = 'Нет id слова';
      showError(answerError.value);
      return;
    }

    if (!skip && !textAnswer && !hasAudio) {
      answerError.value = 'Введите ответ или запишите голос';
      showError(answerError.value);
      return;
    }

    const requestId = ++answerRequestSequence;
    const answerType = skip ? 'skip' : hasAudio ? 'audio' : 'text';
    const debugPrefix = [
      'POST /api/telegram-app/words/answer',
      `request=${requestId}`,
      `word_id=${wordId}`,
      `type=${answerType}`,
      `lang=${targetAnswerLanguage}`,
      ...(recordedAudio ? [`audio=${recordedAudio.size}B/${recordedAudio.type || 'unknown'}`] : []),
    ].join(' · ');
    const requestStartedAt = performance.now();
    activeAnswerRequestId = requestId;
    isSendingAnswer.value = true;

    if (hasAudio && !skip) {
      showVoiceAnswerChecking(requestId, debugPrefix);
    } else {
      hideVoiceAnswerDialog();
    }

    try {
      const data = await sendPracticeAnswer({
        wordId, answerLanguage: targetAnswerLanguage, textAnswer, recordedAudio, skip,
      });
      if (activeAnswerRequestId !== requestId) return;

      const fallbackCorrectAnswers =
        targetState.displayDirection === 'en-ru'
          ? targetState.word?.translations ?? []
          : targetState.word?.word
            ? [targetState.word.word]
            : [];
      Object.assign(targetState, data, {
        correctAnswers: data.correctAnswers.length ? data.correctAnswers : fallbackCorrectAnswers,
      });
      targetState.answerText = '';
      targetState.recordedAudio = null;
      targetState.showAnswer = true;
      targetState.answerSubmitted = true;
      hideVoiceAnswerDialog();
    } catch (error) {
      if (activeAnswerRequestId !== requestId) {
        console.log('Ошибка устаревшего запроса ответа:', { requestId, error });
        return;
      }

      answerError.value = getApiErrorMessage(error, 'Не удалось отправить ответ');
      if (hasAudio && !skip) {
        showVoiceAnswerError(
          requestId,
          `${debugPrefix} · ${error instanceof ApiError ? `${error.kind}/HTTP=${error.status ?? '—'}` : 'error'} · time=${Math.round(performance.now() - requestStartedAt)}ms · ${shortenDebugValue(answerError.value)}`,
        );
      } else {
        showError(answerError.value);
      }
      console.error('Не удалось отправить ответ:', error);
    } finally {
      if (activeAnswerRequestId === requestId) {
        activeAnswerRequestId = null;
        clearVoiceAnswerTimeout();
        isSendingAnswer.value = false;
      }
    }
  }

  async function submitCurrentAnswer() {
    await submitAnswer();
  }

  async function retryVoiceAnswer() {
    if (voiceAnswerDialogState.value !== 'error' || !currentState.value.recordedAudio) {
      return;
    }

    await submitAnswer(currentState.value);
  }

  async function skipTimedOutVoiceAnswer() {
    if (voiceAnswerDialogState.value !== 'error') {
      return;
    }

    const targetState = currentState.value;
    invalidateActiveAnswerRequest();
    targetState.answerText = '';
    targetState.recordedAudio = null;
    await requestWord();
  }

  async function handleNextButton() {
    const targetState = currentState.value;

    if (selectedMode.value !== 'learn' && targetState.word && !targetState.answerSubmitted) {
      await submitAnswer(targetState, { skip: true });
      return;
    }

    await requestWord();
  }


  async function startRecording() {
    if (isStartingRecording.value || isRecording.value) return;
    const targetState = currentState.value;
    answerError.value = null;
    clearError();
    targetState.recordedAudio = null;
    try {
      await recorder.startRecording(({ blob, reason }) => {
        targetState.recordedAudio = blob;
        if (reason !== 'manual' && blob.size > 0) void submitAnswer(targetState);
      });
    } catch (error) {
      answerError.value = error instanceof Error ? error.message : 'Не удалось включить микрофон';
      showError(answerError.value);
      console.error('Не удалось начать аудиозапись:', error);
    }
  }

  async function toggleRecording() {
    if (isRecording.value) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  onUnmounted(() => {
    isUnmounted = true;
    wordRequestSequence += 1;
    invalidateActiveAnswerRequest();
  });

  return {
    selectedMode, currentState, currentWord, isLoading, isSendingAnswer,
    manualReviewLoadingWordId, manuallyReviewedWordIds, errorMessage, clearError,
    showLearnStartDialog, showRepeatStartDialog, voiceAnswerDialogState, answerDebugReport,
    isRecording, isStartingRecording, recordingAnalyser,
    startLearning, startRepeating, requestWord, sendCurrentWordToManualReview,
    submitCurrentAnswer, retryVoiceAnswer, skipTimedOutVoiceAnswer, handleNextButton,
    startRecording, stopRecording, toggleRecording,
  };
}
