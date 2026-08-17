<script setup lang="ts">
import { BookOpen, Languages, MessageCircle, RotateCcw } from '@lucide/vue';
</script>

<template>
  <section class="home-layout" aria-label="Главная">
    <div class="home-menu">
      <RouterLink class="home-menu-button home-menu-learn" :to="{ name: 'practice', query: { mode: 'learn' } }">
        <BookOpen :size="28" />
        <span>Учить</span>
      </RouterLink>

      <RouterLink class="home-menu-button home-menu-repeat" :to="{ name: 'practice', query: { mode: 'repeat' } }">
        <RotateCcw :size="28" />
        <span>Повторять</span>
      </RouterLink>

      <button class="home-menu-button home-menu-translate" type="button" disabled aria-label="Перевод — скоро">
        <Languages :size="28" />
        <span>Перевод</span>
      </button>

      <button class="home-menu-button home-menu-conversation" type="button" disabled aria-label="Разговор — скоро">
        <MessageCircle :size="28" />
        <span>Разговор</span>
      </button>
    </div>
  </section>
</template>
