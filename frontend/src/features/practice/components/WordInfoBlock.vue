<script setup lang="ts">
import { Volume2 } from '@lucide/vue';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

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
let resizeObserver: ResizeObserver | null = null;

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
  if (!props.item.audioUrl) {
    return;
  }

  new Audio(props.item.audioUrl).play();
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
});

watch(
  () => props.item.text,
  () => {
    void nextTick(fitWordToContainer);
  },
);
</script>

<template>
  <article class="word-info" :class="[`word-info-${tone}`, result ? `word-info-${result}` : null]">
    <div ref="wordMainElement" class="word-info-main">
      <span class="word-info-text-box" :style="{ width: wordWidth }">
        <strong ref="wordTextElement" class="word-info-text" :style="{ '--word-scale': wordScale }">
          {{ item.text }}
        </strong>
      </span>
      <button
        v-if="item.audioUrl"
        type="button"
        class="audio-button"
        aria-label="Воспроизвести звук"
        @click="playAudio"
      >
        <Volume2 :size="21" />
      </button>
    </div>

    <div v-if="item.pronunciation || item.partOfSpeech" class="word-info-details">
      <span v-if="item.pronunciation" class="word-pronunciation">{{ item.pronunciation }}</span>
      <span v-if="item.partOfSpeech" class="word-part-of-speech">{{ item.partOfSpeech }}</span>
    </div>
  </article>
</template>
