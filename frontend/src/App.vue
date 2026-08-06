<script setup lang="ts">
import { BookOpen, Languages, MessageCircle, RotateCcw } from '@lucide/vue';
import Button from 'primevue/button';
import { RouterView, useRoute } from 'vue-router';
import { computed, onMounted, ref } from 'vue';

import { authenticateTelegram } from '@/shared/api/auth';
import { fetchAndStoreUserSettings } from '@/shared/settings/userSettings';
import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { colorScheme, webApp } = useTelegramApp();
const route = useRoute();

const authStatus = ref<'loading' | 'authenticated' | 'failed'>('loading');
const showBottomNavigation = computed(() => route.name !== 'admin');

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
    <template v-if="authStatus === 'authenticated'">
      <main class="app-content" :class="{ 'app-content-with-navigation': showBottomNavigation }">
        <RouterView />
      </main>

      <nav v-if="showBottomNavigation" class="bottom-navigation" aria-label="Основное меню">
        <RouterLink
          class="bottom-navigation-item"
          :class="{ active: route.name === 'practice' && route.query.mode === 'learn' }"
          :to="{ name: 'practice', query: { mode: 'learn' } }"
        >
          <BookOpen :size="22" />
          <span>Учить</span>
        </RouterLink>

        <RouterLink
          class="bottom-navigation-item"
          :class="{ active: route.name === 'practice' && route.query.mode !== 'learn' }"
          :to="{ name: 'practice', query: { mode: 'repeat' } }"
        >
          <RotateCcw :size="22" />
          <span>Повтор</span>
        </RouterLink>

        <button class="bottom-navigation-item" type="button" disabled aria-label="Перевод — скоро">
          <Languages :size="22" />
          <span>Перевод</span>
        </button>

        <button class="bottom-navigation-item" type="button" disabled aria-label="Разговор — скоро">
          <MessageCircle :size="22" />
          <span>Разговор</span>
        </button>
      </nav>
    </template>

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
