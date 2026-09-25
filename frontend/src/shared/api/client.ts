import { z } from 'zod';

import { fetchResponse, requestWithSchema, type ApiRequestOptions } from '@/shared/api/request';
import { BACKEND_URL } from '@/shared/config';

export { ApiError, getApiErrorMessage } from '@/shared/api/errors';
export type { ApiErrorKind } from '@/shared/api/errors';
export type { ApiRequestOptions } from '@/shared/api/request';

export { BACKEND_URL };

let sessionRenewal: Promise<boolean> | null = null;

export async function authenticateTelegramSession(initData: string): Promise<boolean> {
  // Авторизация использует тот же транспорт, но не запускает собственное обновление сессии.
  return requestWithSchema(`${BACKEND_URL}/api/auth_tg`, z.boolean(), {
    method: 'POST',
    credentials: 'include',
    json: { init_data: initData },
  });
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
  let response = await fetchResponse(url, requestInit);

  if (response.status !== 401 || !(await renewSession())) {
    return response;
  }

  response = await fetchResponse(url, requestInit);
  return response;
}

export async function apiRequest<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  options: ApiRequestOptions = {},
): Promise<z.output<S>> {
  return requestWithSchema(`${BACKEND_URL}${path}`, schema, options, authorizedFetch);
}
