import { z } from 'zod';

import { BACKEND_URL } from '@/shared/config';

export { BACKEND_URL };

let sessionRenewal: Promise<boolean> | null = null;

export async function authenticateTelegramSession(initData: string): Promise<boolean> {
  const response = await fetch(`${BACKEND_URL}/api/auth_tg`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ init_data: initData }),
  });

  if (!response.ok) {
    throw new Error(`Telegram authentication failed: ${response.status}`);
  }

  return z.boolean().parse(await response.json());
}

async function renewSession(): Promise<boolean> {
  if (!sessionRenewal) {
    const initData = window.Telegram?.WebApp?.initData ?? '';
    sessionRenewal = authenticateTelegramSession(initData).finally(() => {
      sessionRenewal = null;
    });
  }

  return sessionRenewal;
}

export async function authorizedFetch(url: string, init?: RequestInit): Promise<Response> {
  const requestInit: RequestInit = {
    ...init,
    credentials: 'include',
  };
  let response = await fetch(url, requestInit);

  if (response.status !== 401 || !(await renewSession())) {
    return response;
  }

  response = await fetch(url, requestInit);
  return response;
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await authorizedFetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return schema.parse(await response.json());
}
