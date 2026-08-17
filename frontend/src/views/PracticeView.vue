<script setup lang="ts">
import { Mic, Send } from '@lucide/vue';
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { z } from 'zod';

import AudioWaveform from '@/features/practice/components/AudioWaveform.vue';
import WordCard from '@/features/practice/components/WordCard.vue';
import { useIntervalRepetitionQueue } from '@/features/practice/useIntervalRepetitionQueue';
import { authorizedFetch, BACKEND_URL } from '@/shared/api/client';

type Level = 'ANY' | 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
type PracticeMode = 'learn' | 'repeat';
type PracticeDirection = 'ru-en' | 'en-ru' | 'random';
type DisplayDirection = Exclude<PracticeDirection, 'random'>;
type AnswerStatus = 'correct' | 'incorrect' | null;
type TypoType = 'replace' | 'missing' | 'extra';
type VoiceAnswerDialogState = 'hidden' | 'checking' | 'error';

type AnswerTypo = {
  index: number;
  type: TypoType;
  expected: string | null;
  actual: string | null;
};

type AnswerCharState = 'normal' | 'replace' | 'extra' | 'missing' | 'expected';

type AnswerCharPart = {
  key: string;
  value: string;
  state: AnswerCharState;
};

type WordData = {
  id: number | null;
  word: string;
  pronunciation: string | null;
  translation: string;
  translations: string[];
  partOfSpeech: string | null;
  audioUrl: string | null;
  level: string | null;
};

type WordInfo = {
  text: string;
  pronunciation?: string | null;
  partOfSpeech?: string | null;
  audioUrl?: string | null;
};

type PracticeState = {
  word: WordData | null;
  displayDirection: DisplayDirection;
  showAnswer: boolean;
  answerSubmitted: boolean;
  answerText: string;
  answerStatus: AnswerStatus;
  answerSkipped: boolean;
  answerTypo: AnswerTypo | null;
  submittedAnswer: string;
  correctAnswer: string;
  recordedAudio: Blob | null;
};

const wordDataStorageSchema = z.object({
  id: z.number().nullable(),
  word: z.string(),
  pronunciation: z.string().nullable(),
  translation: z.string(),
  translations: z.array(z.string()),
  partOfSpeech: z.string().nullable(),
  audioUrl: z.string().nullable(),
  level: z.string().nullable(),
});

const answerTypoStorageSchema = z.object({
  index: z.number(),
  type: z.enum(['replace', 'missing', 'extra']),
  expected: z.string().nullable(),
  actual: z.string().nullable(),
});

const learnSessionWordSchema = z.object({
  word: wordDataStorageSchema,
  displayDirection: z.enum(['ru-en', 'en-ru']),
});

const repeatSessionStateSchema = z.object({
  word: wordDataStorageSchema,
  displayDirection: z.enum(['ru-en', 'en-ru']),
  showAnswer: z.boolean(),
  answerSubmitted: z.boolean(),
  answerText: z.string(),
  answerStatus: z.enum(['correct', 'incorrect']).nullable(),
  answerSkipped: z.boolean().default(false),
  answerTypo: answerTypoStorageSchema.nullable(),
  submittedAnswer: z.string(),
  correctAnswer: z.string(),
});

const LEARN_SESSION_WORD_STORAGE_KEY = 'practice:last-learn-word';
const REPEAT_SESSION_STATE_STORAGE_KEY = 'practice:last-repeat-state';
const VOICE_ANSWER_TIMEOUT_MS = 10_000;

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
    correctAnswer: '',
    recordedAudio: null,
  };
}

const selectedLevel = ref<Level>('ANY');
const direction = ref<PracticeDirection>('en-ru');
const route = useRoute();
const selectedMode = ref<PracticeMode>(route.query.mode === 'learn' ? 'learn' : 'repeat');
const isLoading = ref(false);
const isSendingAnswer = ref(false);
const isRecording = ref(false);
const requestError = ref<string | null>(null);
const answerError = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const mediaRecorder = ref<MediaRecorder | null>(null);
const audioChunks = ref<BlobPart[]>([]);
const recordingStream = ref<MediaStream | null>(null);
const recordingAudioContext = ref<AudioContext | null>(null);
const recordingAnalyser = ref<AnalyserNode | null>(null);
const voiceDetectionFrame = ref<number | null>(null);
const repeatState = ref<PracticeState>(createPracticeState('en-ru'));
const learnState = ref<PracticeState>(createPracticeState('en-ru'));
const showLearnStartDialog = ref(false);
const showRepeatStartDialog = ref(false);
const voiceAnswerDialogState = ref<VoiceAnswerDialogState>('hidden');
const intervalRepetitionQueue = useIntervalRepetitionQueue();

let answerRequestSequence = 0;
let activeAnswerRequestId: number | null = null;
let voiceAnswerTimeout: ReturnType<typeof setTimeout> | null = null;

function restoreLearnSessionWord() {
  try {
    const storedValue = sessionStorage.getItem(LEARN_SESSION_WORD_STORAGE_KEY);
    if (!storedValue) {
      return false;
    }

    const storedWord = learnSessionWordSchema.parse(JSON.parse(storedValue));
    learnState.value.word = storedWord.word;
    learnState.value.displayDirection = storedWord.displayDirection;
    learnState.value.answerSubmitted = true;
    return true;
  } catch {
    sessionStorage.removeItem(LEARN_SESSION_WORD_STORAGE_KEY);
    return false;
  }
}

function saveLearnSessionWord(word: WordData, displayDirection: DisplayDirection) {
  try {
    sessionStorage.setItem(
      LEARN_SESSION_WORD_STORAGE_KEY,
      JSON.stringify({ word, displayDirection }),
    );
  } catch {
    // The current word remains available in memory if browser storage is unavailable.
  }
}

function restoreRepeatSessionState() {
  try {
    const storedValue = sessionStorage.getItem(REPEAT_SESSION_STATE_STORAGE_KEY);
    if (!storedValue) {
      return false;
    }

    const storedState = repeatSessionStateSchema.parse(JSON.parse(storedValue));
    repeatState.value = {
      ...storedState,
      recordedAudio: null,
    };
    return true;
  } catch {
    sessionStorage.removeItem(REPEAT_SESSION_STATE_STORAGE_KEY);
    return false;
  }
}

function saveRepeatSessionState(state: PracticeState) {
  if (!state.word) {
    return;
  }

  try {
    sessionStorage.setItem(
      REPEAT_SESSION_STATE_STORAGE_KEY,
      JSON.stringify({
        word: state.word,
        displayDirection: state.displayDirection,
        showAnswer: state.showAnswer,
        answerSubmitted: state.answerSubmitted,
        answerText: state.answerText,
        answerStatus: state.answerStatus,
        answerSkipped: state.answerSkipped,
        answerTypo: state.answerTypo,
        submittedAnswer: state.submittedAnswer,
        correctAnswer: state.correctAnswer,
      }),
    );
  } catch {
    // The current state remains available in memory if browser storage is unavailable.
  }
}

restoreLearnSessionWord();
restoreRepeatSessionState();
showLearnStartDialog.value = selectedMode.value === 'learn' && !learnState.value.word;
showRepeatStartDialog.value = selectedMode.value === 'repeat' && !repeatState.value.word;

if (selectedMode.value === 'repeat') {
  void loadIntervalRepetitions();
}

watch(
  () => route.query.mode,
  (mode) => {
    selectedMode.value = mode === 'learn' ? 'learn' : 'repeat';
    showLearnStartDialog.value = selectedMode.value === 'learn' && !learnState.value.word;
    showRepeatStartDialog.value = selectedMode.value === 'repeat' && !repeatState.value.word;

    if (selectedMode.value === 'repeat') {
      void loadIntervalRepetitions();
    }
  },
);

watch(
  repeatState,
  (state) => saveRepeatSessionState(state),
  { deep: true },
);

const voiceSilenceThreshold = 0.025;
const voiceSilenceMsToStop = 1200;
const voiceMinRecordingMs = 500;

let voiceDetected = false;
let silenceStartedAt: number | null = null;
let recordingStartedAt = 0;

const levelRows: Array<Array<{ value: Level; label: string; className: string; ariaLabel: string }>> = [
  [
    { value: 'ANY', label: 'A-C', className: 'level-any', ariaLabel: 'Любой уровень' },
    { value: 'C1', label: 'C1', className: 'level-c1', ariaLabel: 'Уровень C1' },
    { value: 'C2', label: 'C2', className: 'level-c2', ariaLabel: 'Уровень C2' },
  ],
  [
    { value: 'A1', label: 'A1', className: 'level-a1', ariaLabel: 'Уровень A1' },
    { value: 'A2', label: 'A2', className: 'level-a2', ariaLabel: 'Уровень A2' },
    { value: 'B1', label: 'B1', className: 'level-b1', ariaLabel: 'Уровень B1' },
    { value: 'B2', label: 'B2', className: 'level-b2', ariaLabel: 'Уровень B2' },
  ],
];
const directions: Array<{ value: PracticeDirection; label: string; className: string }> = [
  { value: 'ru-en', label: 'RU -> ENG', className: 'direction-ru-en' },
  { value: 'en-ru', label: 'ENG -> RU', className: 'direction-en-ru' },
  { value: 'random', label: 'Случайно', className: 'direction-random' },
];

const currentState = computed(() => (selectedMode.value === 'learn' ? learnState.value : repeatState.value));
const currentWord = computed(() => currentState.value.word);

const englishBlock = computed<WordInfo>(() => ({
  text: currentWord.value?.word ?? '',
  pronunciation: selectedMode.value === 'learn' ? currentWord.value?.pronunciation : null,
  partOfSpeech: currentWord.value?.partOfSpeech ?? null,
  audioUrl: currentWord.value?.audioUrl ?? null,
}));

const russianBlock = computed<WordInfo>(() => ({
  text: currentWord.value?.translations.join(', ') ?? '',
}));

const promptBlock = computed(() =>
  currentState.value.displayDirection === 'en-ru' ? englishBlock.value : russianBlock.value,
);
const answerBlock = computed(() =>
  currentState.value.displayDirection === 'en-ru' ? russianBlock.value : englishBlock.value,
);
const promptTone = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'english' : 'russian'));
const answerTone = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'russian' : 'english'));
const promptLanguage = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'ENG' : 'RU'));
const answerLanguage = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'RU' : 'ENG'));
const answerRequestLanguage = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'ru' : 'en'));
const isLearnMode = computed(() => selectedMode.value === 'learn');
const hasCurrentWord = computed(() => currentWord.value !== null);
const isMicrophoneDisabled = computed(
  () =>
    !hasCurrentWord.value ||
    isLearnMode.value ||
    currentState.value.answerSubmitted ||
    isSendingAnswer.value ||
    isLoading.value,
);
const isAnswerInputDisabled = computed(() => isMicrophoneDisabled.value || isRecording.value);
const arePracticeSettingsDisabled = computed(() => false);
const nextButtonText = computed(() => {
  if (isLoading.value) {
    return 'Загрузка...';
  }

  if (!hasCurrentWord.value || isLearnMode.value || currentState.value.answerSubmitted) {
    return 'Следующее';
  }

  return 'Пропустить';
});
const submittedAnswerParts = computed(() =>
  buildAnswerParts(currentState.value.submittedAnswer, currentState.value.answerTypo, 'submitted'),
);
const displayedCorrectAnswer = computed(() => currentState.value.correctAnswer || answerBlock.value.text);
const correctAnswerParts = computed(() => buildAnswerParts(displayedCorrectAnswer.value, currentState.value.answerTypo, 'correct'));
const skippedCorrectAnswers = computed(() =>
  displayedCorrectAnswer.value
    .split(/[,;/]+/)
    .map((answer) => answer.trim())
    .filter(Boolean),
);
function getRequestBody(mode: PracticeMode, intervalRepetitionWordId: number | null) {
  const body: { level: Level | null; word_id?: number } = {
    level: mode === 'learn' && selectedLevel.value !== 'ANY' ? selectedLevel.value : null,
  };

  if (mode === 'repeat' && intervalRepetitionWordId !== null) {
    body.word_id = intervalRepetitionWordId;
  }

  return body;
}

function resolveDisplayDirection(value: PracticeDirection): DisplayDirection {
  return value === 'random' ? (Math.random() > 0.5 ? 'ru-en' : 'en-ru') : value;
}

function getAnswerLanguage(displayDirection: DisplayDirection) {
  return displayDirection === 'en-ru' ? 'ru' : 'en';
}

function getResponseData(data: unknown) {
  if (data && typeof data === 'object' && 'data' in data && data.data && typeof data.data === 'object') {
    return data.data;
  }

  return data;
}

function isTypoType(value: unknown): value is TypoType {
  return value === 'replace' || value === 'missing' || value === 'extra';
}

function getAnswerTypo(data: unknown): AnswerTypo | null {
  const responseData = getResponseData(data);

  if (!responseData || typeof responseData !== 'object') {
    return null;
  }

  if (!('has_typo' in responseData) || responseData.has_typo !== true) {
    return null;
  }

  if (!('typo' in responseData) || !responseData.typo || typeof responseData.typo !== 'object') {
    return null;
  }

  const typo = responseData.typo;

  if (
    !('index' in typo) ||
    typeof typo.index !== 'number' ||
    !('type' in typo) ||
    !isTypoType(typo.type)
  ) {
    return null;
  }

  return {
    index: typo.index,
    type: typo.type,
    expected: 'expected' in typo && typeof typo.expected === 'string' ? typo.expected : null,
    actual: 'actual' in typo && typeof typo.actual === 'string' ? typo.actual : null,
  };
}

function buildAnswerParts(text: string, typo: AnswerTypo | null, line: 'submitted' | 'correct'): AnswerCharPart[] {
  const chars = Array.from(text);
  const parts = chars.map((value, index) => ({
    key: `${line}-${index}-${value}`,
    value,
    state: 'normal' as AnswerCharState,
  }));

  if (!typo) {
    return parts;
  }

  const index = Math.max(0, Math.min(typo.index, chars.length));

  if (typo.type === 'missing') {
    if (line === 'submitted') {
      parts.splice(index, 0, {
        key: `${line}-missing-${index}`,
        value: typo.expected ?? '',
        state: 'missing',
      });
    } else if (parts[index]) {
      parts[index].state = 'expected';
    }

    return parts;
  }

  if (typo.type === 'extra') {
    if (line === 'submitted' && parts[index]) {
      parts[index].state = 'extra';
    }

    return parts;
  }

  if (line === 'submitted' && parts[index]) {
    parts[index].state = 'replace';
  }

  if (line === 'correct' && parts[index]) {
    parts[index].state = 'expected';
  }

  return parts;
}

function normalizeWordData(data: unknown): WordData | null {
  if (!data || typeof data !== 'object' || !('data' in data) || !data.data || typeof data.data !== 'object') {
    return null;
  }

  const wordData = data.data;

  if (!('word' in wordData) || typeof wordData.word !== 'string') {
    return null;
  }

  return {
    id: 'id' in wordData && typeof wordData.id === 'number' ? wordData.id : null,
    word: wordData.word,
    pronunciation:
      'pronunciation' in wordData && typeof wordData.pronunciation === 'string' ? wordData.pronunciation : null,
    translation:
      'translation' in wordData && typeof wordData.translation === 'string' ? wordData.translation : 'Перевод не пришел',
    translations: getWordTranslations(wordData),
    partOfSpeech:
      'part_of_speech' in wordData && typeof wordData.part_of_speech === 'string' ? wordData.part_of_speech : null,
    audioUrl: 'audio_url' in wordData && typeof wordData.audio_url === 'string' ? wordData.audio_url : null,
    level: 'level' in wordData && typeof wordData.level === 'string' ? wordData.level : null,
  };
}

function getWordTranslations(wordData: object): string[] {
  if ('translations' in wordData && Array.isArray(wordData.translations)) {
    const translations = wordData.translations.filter(
      (translation): translation is string => typeof translation === 'string' && translation.trim().length > 0,
    );
    if (translations.length > 0) {
      return translations;
    }
  }

  if ('translation' in wordData && typeof wordData.translation === 'string') {
    return [wordData.translation];
  }

  return ['РџРµСЂРµРІРѕРґ РЅРµ РїСЂРёС€РµР»'];
}

function getBackendErrorMessage(data: unknown, fallback: string) {
  if (data && typeof data === 'object') {
    if ('detail' in data && typeof data.detail === 'string') {
      return data.detail;
    }

    if ('message' in data && typeof data.message === 'string') {
      return data.message;
    }

    if ('error' in data && typeof data.error === 'string') {
      return data.error;
    }
  }

  if (typeof data === 'string' && data.trim()) {
    return data;
  }

  return fallback;
}

function getWordNotFoundMessage() {
  if (selectedLevel.value === 'ANY') {
    return 'У нас сложности с поиском слова для вас, попробуйте позже';
  }

  return `Кажется, вы выучили все слова уровня ${selectedLevel.value}`;
}

function showError(message: string) {
  errorMessage.value = message;
}

function clearError() {
  errorMessage.value = null;
}

async function loadIntervalRepetitions() {
  try {
    await intervalRepetitionQueue.loadOnce();
  } catch (error) {
    console.error('[interval-repetitions:error]', error);
  }
}

function chooseDisplayDirection(value: PracticeDirection) {
  direction.value = value;
}

function changeDisplayDirection(value: PracticeDirection) {
  chooseDisplayDirection(value);
}

async function startLearning() {
  showLearnStartDialog.value = false;
  await requestWord();
}

async function startRepeating() {
  showRepeatStartDialog.value = false;
  await requestWord();
}

async function requestWord() {
  invalidateActiveAnswerRequest();
  const nextMode = selectedMode.value;
  const wordModePath = nextMode === 'learn' ? 'learn' : 'repeat';
  const url = `${BACKEND_URL}/api/telegram-app/words/${wordModePath}`;
  clearError();
  requestError.value = null;
  isLoading.value = true;
  const nextDisplayDirection = resolveDisplayDirection(direction.value);
  const targetState = nextMode === 'learn' ? learnState.value : repeatState.value;
  let intervalRepetitionWordId: number | null = null;

  try {
    if (nextMode === 'repeat') {
      await loadIntervalRepetitions();
      intervalRepetitionWordId = intervalRepetitionQueue.getRandomWordId();
    }

    const body = getRequestBody(nextMode, intervalRepetitionWordId);
    console.log('[practice-word:request]', {
      method: 'POST',
      url,
      body,
    });

    const response = await authorizedFetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const contentType = response.headers.get('content-type') ?? '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();

    console.log('[practice-word:response]', data);

    if (!response.ok) {
      requestError.value =
        response.status === 404
          ? getWordNotFoundMessage()
          : getBackendErrorMessage(data, `Backend вернул ${response.status}`);
      showError(requestError.value);
      return;
    }

    targetState.word = normalizeWordData(data) ?? {
      id: null,
      word: 'Ответ без слова',
      pronunciation: null,
      translations: ['РћС‚РІРµС‚ Р±РµР· РїРµСЂРµРІРѕРґР°'],
      translation: 'Ответ без перевода',
      partOfSpeech: null,
      audioUrl: null,
      level: null,
    };
    targetState.displayDirection = nextDisplayDirection;
    targetState.showAnswer = false;
    targetState.answerStatus = null;
    targetState.answerSkipped = false;
    targetState.answerTypo = null;
    targetState.submittedAnswer = '';
    targetState.correctAnswer = '';
    targetState.answerText = '';
    targetState.recordedAudio = null;
    targetState.answerSubmitted = nextMode === 'learn';

    if (nextMode === 'learn') {
      saveLearnSessionWord(targetState.word, nextDisplayDirection);
    } else if (intervalRepetitionWordId !== null) {
      intervalRepetitionQueue.removeWordId(intervalRepetitionWordId);
    }
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : 'Не удалось выполнить запрос';
    showError(requestError.value);
    console.error('[practice-word:error]', error);
  } finally {
    isLoading.value = false;
  }
}

function getAnswerResult(data: unknown): AnswerStatus {
  const responseData = getResponseData(data);

  if (!responseData || typeof responseData !== 'object') {
    return null;
  }

  if ('is_correct' in responseData && typeof responseData.is_correct === 'boolean') {
    return responseData.is_correct ? 'correct' : 'incorrect';
  }

  if ('correct' in responseData && typeof responseData.correct === 'boolean') {
    return responseData.correct ? 'correct' : 'incorrect';
  }

  return null;
}

function getAnswerSkipped(data: unknown) {
  const responseData = getResponseData(data);

  return Boolean(
    responseData &&
      typeof responseData === 'object' &&
      'skip' in responseData &&
      responseData.skip === true
  );
}

function getSubmittedAnswerFromResponse(data: unknown, fallback: string) {
  const responseData = getResponseData(data);

  if (responseData && typeof responseData === 'object' && 'answer' in responseData && typeof responseData.answer === 'string') {
    return responseData.answer;
  }

  return fallback;
}

function getCorrectAnswerFromResponse(data: unknown, fallback: string) {
  const responseData = getResponseData(data);

  if (
    responseData &&
    typeof responseData === 'object' &&
    'correct_answer' in responseData &&
    typeof responseData.correct_answer === 'string'
  ) {
    return responseData.correct_answer;
  }

  return fallback;
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
}

function showVoiceAnswerChecking(requestId: number) {
  clearVoiceAnswerTimeout();
  voiceAnswerDialogState.value = 'checking';
  voiceAnswerTimeout = setTimeout(() => {
    voiceAnswerTimeout = null;
    if (activeAnswerRequestId === requestId && voiceAnswerDialogState.value === 'checking') {
      voiceAnswerDialogState.value = 'error';
    }
  }, VOICE_ANSWER_TIMEOUT_MS);
}

function showVoiceAnswerError(requestId: number) {
  if (activeAnswerRequestId !== requestId) {
    return;
  }

  clearVoiceAnswerTimeout();
  voiceAnswerDialogState.value = 'error';
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
  const url = `${BACKEND_URL}/api/telegram-app/words/answer`;
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
  activeAnswerRequestId = requestId;
  isSendingAnswer.value = true;

  if (hasAudio && !skip) {
    showVoiceAnswerChecking(requestId);
  } else {
    hideVoiceAnswerDialog();
  }

  try {
    const requestInit: RequestInit = {
      method: 'POST',
    };
    const requestDebug: Record<string, unknown> = {
      method: 'POST',
      url,
    };

    if (skip) {
      const body = {
        word_id: wordId,
        answer_type: 'text',
        answer_language: targetAnswerLanguage,
        skip: true,
      };

      requestInit.headers = {
        'Content-Type': 'application/json',
      };
      requestInit.body = JSON.stringify(body);
      requestDebug.body = body;
    } else if (recordedAudio) {
      const formData = new FormData();

      formData.append('word_id', String(wordId));
      formData.append('answer_type', 'audio');
      formData.append('answer_language', targetAnswerLanguage);
      formData.append('skip', 'false');
      formData.append('audio_file', recordedAudio, 'answer.webm');

      requestInit.body = formData;
      requestDebug.body = {
        word_id: wordId,
        answer_type: 'audio',
        answer_language: targetAnswerLanguage,
        skip: false,
        audio_file: {
          name: 'answer.webm',
          size: recordedAudio.size,
          type: recordedAudio.type,
        },
      };
    } else {
      const body = {
        word_id: wordId,
        answer_type: 'text',
        answer_language: targetAnswerLanguage,
        answer: textAnswer,
        skip: false,
      };

      requestInit.headers = {
        'Content-Type': 'application/json',
      };
      requestInit.body = JSON.stringify(body);
      requestDebug.body = body;
    }

    console.log('[practice-answer:request]', requestDebug);

    const response = await authorizedFetch(url, requestInit);
    const contentType = response.headers.get('content-type') ?? '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();

    console.log('[practice-answer:response]', data);

    if (activeAnswerRequestId !== requestId) {
      console.log('[practice-answer:stale-response]', { requestId });
      return;
    }

    if (!response.ok) {
      answerError.value = getBackendErrorMessage(data, `Backend вернул ${response.status}`);
      if (hasAudio && !skip) {
        showVoiceAnswerError(requestId);
      } else {
        showError(answerError.value);
      }
      return;
    }

    targetState.answerStatus = getAnswerResult(data);
    targetState.answerSkipped = getAnswerSkipped(data);
    targetState.answerTypo = getAnswerTypo(data);
    targetState.submittedAnswer = getSubmittedAnswerFromResponse(data, skip ? '' : textAnswer);
    targetState.correctAnswer = getCorrectAnswerFromResponse(data, answerBlock.value.text);
    targetState.answerText = '';
    targetState.recordedAudio = null;
    targetState.showAnswer = true;
    targetState.answerSubmitted = true;
    hideVoiceAnswerDialog();
  } catch (error) {
    if (activeAnswerRequestId !== requestId) {
      console.log('[practice-answer:stale-error]', { requestId, error });
      return;
    }

    answerError.value = error instanceof Error ? error.message : 'Не удалось отправить ответ';
    if (hasAudio && !skip) {
      showVoiceAnswerError(requestId);
    } else {
      showError(answerError.value);
    }
    console.error('[practice-answer:error]', error);
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

  if (!isLearnMode.value && targetState.word && !targetState.answerSubmitted) {
    await submitAnswer(targetState, { skip: true });
    return;
  }

  await requestWord();
}

function setRecordingStreamEnabled(enabled: boolean) {
  recordingStream.value?.getAudioTracks().forEach((track) => {
    track.enabled = enabled;
  });
}

async function getRecordingStream() {
  if (recordingStream.value && recordingStream.value.active) {
    setRecordingStreamEnabled(true);
    return recordingStream.value;
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordingStream.value = stream;
  setRecordingStreamEnabled(true);

  return stream;
}

function releaseRecordingStream() {
  recordingStream.value?.getTracks().forEach((track) => track.stop());
  recordingStream.value = null;
}

function stopVoiceDetection() {
  if (voiceDetectionFrame.value !== null) {
    cancelAnimationFrame(voiceDetectionFrame.value);
    voiceDetectionFrame.value = null;
  }

  recordingAudioContext.value?.close().catch((error: unknown) => {
    console.error('[practice-answer:voice-context-error]', error);
  });
  recordingAudioContext.value = null;
  recordingAnalyser.value = null;
  voiceDetected = false;
  silenceStartedAt = null;
  recordingStartedAt = 0;
}

function getVoiceVolume(analyser: AnalyserNode) {
  const data = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(data);

  let sum = 0;
  for (const value of data) {
    const normalizedValue = (value - 128) / 128;
    sum += normalizedValue * normalizedValue;
  }

  return Math.sqrt(sum / data.length);
}

function startVoiceDetection(targetState: PracticeState) {
  const analyser = recordingAnalyser.value;

  if (!analyser) {
    return;
  }

  const checkVoice = () => {
    const volume = getVoiceVolume(analyser);
    const now = performance.now();

    if (volume >= voiceSilenceThreshold) {
      voiceDetected = true;
      silenceStartedAt = null;
    } else if (voiceDetected) {
      silenceStartedAt ??= now;

      if (now - silenceStartedAt >= voiceSilenceMsToStop && now - recordingStartedAt >= voiceMinRecordingMs) {
        stopRecording({ shouldSubmit: true, targetState });
        return;
      }
    }

    voiceDetectionFrame.value = requestAnimationFrame(checkVoice);
  };

  voiceDetectionFrame.value = requestAnimationFrame(checkVoice);
}

function stopRecording(options?: { shouldSubmit?: boolean; targetState?: PracticeState }) {
  const recorder = mediaRecorder.value;
  const shouldSubmit = options?.shouldSubmit === true;
  const targetState = options?.targetState ?? currentState.value;

  stopVoiceDetection();

  if (recorder && recorder.state !== 'inactive') {
    recorder.onstop = () => {
      targetState.recordedAudio = new Blob(audioChunks.value, { type: recorder.mimeType || 'audio/webm' });
      console.log('[practice-answer:voice]', {
        size: targetState.recordedAudio.size,
        type: targetState.recordedAudio.type,
        auto_submit: shouldSubmit,
      });

      if (shouldSubmit && targetState.recordedAudio.size > 0) {
        void submitAnswer(targetState);
      }
    };
    recorder.stop();
  }

  mediaRecorder.value = null;
  setRecordingStreamEnabled(false);
  isRecording.value = false;
}

async function startRecording() {
  const targetState = currentState.value;

  answerError.value = null;
  clearError();
  targetState.recordedAudio = null;
  audioChunks.value = [];

  try {
    const stream = await getRecordingStream();
    const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : undefined;
    const recorder = new MediaRecorder(stream, options);
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();

    analyser.fftSize = 1024;
    source.connect(analyser);

    mediaRecorder.value = recorder;
    recordingAudioContext.value = audioContext;
    recordingAnalyser.value = analyser;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
      }
    };
    recorder.start();
    voiceDetected = false;
    silenceStartedAt = null;
    recordingStartedAt = performance.now();
    isRecording.value = true;
    startVoiceDetection(targetState);
    console.log('[practice-answer:voice]', 'recording-started');
  } catch (error) {
    answerError.value = error instanceof Error ? error.message : 'Не удалось включить микрофон';
    showError(answerError.value);
    console.error('[practice-answer:voice-error]', error);
  }
}

async function toggleRecording() {
  if (isRecording.value) {
    stopRecording();
    return;
  }

  await startRecording();
}

onUnmounted(() => {
  invalidateActiveAnswerRequest();
  stopRecording();
  releaseRecordingStream();
});
</script>

<template>
  <section
    class="practice-layout"
    :class="{ 'practice-layout-without-header': !isLearnMode }"
    aria-label="Тренировка слов"
  >
    <div v-if="showLearnStartDialog" class="practice-start-backdrop">
      <section
        class="practice-start-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="learn-start-title"
        aria-describedby="learn-start-description"
      >
        <h2 id="learn-start-title">Начнём учить?</h2>
        <p id="learn-start-description">Новые слова будут сохранены в ваш словарь.</p>
        <button type="button" class="practice-start-button" @click="startLearning">
          Выучить новое слово
        </button>
      </section>
    </div>

    <div v-if="showRepeatStartDialog" class="practice-start-backdrop">
      <section
        class="practice-start-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="repeat-start-title"
        aria-describedby="repeat-start-description"
      >
        <h2 id="repeat-start-title">Пора повторить?</h2>
        <p id="repeat-start-description">Повторение помогает закрепить слова в памяти.</p>
        <button type="button" class="practice-start-button" @click="startRepeating">
          Начать повторение
        </button>
      </section>
    </div>

    <div v-if="voiceAnswerDialogState !== 'hidden'" class="answer-check-backdrop">
      <section
        class="answer-check-dialog"
        :role="voiceAnswerDialogState === 'error' ? 'alertdialog' : 'dialog'"
        aria-modal="true"
        aria-live="assertive"
        aria-labelledby="answer-check-title"
      >
        <div v-if="voiceAnswerDialogState === 'checking'" class="answer-check-spinner" aria-hidden="true" />
        <h2 id="answer-check-title">
          {{ voiceAnswerDialogState === 'checking' ? 'Проверяю…' : 'Произошла ошибка' }}
        </h2>

        <div v-if="voiceAnswerDialogState === 'error'" class="answer-check-actions">
          <button type="button" class="answer-check-button answer-check-retry" @click="retryVoiceAnswer">
            Отправить снова
          </button>
          <button type="button" class="answer-check-button answer-check-skip" @click="skipTimedOutVoiceAnswer">
            Пропустить
          </button>
        </div>
      </section>
    </div>

    <div v-if="errorMessage" class="error-toast" role="alert">
      <span>{{ errorMessage }}</span>
      <button type="button" class="error-toast-close" aria-label="Закрыть ошибку" @click="clearError">
        Я понял
      </button>
    </div>

    <header v-if="isLearnMode" class="practice-top">
      <div class="level-grid" aria-label="Выбор уровня">
        <div v-for="(row, rowIndex) in levelRows" :key="rowIndex" class="level-row">
          <button
            v-for="level in row"
            :key="level.value"
            type="button"
            class="level-button"
            :class="[level.className, { active: selectedLevel === level.value }]"
            :aria-label="level.ariaLabel"
            :disabled="arePracticeSettingsDisabled"
            @click="selectedLevel = level.value"
          >
            {{ level.label }}
          </button>
        </div>
      </div>
    </header>

    <main
      v-if="isLearnMode"
      class="word-stage word-stage-learn"
      :class="{ 'word-stage-empty': !hasCurrentWord }"
      aria-live="polite"
    >
      <WordCard
        v-if="hasCurrentWord"
        class="word-card-learn"
        language="ENG"
        :level="currentWord?.level"
        :text="englishBlock.text"
        :pronunciation="englishBlock.pronunciation"
        :part-of-speech="englishBlock.partOfSpeech"
        :audio-url="englishBlock.audioUrl"
        :translation="currentWord?.translations.join(', ')"
        translation-language="RU"
        tone="english"
      />
    </main>

    <main v-else class="word-stage" :class="{ 'word-stage-empty': !hasCurrentWord }" aria-live="polite">
      <WordCard
        class="word-stage-prompt"
        :language="hasCurrentWord ? promptLanguage : null"
        :level="hasCurrentWord ? currentWord?.level : null"
        :text="hasCurrentWord ? promptBlock.text : null"
        :part-of-speech="hasCurrentWord ? promptBlock.partOfSpeech : null"
        :audio-url="hasCurrentWord ? promptBlock.audioUrl : null"
        :tone="promptTone"
      />

      <WordCard
        class="word-stage-answer"
        :language="hasCurrentWord ? answerLanguage : null"
        :text="hasCurrentWord && currentState.showAnswer ? displayedCorrectAnswer : null"
        :text-lines="currentState.showAnswer && currentState.answerSkipped ? skippedCorrectAnswers : []"
        :text-parts="currentState.showAnswer && !currentState.answerSkipped ? correctAnswerParts : []"
        :submitted-parts="currentState.showAnswer && !currentState.answerSkipped ? submittedAnswerParts : []"
        :pronunciation="
          currentState.showAnswer && answerTone === 'english' ? currentWord?.pronunciation : null
        "
        :part-of-speech="
          currentState.showAnswer && answerTone === 'english' ? currentWord?.partOfSpeech : null
        "
        :audio-url="currentState.showAnswer && answerTone === 'english' ? currentWord?.audioUrl : null"
        :tone="answerTone"
        :result="currentState.answerStatus"
        :skipped="currentState.answerSkipped"
      />
    </main>

    <footer class="practice-actions">
      <form v-if="!isLearnMode" class="answer-input-panel" @submit.prevent="submitCurrentAnswer">
        <AudioWaveform
          v-if="isRecording && recordingAnalyser"
          :analyser="recordingAnalyser"
          :is-recording="isRecording"
        />
        <input
          v-model="currentState.answerText"
          class="answer-input"
          type="text"
          placeholder="Введите ответ"
          autocomplete="off"
          :disabled="isAnswerInputDisabled"
        />
        <button
          type="submit"
          class="answer-icon-button submit-answer-button"
          :disabled="isAnswerInputDisabled"
          aria-label="Отправить ответ"
        >
          <Send :size="20" />
        </button>
        <button
          type="button"
          class="answer-icon-button microphone-button"
          :class="{ active: isRecording }"
          :disabled="isMicrophoneDisabled"
          aria-label="Записать голосом"
          @click="toggleRecording"
        >
          <Mic :size="20" />
        </button>
      </form>

      <div class="word-actions">
        <button
          type="button"
          class="next-button"
          :disabled="isLoading || isSendingAnswer || isRecording"
          @click="handleNextButton"
        >
          {{ nextButtonText }}
        </button>
      </div>

      <div v-if="!isLearnMode" class="direction-row" aria-label="Направление тренировки">
        <button
          v-for="item in directions"
          :key="item.value"
          type="button"
          class="direction-button"
          :class="[item.className, { active: direction === item.value }]"
          :disabled="arePracticeSettingsDisabled"
          @click="changeDisplayDirection(item.value)"
        >
          {{ item.label }}
        </button>
      </div>

    </footer>
  </section>
</template>
