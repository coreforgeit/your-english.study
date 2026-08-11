<script setup lang="ts">
import { Volume2 } from '@lucide/vue';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const AUDIO_UNAVAILABLE_MESSAGE = 'Аудиофайл недоступен';
const AUDIO_WARNING_DURATION_MS = 2000;

type WordInfo = {
  text: string;
  pronunciation?: string | null;
  partOfSpeech?: string | null;
  audioUrl?: string | null;
};

const props = defineProps<{
  item: WordInfo;
  tone: 'english' | 'russian';
  result?: 'correct' | 'incorrect' | null;
}>();

const wordMainElement = ref<HTMLElement | null>(null);
const wordTextElement = ref<HTMLElement | null>(null);
const wordScale = ref(1);
const wordWidth = ref('auto');
const isAudioUnavailable = ref(false);
const showAudioWarning = ref(false);
let resizeObserver: ResizeObserver | null = null;
let activeAudio: HTMLAudioElement | null = null;
let audioRequestId = 0;
let audioWarningTimeout: ReturnType<typeof setTimeout> | null = null;

function clearAudioWarningTimeout() {
  if (audioWarningTimeout === null) {
    return;
  }

  clearTimeout(audioWarningTimeout);
  audioWarningTimeout = null;
}

function hideAudioWarning() {
  clearAudioWarningTimeout();
  showAudioWarning.value = false;
}

function showUnavailableAudioWarning() {
  clearAudioWarningTimeout();
  showAudioWarning.value = true;
  audioWarningTimeout = setTimeout(() => {
    showAudioWarning.value = false;
    audioWarningTimeout = null;
  }, AUDIO_WARNING_DURATION_MS);
}

function stopActiveAudio() {
  audioRequestId += 1;
  activeAudio?.pause();
  activeAudio = null;
}

function resetAudioState() {
  stopActiveAudio();
  hideAudioWarning();
  isAudioUnavailable.value = false;
}

function fitWordToContainer() {
  const mainElement = wordMainElement.value;
  const textElement = wordTextElement.value;

  if (!mainElement || !textElement) {
    return;
  }

  wordScale.value = 1;
  wordWidth.value = 'auto';

  requestAnimationFrame(() => {
    const availableWidth = textElement.clientWidth;
    const fullWidth = textElement.scrollWidth;

    if (!availableWidth || !fullWidth || fullWidth <= availableWidth) {
      wordScale.value = 1;
      wordWidth.value = 'auto';
      return;
    }

    const nextScale = Math.max(0.42, availableWidth / fullWidth);

    wordScale.value = nextScale;
    wordWidth.value = `${fullWidth * nextScale}px`;
  });
}

function playAudio() {
  if (!props.item.audioUrl || isAudioUnavailable.value) {
    return;
  }

  stopActiveAudio();

  const audio = new Audio(props.item.audioUrl);
  const requestId = audioRequestId;
  let errorReported = false;
  activeAudio = audio;

  const reportAudioError = () => {
    if (errorReported || requestId !== audioRequestId) {
      return;
    }

    errorReported = true;
    activeAudio = null;
    isAudioUnavailable.value = true;
    showUnavailableAudioWarning();
  };

  audio.addEventListener('error', reportAudioError, { once: true });
  audio.addEventListener(
    'ended',
    () => {
      if (activeAudio === audio) {
        activeAudio = null;
      }
    },
    { once: true },
  );

  try {
    void audio.play().catch(reportAudioError);
  } catch {
    reportAudioError();
  }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => fitWordToContainer());

  if (wordMainElement.value) {
    resizeObserver.observe(wordMainElement.value);
  }

  void nextTick(fitWordToContainer);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  stopActiveAudio();
  clearAudioWarningTimeout();
});

watch(
  () => props.item.text,
  () => {
    void nextTick(fitWordToContainer);
  },
);

watch(() => props.item.audioUrl, resetAudioState);
</script>

<template>
  <article class="word-info" :class="[`word-info-${tone}`, result ? `word-info-${result}` : null]">
    <div ref="wordMainElement" class="word-info-main">
      <span class="word-info-text-box" :style="{ width: wordWidth }">
        <strong ref="wordTextElement" class="word-info-text" :style="{ '--word-scale': wordScale }">
          {{ item.text }}
        </strong>
      </span>
      <div v-if="item.audioUrl" class="audio-control">
        <button
          type="button"
          class="audio-button"
          :disabled="isAudioUnavailable"
          :aria-label="isAudioUnavailable ? AUDIO_UNAVAILABLE_MESSAGE : 'Воспроизвести произношение'"
          @click="playAudio"
        >
          <Volume2 :size="21" />
        </button>
        <div v-if="showAudioWarning" class="audio-unavailable-warning" role="alert">
          {{ AUDIO_UNAVAILABLE_MESSAGE }}
        </div>
      </div>
    </div>

    <div v-if="item.pronunciation || item.partOfSpeech" class="word-info-details">
      <span v-if="item.pronunciation" class="word-pronunciation">{{ item.pronunciation }}</span>
      <span v-if="item.partOfSpeech" class="word-part-of-speech">{{ item.partOfSpeech }}</span>
    </div>
  </article>
</template>
