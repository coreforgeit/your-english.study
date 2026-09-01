<script setup lang="ts">
import { BookOpen, Languages, MessageCircle, RotateCcw, Settings, X } from '@lucide/vue';
import Button from 'primevue/button';
import { RouterView, useRoute } from 'vue-router';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { useLaunchScenario } from '@/app/launch/useLaunchScenario';
import { authenticateTelegram } from '@/shared/api/auth';
import {
  createNotificationStream,
} from '@/shared/api/notifications';
import NotificationChat from '@/shared/components/NotificationChat.vue';
import TimeWheelPicker from '@/shared/components/TimeWheelPicker.vue';
import TimezonePicker from '@/shared/components/TimezonePicker.vue';
import { useNotificationCenter } from '@/shared/notifications/useNotificationCenter';
import {
  fetchAndStoreUserSettings,
  fetchLanguageLevels,
  getStoredUserSettings,
  updateAndStoreUserSettings,
  type LanguageLevel,
  type UserSettings,
} from '@/shared/settings/userSettings';
import { useTelegramApp } from '@/shared/telegram/useTelegramApp';

const { colorScheme, webApp } = useTelegramApp();
const route = useRoute();
const { runAfterPrerequisites } = useLaunchScenario();
const {
  messages: notificationMessages,
  addNotification,
  clearNotifications,
} = useNotificationCenter();

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
const settingsDialogRequired = ref(false);
const canSaveInitialSettings = computed(
  () => selectedLanguageLevelId.value !== null && !settingsDialogLoading.value && !settingsDialogSaving.value,
);
const settingsDialogTitle = computed(() =>
  settingsDialogRequired.value ? 'Выберите уровень английского' : 'Настройки',
);
let notificationStream: EventSource | null = null;

function connectNotificationStream() {
  notificationStream?.close();
  clearNotifications();
  notificationStream = createNotificationStream(addNotification);
}

function getBrowserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}


async function showSettingsDialog(settings: UserSettings, required: boolean) {
  settingsDialogRequired.value = required;
  selectedLanguageLevelId.value = settings.selected_language_level_id;
  remindersEnabled.value = required ? true : settings.reminders_enabled;
  reminderTime.value = settings.reminder_time.slice(0, 5);
  timezone.value = required
    ? (getBrowserTimezone() ?? settings.timezone ?? 'UTC')
    : (settings.timezone ?? getBrowserTimezone() ?? 'UTC');
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

async function openSettingsDialog() {
  if (showLanguageLevelDialog.value) {
    return;
  }

  const settings = getStoredUserSettings() ?? userSettings.value;
  if (!settings) {
    return;
  }

  await showSettingsDialog(settings, settings.selected_language_level_id === null);
}

function closeSettingsDialog() {
  if (settingsDialogRequired.value || settingsDialogSaving.value) {
    return;
  }

  showLanguageLevelDialog.value = false;
  settingsDialogError.value = null;
}

async function saveSettings() {
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
    settingsDialogRequired.value = false;
    await runAfterPrerequisites();
  } catch {
    settingsDialogError.value = 'Не удалось сохранить настройки. Попробуйте ещё раз.';
  } finally {
    settingsDialogSaving.value = false;
  }
}

async function authorize() {
  authStatus.value = 'loading';
  notificationStream?.close();
  notificationStream = null;
  clearNotifications();

  try {
    const isAuthenticated = await authenticateTelegram(webApp.value?.initData ?? '');
    if (!isAuthenticated) {
      authStatus.value = 'failed';
      return;
    }

    const settings = await fetchAndStoreUserSettings();
    userSettings.value = settings;
    connectNotificationStream();

    if (settings.selected_language_level_id === null) {
      authStatus.value = 'authenticated';
      await showSettingsDialog(settings, true);
      return;
    }

    await runAfterPrerequisites();
    authStatus.value = 'authenticated';
  } catch {
    authStatus.value = 'failed';
  }
}

onMounted(authorize);
onBeforeUnmount(() => notificationStream?.close());
</script>

<template>
  <div class="app-shell" :class="{ 'tg-dark': colorScheme === 'dark' }">
    <template v-if="authStatus === 'authenticated'">
      <button
        class="settings-button app-settings-button"
        type="button"
        aria-label="Открыть настройки"
        @click="openSettingsDialog"
      >
        <Settings :size="23" />
      </button>

      <main class="app-content" :class="{ 'app-content-with-navigation': showBottomNavigation }">
        <RouterView />
      </main>

      <NotificationChat
        :messages="notificationMessages"
        :with-navigation="showBottomNavigation"
        @clear="clearNotifications"
      />

      <nav v-if="showBottomNavigation" class="bottom-navigation" aria-label="Основное меню">
        <RouterLink
          class="bottom-navigation-item"
          :class="{ active: route.name === 'learn' }"
          :to="{ name: 'learn' }"
        >
          <BookOpen :size="22" />
          <span>Учить</span>
        </RouterLink>

        <RouterLink
          class="bottom-navigation-item"
          :class="{ active: route.name === 'repeat' }"
          :to="{ name: 'repeat' }"
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

      <div
        v-if="showLanguageLevelDialog"
        class="settings-dialog-backdrop"
        @click.self="closeSettingsDialog"
      >
        <section
          class="settings-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="language-level-dialog-title"
        >
          <button
            v-if="!settingsDialogRequired"
            class="settings-dialog-close"
            type="button"
            aria-label="Закрыть настройки"
            :disabled="settingsDialogSaving"
            @click="closeSettingsDialog"
          >
            <X :size="20" />
          </button>

          <h2 id="language-level-dialog-title">{{ settingsDialogTitle }}</h2>
          <p v-if="settingsDialogRequired" class="settings-dialog-description">
            Это поможет подобрать подходящие слова для изучения.
          </p>

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
            @click="saveSettings"
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
