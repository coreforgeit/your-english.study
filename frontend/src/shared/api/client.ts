import { z } from 'zod';

import { BACKEND_URL } from '@/shared/config';

export { BACKEND_URL };

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
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
