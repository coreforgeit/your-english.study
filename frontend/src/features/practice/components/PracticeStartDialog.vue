<script setup lang="ts">
import { computed } from 'vue';
import type { PracticeMode } from '@/shared/practice';

const props = defineProps<{ mode: PracticeMode }>();
const emit = defineEmits<{ start: [] }>();
const isLearn = computed(() => props.mode === 'learn');
</script>

<template>
  <div class="practice-start-backdrop">
    <section
      class="practice-start-dialog"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`${mode}-start-title`"
      :aria-describedby="`${mode}-start-description`"
    >
      <h2 :id="`${mode}-start-title`">{{ isLearn ? 'Начнём учить?' : 'Пора повторить?' }}</h2>
      <p :id="`${mode}-start-description`">
        {{ isLearn ? 'Новые слова будут сохранены в ваш словарь.' : 'Повторение помогает закрепить слова в памяти.' }}
      </p>
      <button type="button" class="practice-start-button" @click="emit('start')">
        {{ isLearn ? 'Выучить новое слово' : 'Начать повторение' }}
      </button>
    </section>
  </div>
</template>
