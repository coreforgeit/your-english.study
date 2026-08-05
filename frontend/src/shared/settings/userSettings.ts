import { z } from 'zod';

import { apiRequest } from '@/shared/api/client';


const userSettingsSchema = z.object({
  timezone: z.string().min(1).max(64),
});

const userSettingsResponseSchema = z.object({
  data: userSettingsSchema,
});

export type UserSettings = z.infer<typeof userSettingsSchema>;

export const USER_SETTINGS_STORAGE_KEY = 'user_settings';

export async function fetchAndStoreUserSettings(): Promise<UserSettings> {
  const response = await apiRequest(
    '/api/telegram-app/settings',
    userSettingsResponseSchema,
    { method: 'POST' },
  );
  localStorage.setItem(USER_SETTINGS_STORAGE_KEY, JSON.stringify(response.data));
  return response.data;
}
