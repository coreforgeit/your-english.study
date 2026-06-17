import { computed, onMounted, ref } from 'vue';

type TelegramWebApp = {
  colorScheme?: 'light' | 'dark';
  ready?: () => void;
  expand?: () => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

const webApp = ref<TelegramWebApp | null>(null);

export function useTelegramApp() {
  onMounted(() => {
    webApp.value = window.Telegram?.WebApp ?? null;
    webApp.value?.ready?.();
    webApp.value?.expand?.();
  });

  return {
    isTelegram: computed(() => webApp.value !== null),
    colorScheme: computed(() => webApp.value?.colorScheme ?? 'light'),
    webApp,
  };
}
