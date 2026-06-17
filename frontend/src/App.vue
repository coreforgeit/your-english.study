<script setup lang="ts">
import { RouterView } from 'vue-router';

import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { isTelegram, colorScheme } = useTelegramApp();
</script>

<template>
  <div class="app-shell" :class="{ 'tg-dark': colorScheme === 'dark' }">
    <main class="app-content">
      <RouterView />
    </main>

    <div v-if="!isTelegram" class="dev-banner">
      Режим предпросмотра
    </div>
  </div>
</template>
