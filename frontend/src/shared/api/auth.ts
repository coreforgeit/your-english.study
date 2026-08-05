import { z } from 'zod';

import { authenticateTelegramSession } from '@/shared/api/client';

const telegramAuthResponseSchema = z.boolean();

export async function authenticateTelegram(initData: string): Promise<boolean> {
  return telegramAuthResponseSchema.parse(await authenticateTelegramSession(initData));
}
