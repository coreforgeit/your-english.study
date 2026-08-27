import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { parseLaunchMode, type AppLaunchMode } from '@/app/launch/parseLaunchMode';
import {
  APP_LAUNCH_AUTO_START_VALUE,
  AppLaunchQuery,
} from '@/shared/navigation/appLaunch';

export function useLaunchScenario() {
  const route = useRoute();
  const router = useRouter();
  const pendingMode = ref<AppLaunchMode | null>(
    parseLaunchMode(route.query[AppLaunchQuery.MODE]),
  );

  async function runAfterPrerequisites() {
    if (pendingMode.value !== 'repeat') {
      return;
    }

    // Запускаем сценарий только после авторизации и обязательных настроек.
    await router.replace({
      name: 'repeat',
      query: {
        [AppLaunchQuery.AUTO_START]: APP_LAUNCH_AUTO_START_VALUE,
      },
    });
    pendingMode.value = null;
  }

  return {
    runAfterPrerequisites,
  };
}
