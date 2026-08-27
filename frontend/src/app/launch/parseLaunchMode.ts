import type { LocationQueryValue } from 'vue-router';

export type AppLaunchMode = 'repeat';

export function parseLaunchMode(
  queryValue: LocationQueryValue | LocationQueryValue[],
): AppLaunchMode | null {
  const value = Array.isArray(queryValue) ? queryValue[0] : queryValue;

  // Неизвестный mode игнорируем: ссылка должна открыть обычное главное меню.
  return value === 'repeat' ? value : null;
}
