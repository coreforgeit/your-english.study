<script setup lang="ts">
import Button from 'primevue/button';
import { RouterView } from 'vue-router';
import { onMounted, ref } from 'vue';

import { authenticateTelegram } from '@/shared/api/auth';
import { fetchAndStoreUserSettings } from '@/shared/settings/userSettings';
import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { colorScheme, webApp } = useTelegramApp();

const authStatus = ref<'loading' | 'authenticated' | 'failed'>('loading');

async function authorize() {
  authStatus.value = 'loading';

  try {
    const isAuthenticated = await authenticateTelegram(webApp.value?.initData ?? '');
    if (!isAuthenticated) {
      authStatus.value = 'failed';
      return;
    }

    await fetchAndStoreUserSettings();
    authStatus.value = 'authenticated';
  } catch {
    authStatus.value = 'failed';
  }
}

onMounted(authorize);
</script>

<template>
  <div class="app-shell" :class="{ 'tg-dark': colorScheme === 'dark' }">
    <main v-if="authStatus === 'authenticated'" class="app-content">
      <RouterView />
    </main>

    <div v-else-if="authStatus === 'loading'" class="auth-state" role="status">
      Проверяем авторизацию…
    </div>

    <div v-else class="auth-error-backdrop">
      <section class="auth-error" role="alertdialog" aria-modal="true" aria-labelledby="auth-error-title">
        <h1 id="auth-error-title">Ошибка авторизации</h1>
        <p>Не удалось подтвердить вход через Telegram. Откройте приложение из Telegram и попробуйте ещё раз.</p>
        <Button label="Повторить" severity="danger" @click="authorize" />
      </section>
    </div>
  </div>
</template>
