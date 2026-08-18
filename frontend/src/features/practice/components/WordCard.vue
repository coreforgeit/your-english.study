<script setup lang="ts">
import { Volume2 } from '@lucide/vue';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

type TextPart = {
  key: string;
  value: string;
  state: 'normal' | 'replace' | 'extra' | 'missing' | 'expected';
};

const AUDIO_UNAVAILABLE_MESSAGE = 'Аудиофайл недоступен';
const AUDIO_WARNING_DURATION_MS = 2000;
const MINIMUM_TEXT_SCALE = 0.5;
const TEXT_SCALE_STEP = 0.05;

const props = withDefaults(
  defineProps<{
    language?: string | null;
    level?: string | null;
    text?: string | null;
    textLines?: string[];
    textParts?: TextPart[];
    submittedParts?: TextPart[];
    pronunciation?: string | null;
    translation?: string | null;
    translationLanguage?: string | null;
    partOfSpeech?: string | null;
    audioUrl?: string | null;
    comment?: string | null;
    tone?: 'english' | 'russian' | 'neutral';
    result?: 'correct' | 'incorrect' | 'neutral' | null;
    skipped?: boolean;
  }>(),
  {
    language: null,
    level: null,
    text: null,
    textLines: () => [],
    textParts: () => [],
    submittedParts: () => [],
    pronunciation: null,
    translation: null,
    translationLanguage: null,
    partOfSpeech: null,
    audioUrl: null,
    comment: null,
    tone: 'neutral',
    result: null,
    skipped: false,
  },
);

const cardElement = ref<HTMLElement | null>(null);
const contentElement = ref<HTMLElement | null>(null);
const isAudioUnavailable = ref(false);
const showAudioWarning = ref(false);
let resizeObserver: ResizeObserver | null = null;
let fitFrame: number | null = null;
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
  if (!props.audioUrl || isAudioUnavailable.value) {
    return;
  }

  stopActiveAudio();
  const audio = new Audio(props.audioUrl);
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

function fitTextToCard() {
  if (fitFrame !== null) {
    cancelAnimationFrame(fitFrame);
  }

  fitFrame = requestAnimationFrame(() => {
    fitFrame = null;
    const card = cardElement.value;
    const content = contentElement.value;
    if (!card || !content) {
      return;
    }

    const textElements = [...content.querySelectorAll<HTMLElement>('[data-fit-text]')];
    for (const element of textElements) {
      element.style.removeProperty('font-size');
    }

    const baseFontSizes = textElements.map((element) => Number.parseFloat(getComputedStyle(element).fontSize));
    const cardStyles = getComputedStyle(card);
    const availableWidth =
      card.clientWidth - Number.parseFloat(cardStyles.paddingLeft) - Number.parseFloat(cardStyles.paddingRight);
    const availableHeight =
      card.clientHeight - Number.parseFloat(cardStyles.paddingTop) - Number.parseFloat(cardStyles.paddingBottom);

    const contentOverflows = () =>
      content.scrollWidth > availableWidth + 1 || content.scrollHeight > availableHeight + 1;

    let scale = 1;
    while (contentOverflows() && scale > MINIMUM_TEXT_SCALE) {
      scale = Math.max(MINIMUM_TEXT_SCALE, scale - TEXT_SCALE_STEP);
      textElements.forEach((element, index) => {
        element.style.fontSize = `${baseFontSizes[index] * scale}px`;
      });
    }
  });
}

onMounted(() => {
  resizeObserver = new ResizeObserver(fitTextToCard);
  if (cardElement.value) {
    resizeObserver.observe(cardElement.value);
  }
  void nextTick(fitTextToCard);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  if (fitFrame !== null) {
    cancelAnimationFrame(fitFrame);
  }
  stopActiveAudio();
  clearAudioWarningTimeout();
});

watch(
  () => [
    props.text,
    props.textLines,
    props.textParts,
    props.submittedParts,
    props.pronunciation,
    props.translation,
    props.partOfSpeech,
    props.comment,
    props.audioUrl,
  ],
  () => void nextTick(fitTextToCard),
  { deep: true },
);

watch(() => props.audioUrl, resetAudioState);
</script>

<template>
  <section
    ref="cardElement"
    class="word-card"
    :class="[
      `word-card-${tone}`,
      result ? `word-card-${result}` : null,
      { 'word-card-skipped': skipped },
    ]"
  >
    <p v-if="language" class="word-card-language">{{ language }}</p>
    <span v-if="level" class="word-card-level">{{ level }}</span>

    <div ref="contentElement" class="word-card-content">
      <p v-if="submittedParts.length" class="word-card-submitted" data-fit-text>
        <span
          v-for="part in submittedParts"
          :key="part.key"
          class="word-card-char"
          :class="`word-card-char-${part.state}`"
        >
          {{ part.value }}
        </span>
      </p>

      <div v-if="text || textLines.length || textParts.length" class="word-card-primary-row">
        <div class="word-card-primary-content">
          <strong class="word-card-text" data-fit-text>
            <template v-if="textLines.length">
              <span v-for="(line, index) in textLines" :key="`${line}-${index}`" class="word-card-text-line">
                {{ line }}
              </span>
            </template>
            <template v-else-if="textParts.length">
              <span
                v-for="part in textParts"
                :key="part.key"
                class="word-card-char"
                :class="`word-card-char-${part.state}`"
              >
                {{ part.value }}
              </span>
            </template>
            <template v-else>{{ text }}</template>
          </strong>

          <div v-if="pronunciation || partOfSpeech" class="word-card-details">
            <span v-if="pronunciation" class="word-card-pronunciation">{{ pronunciation }}</span>
            <span v-if="partOfSpeech" class="word-card-part-of-speech">{{ partOfSpeech }}</span>
          </div>
        </div>

        <div v-if="audioUrl" class="word-card-audio-control">
          <button
            type="button"
            class="word-card-audio-button"
            :disabled="isAudioUnavailable"
            :aria-label="isAudioUnavailable ? AUDIO_UNAVAILABLE_MESSAGE : 'Воспроизвести произношение'"
            @click="playAudio"
          >
            <Volume2 :size="21" />
          </button>
          <div v-if="showAudioWarning" class="word-card-audio-warning" role="alert">
            {{ AUDIO_UNAVAILABLE_MESSAGE }}
          </div>
        </div>
      </div>

      <p v-if="comment" class="word-card-comment" data-fit-text>{{ comment }}</p>

      <div v-if="translation" class="word-card-translation">
        <span v-if="translationLanguage">{{ translationLanguage }}</span>
        <strong data-fit-text>{{ translation }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.word-card {
  position: relative;
  display: grid;
  place-items: center;
  align-content: center;
  min-width: 0;
  min-height: 150px;
  height: 100%;
  padding: 18px;
  overflow: hidden;
  box-sizing: border-box;
  text-align: center;
}

.word-card.word-card-learn {
  min-height: 100%;
  padding: 24px 18px;
}

.word-card-language {
  position: absolute;
  top: 12px;
  left: 14px;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.word-card-level {
  position: absolute;
  top: 10px;
  right: 12px;
  display: inline-grid;
  place-items: center;
  min-width: 38px;
  min-height: 26px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
  font-size: 12px;
  font-weight: 800;
}

.word-card-content {
  display: grid;
  justify-items: center;
  gap: 10px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.word-card-primary-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.word-card-primary-content {
  display: grid;
  flex: 0 1 auto;
  justify-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
}

.word-card-text,
.word-card-translation strong {
  width: 100%;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: normal;
}

.word-card-text {
  display: block;
  color: var(--color-text);
  font-size: clamp(24px, 10vw, 44px);
  font-weight: 800;
  line-height: 1.04;
}

.word-card-text-line {
  display: block;
}

.word-card-details {
  display: grid;
  justify-items: center;
  gap: 4px;
  font-size: 15px;
  line-height: 1.3;
}

.word-card-pronunciation {
  color: var(--color-primary-text);
  font-weight: 700;
}

.word-card-part-of-speech {
  color: var(--color-success-text);
  font-weight: 700;
}

.word-card-translation {
  display: grid;
  justify-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.word-card-translation > span {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.word-card-translation strong {
  color: var(--color-success-text);
  font-size: clamp(22px, 9vw, 40px);
  line-height: 1.08;
}

.word-card-comment {
  width: 100%;
  max-width: 100%;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
  white-space: normal;
}

.word-card-submitted {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  max-width: 100%;
  margin: 0;
  color: var(--color-text-muted);
  font-size: clamp(15px, 6vw, 24px);
  font-weight: 700;
  line-height: 1.08;
}

.word-card-correct .word-card-text {
  color: var(--color-success-text);
}

.word-card-incorrect .word-card-text {
  color: var(--color-danger-text);
}

.word-card-skipped .word-card-text {
  color: var(--color-primary-text);
}

.word-card-char {
  display: inline-grid;
  place-items: center;
  min-width: 0.42em;
  border-radius: 6px;
  white-space: pre;
}

.word-card-char-replace,
.word-card-char-extra {
  background: var(--color-danger-strong);
  color: var(--color-danger-text);
}

.word-card-char-missing {
  min-width: 0.72em;
  border: 1px dashed var(--color-danger-border);
  background: var(--color-danger-soft);
  color: var(--color-danger-text);
}

.word-card-char-expected {
  background: var(--color-success-soft);
  color: var(--color-success-text);
}

.word-card-audio-control {
  position: relative;
  flex: 0 0 42px;
}

.word-card-audio-button {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  padding: 0;
  border: 2px solid var(--color-transparent);
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
  cursor: pointer;
}

.word-card-audio-button:hover:not(:disabled),
.word-card-audio-button:focus-visible:not(:disabled) {
  border-color: var(--color-accent);
}

.word-card-audio-button:disabled {
  background: var(--color-neutral-soft);
  color: var(--color-text-muted);
  cursor: not-allowed;
  opacity: 0.65;
}

.word-card-audio-warning {
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: calc(100% + 8px);
  width: max-content;
  max-width: min(240px, calc(100vw - 32px));
  padding: 8px 10px;
  border: 1px solid var(--color-danger-border);
  border-radius: 9px;
  background: var(--color-surface);
  box-shadow: 0 8px 20px var(--color-shadow-soft);
  color: var(--color-danger-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
}

.word-card-audio-warning::before {
  position: absolute;
  top: 100%;
  right: 14px;
  width: 8px;
  height: 8px;
  border-right: 1px solid var(--color-danger-border);
  border-bottom: 1px solid var(--color-danger-border);
  background: var(--color-surface);
  content: '';
  transform: translateY(-4px) rotate(45deg);
}
</style>
