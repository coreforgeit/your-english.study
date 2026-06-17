<script setup lang="ts">
import { ref } from 'vue';

type Level = 'ANY' | 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
type PracticeDirection = 'ru-en' | 'en-ru' | 'random';

const selectedLevel = ref<Level>('ANY');
const direction = ref<PracticeDirection>('ru-en');

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
</script>

<template>
  <section class="practice-layout" aria-label="Тренировка слов">
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
            @click="selectedLevel = level.value"
          >
            {{ level.label }}
          </button>
        </div>
      </div>
    </header>

    <main class="word-stage" aria-live="polite">
      <p class="word-meta">
        {{ selectedLevel === 'ANY' ? 'Любой уровень' : `Уровень ${selectedLevel}` }}
      </p>
      <strong class="word">accurate</strong>
      <span class="word-hint">Нажми режим ниже, чтобы выбрать направление перевода</span>
    </main>

    <footer class="practice-actions">
      <div class="direction-row" aria-label="Направление тренировки">
        <button
          v-for="item in directions"
          :key="item.value"
          type="button"
          class="direction-button"
          :class="[item.className, { active: direction === item.value }]"
          @click="direction = item.value"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="primary-actions">
        <button type="button" class="action-button action-repeat">Повторять</button>
        <button type="button" class="action-button action-new">Учить новое</button>
      </div>
    </footer>
  </section>
</template>
