<script setup lang="ts">
import { RouterView } from 'vue-router';

import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { colorScheme } = useTelegramApp();
</script>

<template>
  <div class="app-shell" :class="{ 'tg-dark': colorScheme === 'dark' }">
    <main class="app-content">
      <RouterView />
    </main>
  </div>
</template>
