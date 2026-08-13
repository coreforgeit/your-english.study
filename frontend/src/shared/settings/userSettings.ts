import { z } from 'zod';

import { apiRequest } from '@/shared/api/client';


const userSettingsSchema = z.object({
  selected_language_level_id: z.number().int().nullable(),
  system_language_level_id: z.number().int().nullable(),
  reminders_enabled: z.boolean(),
  timezone: z.string().min(1).max(64).nullable(),
  reminder_time: z.string(),
});

const userSettingsResponseSchema = z.object({
  data: userSettingsSchema,
});

const languageLevelSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  grade: z.number().int(),
});

const languageLevelsResponseSchema = z.object({
  data: z.array(languageLevelSchema),
});

export type UserSettings = z.infer<typeof userSettingsSchema>;
export type LanguageLevel = z.infer<typeof languageLevelSchema>;

export type UserSettingsUpdate = {
  selected_language_level_id: number;
  reminders_enabled: boolean;
  timezone: string;
  reminder_time: string;
};

export const USER_SETTINGS_STORAGE_KEY = 'user_settings';

export async function fetchAndStoreUserSettings(): Promise<UserSettings> {
  const response = await apiRequest(
    '/api/telegram-app/settings',
    userSettingsResponseSchema,
    { method: 'GET' },
  );
  localStorage.setItem(USER_SETTINGS_STORAGE_KEY, JSON.stringify(response.data));
  return response.data;
}

export async function fetchLanguageLevels(): Promise<LanguageLevel[]> {
  const response = await apiRequest(
    '/api/telegram-app/settings/language-levels',
    languageLevelsResponseSchema,
    { method: 'GET' },
  );
  return response.data;
}

export async function updateAndStoreUserSettings(
  settings: UserSettingsUpdate,
): Promise<UserSettings> {
  const response = await apiRequest(
    '/api/telegram-app/settings',
    userSettingsResponseSchema,
    {
      method: 'PATCH',
      body: JSON.stringify(settings),
    },
  );
  localStorage.setItem(USER_SETTINGS_STORAGE_KEY, JSON.stringify(response.data));
  return response.data;
}
