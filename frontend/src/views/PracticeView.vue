<script setup lang="ts">
import { Mic, Send, X } from '@lucide/vue';
import { computed, ref } from 'vue';

import WordInfoBlock from '@/features/practice/components/WordInfoBlock.vue';
import { BACKEND_URL } from '@/shared/api/client';

type Level = 'ANY' | 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
type PracticeMode = 'learn' | 'repeat';
type PracticeDirection = 'ru-en' | 'en-ru' | 'random';
type DisplayDirection = Exclude<PracticeDirection, 'random'>;
type AnswerStatus = 'correct' | 'incorrect' | null;

type WordData = {
  id: number | null;
  word: string;
  pronunciation: string | null;
  translation: string;
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
  submittedAnswer: string;
  recordedAudio: Blob | null;
};

function createPracticeState(displayDirection: DisplayDirection): PracticeState {
  return {
    word: null,
    displayDirection,
    showAnswer: false,
    answerSubmitted: false,
    answerText: '',
    answerStatus: null,
    submittedAnswer: '',
    recordedAudio: null,
  };
}

const selectedLevel = ref<Level>('ANY');
const direction = ref<PracticeDirection>('en-ru');
const selectedMode = ref<PracticeMode>('repeat');
const isLoading = ref(false);
const isSendingAnswer = ref(false);
const isRecording = ref(false);
const requestError = ref<string | null>(null);
const answerError = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const mediaRecorder = ref<MediaRecorder | null>(null);
const audioChunks = ref<BlobPart[]>([]);
const recordingStream = ref<MediaStream | null>(null);
const repeatState = ref<PracticeState>(createPracticeState('en-ru'));
const learnState = ref<PracticeState>(createPracticeState('en-ru'));

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
  text: currentWord.value?.translation ?? '',
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
const isAnswerInputDisabled = computed(
  () =>
    !hasCurrentWord.value ||
    isLearnMode.value ||
    currentState.value.answerSubmitted ||
    isSendingAnswer.value ||
    isLoading.value,
);
const arePracticeSettingsDisabled = computed(() => false);
const areModeButtonsDisabled = computed(() => false);
const nextButtonText = computed(() => {
  if (isLoading.value) {
    return 'Загрузка...';
  }

  if (!hasCurrentWord.value || isLearnMode.value || currentState.value.answerSubmitted) {
    return 'Следующее';
  }

  return 'Пропустить';
});

function getRequestBody() {
  return {
    level: selectedLevel.value === 'ANY' ? null : selectedLevel.value,
  };
}

function resolveDisplayDirection(value: PracticeDirection): DisplayDirection {
  return value === 'random' ? (Math.random() > 0.5 ? 'ru-en' : 'en-ru') : value;
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
    partOfSpeech:
      'part_of_speech' in wordData && typeof wordData.part_of_speech === 'string' ? wordData.part_of_speech : null,
    audioUrl: 'audio_url' in wordData && typeof wordData.audio_url === 'string' ? wordData.audio_url : null,
    level: 'level' in wordData && typeof wordData.level === 'string' ? wordData.level : null,
  };
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

function chooseDisplayDirection(value: PracticeDirection) {
  direction.value = value;
}

function changeDisplayDirection(value: PracticeDirection) {
  chooseDisplayDirection(value);
}

function selectMode(mode: PracticeMode) {
  selectedMode.value = mode;
}

async function requestWord() {
  const wordModePath = selectedMode.value === 'learn' ? 'learn' : 'reapit';
  const url = `${BACKEND_URL}/api/telegram-app/words/${wordModePath}`;
  const body = getRequestBody();
  const requestDebug = {
    method: 'POST',
    url,
    body,
  };

  console.log('[practice-word:request]', requestDebug);
  clearError();
  requestError.value = null;
  isLoading.value = true;
  const nextMode = selectedMode.value;
  const nextDisplayDirection = resolveDisplayDirection(direction.value);
  const targetState = nextMode === 'learn' ? learnState.value : repeatState.value;

  try {
    const response = await fetch(url, {
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
      translation: 'Ответ без перевода',
      partOfSpeech: null,
      audioUrl: null,
      level: null,
    };
    targetState.displayDirection = nextDisplayDirection;
    targetState.showAnswer = false;
    targetState.answerStatus = null;
    targetState.submittedAnswer = '';
    targetState.answerText = '';
    targetState.recordedAudio = null;
    targetState.answerSubmitted = nextMode === 'learn';
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : 'Не удалось выполнить запрос';
    showError(requestError.value);
    console.error('[practice-word:error]', error);
  } finally {
    isLoading.value = false;
  }
}

function getAnswerResult(data: unknown): AnswerStatus {
  if (!data || typeof data !== 'object') {
    return null;
  }

  if ('is_correct' in data && typeof data.is_correct === 'boolean') {
    return data.is_correct ? 'correct' : 'incorrect';
  }

  if ('correct' in data && typeof data.correct === 'boolean') {
    return data.correct ? 'correct' : 'incorrect';
  }

  if ('data' in data && data.data && typeof data.data === 'object') {
    const responseData = data.data;

    if ('is_correct' in responseData && typeof responseData.is_correct === 'boolean') {
      return responseData.is_correct ? 'correct' : 'incorrect';
    }

    if ('correct' in responseData && typeof responseData.correct === 'boolean') {
      return responseData.correct ? 'correct' : 'incorrect';
    }
  }

  return null;
}

async function submitAnswer() {
  const url = `${BACKEND_URL}/api/telegram-app/words/answer`;
  const targetState = currentState.value;
  const wordId = targetState.word?.id;
  const textAnswer = targetState.answerText.trim();
  const hasAudio = targetState.recordedAudio !== null;

  answerError.value = null;
  clearError();

  if (!wordId) {
    answerError.value = 'Нет id слова';
    showError(answerError.value);
    return;
  }

  if (!textAnswer && !hasAudio) {
    answerError.value = 'Введите ответ или запишите голос';
    showError(answerError.value);
    return;
  }

  isSendingAnswer.value = true;

  try {
    const requestInit: RequestInit = {
      method: 'POST',
    };
    const requestDebug: Record<string, unknown> = {
      method: 'POST',
      url,
    };

    if (targetState.recordedAudio) {
      const formData = new FormData();

      formData.append('word_id', String(wordId));
      formData.append('answer_type', 'audio');
      formData.append('answer_language', answerRequestLanguage.value);
      formData.append('audio_file', targetState.recordedAudio, 'answer.webm');

      requestInit.body = formData;
      requestDebug.body = {
        word_id: wordId,
        answer_type: 'audio',
        answer_language: answerRequestLanguage.value,
        audio_file: {
          name: 'answer.webm',
          size: targetState.recordedAudio.size,
          type: targetState.recordedAudio.type,
        },
      };
    } else {
      const body = {
        word_id: wordId,
        answer_type: 'text',
        answer_language: answerRequestLanguage.value,
        answer: textAnswer,
      };

      requestInit.headers = {
        'Content-Type': 'application/json',
      };
      requestInit.body = JSON.stringify(body);
      requestDebug.body = body;
    }

    console.log('[practice-answer:request]', requestDebug);

    const response = await fetch(url, requestInit);
    const contentType = response.headers.get('content-type') ?? '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();

    console.log('[practice-answer:response]', data);

    if (!response.ok) {
      answerError.value = getBackendErrorMessage(data, `Backend вернул ${response.status}`);
      showError(answerError.value);
      return;
    }

    targetState.answerStatus = getAnswerResult(data);
    targetState.submittedAnswer = targetState.recordedAudio ? 'Голосовой ответ' : textAnswer;
    targetState.answerText = '';
    targetState.recordedAudio = null;
    targetState.showAnswer = true;
    targetState.answerSubmitted = true;
  } catch (error) {
    answerError.value = error instanceof Error ? error.message : 'Не удалось отправить ответ';
    showError(answerError.value);
    console.error('[practice-answer:error]', error);
  } finally {
    isSendingAnswer.value = false;
  }
}

function stopRecording() {
  mediaRecorder.value?.stop();
  recordingStream.value?.getTracks().forEach((track) => track.stop());
  mediaRecorder.value = null;
  recordingStream.value = null;
  isRecording.value = false;
}

async function startRecording() {
  const targetState = currentState.value;

  answerError.value = null;
  clearError();
  targetState.recordedAudio = null;
  audioChunks.value = [];

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : undefined;
    const recorder = new MediaRecorder(stream, options);

    recordingStream.value = stream;
    mediaRecorder.value = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
      }
    };
    recorder.onstop = () => {
      targetState.recordedAudio = new Blob(audioChunks.value, { type: recorder.mimeType || 'audio/webm' });
      console.log('[practice-answer:voice]', {
        size: targetState.recordedAudio.size,
        type: targetState.recordedAudio.type,
      });
    };
    recorder.start();
    isRecording.value = true;
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
</script>

<template>
  <section class="practice-layout" aria-label="Тренировка слов">
    <div v-if="errorMessage" class="error-toast" role="alert">
      <span>{{ errorMessage }}</span>
      <button type="button" class="error-toast-close" aria-label="Закрыть ошибку" @click="clearError">
        <X :size="18" />
      </button>
    </div>

    <header class="practice-top">
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
      <section v-if="hasCurrentWord" class="learn-word-card">
        <p class="word-language">ENG</p>
        <WordInfoBlock :item="englishBlock" tone="english" />
        <div class="learn-translation">
          <span>RU</span>
          <strong>{{ currentWord?.translation }}</strong>
        </div>
      </section>
    </main>

    <main v-else class="word-stage" :class="{ 'word-stage-empty': !hasCurrentWord }" aria-live="polite">
      <section class="word-stage-half word-stage-prompt">
        <template v-if="hasCurrentWord">
          <p class="word-language">{{ promptLanguage }}</p>
          <WordInfoBlock :item="promptBlock" :tone="promptTone" />
        </template>
      </section>

      <section class="word-stage-half word-stage-answer">
        <template v-if="hasCurrentWord">
          <p class="word-language">{{ answerLanguage }}</p>
          <template v-if="currentState.showAnswer">
            <div class="answer-result">
              <span class="submitted-answer">
                {{ currentState.submittedAnswer }}
              </span>
              <WordInfoBlock :item="answerBlock" :tone="answerTone" :result="currentState.answerStatus" />
            </div>
          </template>
        </template>
      </section>
    </main>

    <footer class="practice-actions">
      <form v-if="!isLearnMode" class="answer-input-panel" @submit.prevent="submitAnswer">
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
          :disabled="isAnswerInputDisabled"
          aria-label="Записать голосом"
          @click="toggleRecording"
        >
          <Mic :size="20" />
        </button>
      </form>

      <div class="word-actions">
        <button type="button" class="next-button" :disabled="isLoading" @click="requestWord">
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

      <div class="primary-actions">
        <button
          type="button"
          class="action-button action-repeat"
          :class="{ active: selectedMode === 'repeat' }"
          :disabled="areModeButtonsDisabled"
          @click="selectMode('repeat')"
        >
          Повторять
        </button>
        <button
          type="button"
          class="action-button action-new"
          :class="{ active: selectedMode === 'learn' }"
          :disabled="areModeButtonsDisabled"
          @click="selectMode('learn')"
        >
          Учить новое
        </button>
      </div>
    </footer>
  </section>
</template>
