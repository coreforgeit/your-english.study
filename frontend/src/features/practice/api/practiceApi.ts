import { z } from 'zod';

import { authorizedFetch, BACKEND_URL } from '@/shared/api/client';

export const wordIdentitySchema = z.object({
  id: z.number().int().positive(),
  word: z.string().refine((value) => value.trim().length > 0, 'Слово не должно быть пустым'),
});

// Проверяем обязательные поля; остальные сохраняем для нормализации в карточку.
const wordResponseSchema = z.object({
  data: wordIdentitySchema.passthrough(),
});

export type PracticeWordResponse = z.infer<typeof wordResponseSchema>;

const intervalRepetitionsResponseSchema = z.object({
  data: z.array(z.number().int().positive()),
});

export class PracticeApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly responseData: unknown,
  ) {
    super(`Practice API вернул ${status}`);
    this.name = 'PracticeApiError';
  }
}

async function readResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  return contentType.includes('application/json')
    ? response.json()
    : response.text();
}

async function requestWord(
  mode: 'learn' | 'repeat',
  wordId: number | null = null,
): Promise<PracticeWordResponse> {
  const url = `${BACKEND_URL}/api/telegram-app/words/${mode}`;
  const body = mode === 'repeat' && wordId !== null ? { word_id: wordId } : {};

  console.log('[practice-word:request]', { method: 'POST', url, body });

  const response = await authorizedFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const data = await readResponse(response);

  console.log('[practice-word:response]', data);

  if (!response.ok) {
    throw new PracticeApiError(response.status, data);
  }

  const result = wordResponseSchema.safeParse(data);
  if (!result.success) {
    throw new Error('Не удалось загрузить слово. Попробуйте ещё раз.', { cause: result.error });
  }

  return result.data;
}

export async function fetchLearnWord(): Promise<PracticeWordResponse> {
  return requestWord('learn');
}

export async function fetchRepeatWord(wordId: number | null): Promise<PracticeWordResponse> {
  return requestWord('repeat', wordId);
}

export async function fetchIntervalRepetitionWordIds(): Promise<number[]> {
  const response = await authorizedFetch(
    `${BACKEND_URL}/api/telegram-app/words/interval-repetitions`,
  );
  const data = await readResponse(response);

  if (!response.ok) {
    throw new PracticeApiError(response.status, data);
  }

  // Проверяем контракт здесь, чтобы UI всегда получал обычный массив id.
  return intervalRepetitionsResponseSchema.parse(data).data;
}
