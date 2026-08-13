<script setup lang="ts">
import { BookOpen, Languages, MessageCircle, RotateCcw } from '@lucide/vue';
import Button from 'primevue/button';
import { RouterView, useRoute } from 'vue-router';
import { computed, onMounted, ref } from 'vue';

import { authenticateTelegram } from '@/shared/api/auth';
import TimeWheelPicker from '@/shared/components/TimeWheelPicker.vue';
import TimezonePicker from '@/shared/components/TimezonePicker.vue';
import {
  fetchAndStoreUserSettings,
  fetchLanguageLevels,
  updateAndStoreUserSettings,
  type LanguageLevel,
  type UserSettings,
} from '@/shared/settings/userSettings';
import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { colorScheme, webApp } = useTelegramApp();
const route = useRoute();

const authStatus = ref<'loading' | 'authenticated' | 'failed'>('loading');
const showBottomNavigation = computed(() => route.name !== 'admin');
const userSettings = ref<UserSettings | null>(null);
const languageLevels = ref<LanguageLevel[]>([]);
const showLanguageLevelDialog = ref(false);
const selectedLanguageLevelId = ref<number | null>(null);
const remindersEnabled = ref(true);
const reminderTime = ref('20:00');
const timezone = ref('UTC');
const settingsDialogLoading = ref(false);
const settingsDialogSaving = ref(false);
const settingsDialogError = ref<string | null>(null);
const canSaveInitialSettings = computed(
  () => selectedLanguageLevelId.value !== null && !settingsDialogLoading.value && !settingsDialogSaving.value,
);

function getBrowserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

async function openInitialSettingsDialog(settings: UserSettings) {
  remindersEnabled.value = true;
  reminderTime.value = settings.reminder_time.slice(0, 5);
  timezone.value = getBrowserTimezone() ?? settings.timezone ?? 'UTC';
  showLanguageLevelDialog.value = true;
  settingsDialogLoading.value = true;
  settingsDialogError.value = null;

  try {
    languageLevels.value = await fetchLanguageLevels();
  } catch {
    settingsDialogError.value = 'Не удалось загрузить список уровней. Попробуйте ещё раз.';
  } finally {
    settingsDialogLoading.value = false;
  }
}

async function saveInitialSettings() {
  if (!canSaveInitialSettings.value || selectedLanguageLevelId.value === null) {
    return;
  }

  settingsDialogSaving.value = true;
  settingsDialogError.value = null;

  try {
    userSettings.value = await updateAndStoreUserSettings({
      selected_language_level_id: selectedLanguageLevelId.value,
      reminders_enabled: remindersEnabled.value,
      reminder_time: reminderTime.value,
      timezone: timezone.value,
    });
    showLanguageLevelDialog.value = false;
  } catch {
    settingsDialogError.value = 'Не удалось сохранить настройки. Попробуйте ещё раз.';
  } finally {
    settingsDialogSaving.value = false;
  }
}

async function authorize() {
  authStatus.value = 'loading';

  try {
    const isAuthenticated = await authenticateTelegram(webApp.value?.initData ?? '');
    if (!isAuthenticated) {
      authStatus.value = 'failed';
      return;
    }

    const settings = await fetchAndStoreUserSettings();
    userSettings.value = settings;
    authStatus.value = 'authenticated';

    if (settings.selected_language_level_id === null) {
      await openInitialSettingsDialog(settings);
    }
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

      <div v-if="showLanguageLevelDialog" class="settings-dialog-backdrop">
        <section
          class="settings-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="language-level-dialog-title"
        >
          <h2 id="language-level-dialog-title">Выберите уровень английского</h2>
          <p class="settings-dialog-description">Это поможет подобрать подходящие слова для изучения.</p>

          <fieldset class="language-level-options" :disabled="settingsDialogLoading || settingsDialogSaving">
            <legend>Уровень языка</legend>
            <p v-if="settingsDialogLoading" class="settings-dialog-status">Загружаем уровни…</p>
            <template v-else>
              <label
                v-for="level in languageLevels"
                :key="level.id"
                class="language-level-option"
                :class="[
                  `level-${level.name.toLowerCase()}`,
                  { active: selectedLanguageLevelId === level.id },
                ]"
              >
                <input v-model="selectedLanguageLevelId" type="radio" :value="level.id" />
                <span>{{ level.name }}</span>
              </label>
            </template>
          </fieldset>

          <label class="settings-dialog-field settings-dialog-toggle">
            <input v-model="remindersEnabled" type="checkbox" :disabled="settingsDialogSaving" />
            <span>Включить напоминания</span>
          </label>

          <label class="settings-dialog-field">
            <span>Время напоминания</span>
            <TimeWheelPicker v-model="reminderTime" :disabled="settingsDialogSaving" />
          </label>

          <label class="settings-dialog-field">
            <span>Часовой пояс</span>
            <TimezonePicker v-model="timezone" :disabled="settingsDialogSaving" />
          </label>

          <p v-if="settingsDialogError" class="settings-dialog-error" role="alert">
            {{ settingsDialogError }}
          </p>

          <button
            class="settings-dialog-submit"
            type="button"
            :disabled="!canSaveInitialSettings"
            @click="saveInitialSettings"
          >
            {{ settingsDialogSaving ? 'Сохраняем…' : 'ОК' }}
          </button>
        </section>
      </div>
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
