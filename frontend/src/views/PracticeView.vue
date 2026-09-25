<script setup lang="ts">
import { Mic, Send } from '@lucide/vue';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { buildAnswerParts } from '@/features/practice/answerFormatting';
import AudioWaveform from '@/features/practice/components/AudioWaveform.vue';
import WordCard from '@/features/practice/components/WordCard.vue';
import PracticeStartDialog from '@/features/practice/components/PracticeStartDialog.vue';
import VoiceAnswerDialog from '@/features/practice/components/VoiceAnswerDialog.vue';
import { usePracticeSession } from '@/features/practice/composables/usePracticeSession';
import { APP_LAUNCH_AUTO_START_VALUE, AppLaunchQuery } from '@/shared/navigation/appLaunch';
import type { PracticeMode, WordInfo } from '@/shared/practice';

const props = defineProps<{ mode: PracticeMode }>();
const route = useRoute();
const router = useRouter();
const shouldAutoStartRepeat =
  props.mode === 'repeat' &&
  route.query[AppLaunchQuery.AUTO_START] === APP_LAUNCH_AUTO_START_VALUE;

const session = usePracticeSession(() => props.mode, { autoStartRepeat: shouldAutoStartRepeat });
const {
  selectedMode, currentState, currentWord, isLoading, isSendingAnswer,
  manualReviewLoadingWordId, manuallyReviewedWordIds, errorMessage, clearError,
  showLearnStartDialog, showRepeatStartDialog, voiceAnswerDialogState, answerDebugReport,
  isRecording, isStartingRecording, recordingAnalyser,
  startLearning, startRepeating, requestWord, sendCurrentWordToManualReview,
  submitCurrentAnswer, retryVoiceAnswer, skipTimedOutVoiceAnswer, handleNextButton,
  toggleRecording,
} = session;

async function startReminderRepetition() {
  await router.replace({ name: 'repeat' });
  await requestWord({ requireIntervalRepetitions: true });
}
if (shouldAutoStartRepeat) void startReminderRepetition();

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
const promptTone = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'english' : 'russian'));
const answerTone = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'russian' : 'english'));
const promptLanguage = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'ENG' : 'RU'));
const answerLanguage = computed(() => (currentState.value.displayDirection === 'en-ru' ? 'RU' : 'ENG'));
const isLearnMode = computed(() => selectedMode.value === 'learn');
const hasCurrentWord = computed(() => currentWord.value !== null);
const isMicrophoneDisabled = computed(
  () =>
    !hasCurrentWord.value ||
    isLearnMode.value ||
    currentState.value.answerSubmitted ||
    isStartingRecording.value ||
    isSendingAnswer.value ||
    isLoading.value,
);
const isAnswerInputDisabled = computed(() => isMicrophoneDisabled.value || isRecording.value);
const isManualReviewSending = computed(
  () =>
    currentWord.value?.id !== null &&
    currentWord.value?.id !== undefined &&
    manualReviewLoadingWordId.value === currentWord.value.id,
);
const isCurrentWordManuallyReviewed = computed(
  () =>
    currentWord.value?.id !== null &&
    currentWord.value?.id !== undefined &&
    manuallyReviewedWordIds.value.has(currentWord.value.id),
);
const isManualReviewDisabled = computed(
  () =>
    currentWord.value?.id === null ||
    currentWord.value?.id === undefined ||
    manualReviewLoadingWordId.value !== null ||
    isCurrentWordManuallyReviewed.value,
);
const manualReviewButtonText = computed(() => {
  if (isManualReviewSending.value) {
    return 'Отправляю…';
  }

  if (isCurrentWordManuallyReviewed.value) {
    return 'Отправлено на проверку';
  }

  return 'Тех: проверить слово';
});
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
const displayedCorrectAnswers = computed(() => {
  if (currentState.value.correctAnswers.length > 0) {
    return currentState.value.correctAnswers;
  }

  const word = currentState.value.word;
  if (!word) {
    return [];
  }

  return currentState.value.displayDirection === 'en-ru' ? word.translations : [word.word];
});
const correctAnswerPartLines = computed(() =>
  displayedCorrectAnswers.value.map((answer, index) =>
    buildAnswerParts(answer, index === 0 ? currentState.value.answerTypo : null, `correct-${index}`),
  ),
);
</script>

<template>
  <section
    class="practice-layout"
    aria-label="Тренировка слов"
  >
    <PracticeStartDialog v-if="showLearnStartDialog" mode="learn" @start="startLearning" />
    <PracticeStartDialog v-if="showRepeatStartDialog" mode="repeat" @start="startRepeating" />
    <VoiceAnswerDialog
      :state="voiceAnswerDialogState"
      :debug-report="answerDebugReport"
      @retry="retryVoiceAnswer"
      @skip="skipTimedOutVoiceAnswer"
    />

    <div v-if="errorMessage" class="error-toast" role="alert">
      <span>{{ errorMessage }}</span>
      <button type="button" class="error-toast-close" aria-label="Закрыть ошибку" @click="clearError">
        Я понял
      </button>
    </div>

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
        :text-part-lines="currentState.showAnswer ? correctAnswerPartLines : []"
        :submitted-parts="currentState.showAnswer && !currentState.answerSkipped ? submittedAnswerParts : []"
        :pronunciation="
          currentState.showAnswer && answerTone === 'english' ? currentWord?.pronunciation : null
        "
        :part-of-speech="
          currentState.showAnswer && answerTone === 'english' ? currentWord?.partOfSpeech : null
        "
        :audio-url="currentState.showAnswer && answerTone === 'english' ? currentWord?.audioUrl : null"
        :comment="currentState.showAnswer ? currentState.answerComment : null"
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
          class="manual-review-button"
          :disabled="isManualReviewDisabled"
          @click="sendCurrentWordToManualReview"
        >
          {{ manualReviewButtonText }}
        </button>
        <button
          type="button"
          class="next-button"
          :disabled="isLoading || isSendingAnswer || isRecording || isStartingRecording || manualReviewLoadingWordId !== null"
          @click="handleNextButton"
        >
          {{ nextButtonText }}
        </button>
      </div>

    </footer>
  </section>
</template>
