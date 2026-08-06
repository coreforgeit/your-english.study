<script setup lang="ts">
import { BookOpen, RotateCcw, Settings } from '@lucide/vue';
</script>

<template>
  <section class="home-layout" aria-label="Главная">
    <div class="home-toolbar">
      <button class="settings-button" type="button" disabled aria-label="Настройки — скоро" title="Скоро">
        <Settings :size="23" />
      </button>
    </div>

    <div class="home-menu">
      <RouterLink class="home-menu-button home-menu-learn" :to="{ name: 'practice', query: { mode: 'learn' } }">
        <BookOpen :size="28" />
        <span>Учить</span>
      </RouterLink>

      <RouterLink class="home-menu-button home-menu-repeat" :to="{ name: 'practice', query: { mode: 'repeat' } }">
        <RotateCcw :size="28" />
        <span>Повторять</span>
      </RouterLink>
    </div>
  </section>
</template>
