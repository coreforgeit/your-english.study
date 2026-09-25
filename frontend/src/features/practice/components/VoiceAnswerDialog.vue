<script setup lang="ts">
import type { VoiceAnswerDialogState } from '@/shared/practice';

defineProps<{ state: VoiceAnswerDialogState; debugReport: string | null }>();
const emit = defineEmits<{ retry: []; skip: [] }>();
</script>

<template>
  <div v-if="state !== 'hidden'" class="answer-check-backdrop">
    <section
      class="answer-check-dialog"
      :role="state === 'error' ? 'alertdialog' : 'dialog'"
      aria-modal="true"
      aria-live="assertive"
      aria-labelledby="answer-check-title"
    >
      <div v-if="state === 'checking'" class="answer-check-spinner" aria-hidden="true" />
      <h2 id="answer-check-title">
        {{ state === 'checking' ? 'Проверяю…' : 'Произошла ошибка' }}
      </h2>

      <pre v-if="state === 'error' && debugReport" class="answer-check-debug">{{ debugReport }}</pre>

      <div v-if="state === 'error'" class="answer-check-actions">
        <button type="button" class="answer-check-button answer-check-retry" @click="emit('retry')">
          Отправить снова
        </button>
        <button type="button" class="answer-check-button answer-check-skip" @click="emit('skip')">
          Пропустить
        </button>
      </div>
    </section>
  </div>
</template>
