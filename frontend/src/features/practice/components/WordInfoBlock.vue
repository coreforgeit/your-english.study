<script setup lang="ts">
import { Volume2 } from '@lucide/vue';
import { onBeforeUnmount, ref, watch } from 'vue';

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

const isAudioUnavailable = ref(false);
const showAudioWarning = ref(false);
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

onBeforeUnmount(() => {
  stopActiveAudio();
  clearAudioWarningTimeout();
});

watch(() => props.item.audioUrl, resetAudioState);
</script>

<template>
  <article class="word-info" :class="[`word-info-${tone}`, result ? `word-info-${result}` : null]">
    <div class="word-info-main">
      <span class="word-info-text-box">
        <strong class="word-info-text">
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
