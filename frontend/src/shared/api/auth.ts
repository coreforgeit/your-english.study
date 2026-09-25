import { authenticateTelegramSession } from '@/shared/api/client';
import { clearAuthenticatedSession, startAuthenticatedSession } from '@/shared/auth/session';

export async function authenticateTelegram(initData: string): Promise<boolean> {
  clearAuthenticatedSession();
  const authenticated = await authenticateTelegramSession(initData);
  if (authenticated) startAuthenticatedSession(initData);
  return authenticated;
}
