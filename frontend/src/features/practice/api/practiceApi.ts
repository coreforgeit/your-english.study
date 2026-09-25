import { z } from 'zod';

import { authorizedFetch, BACKEND_URL } from '@/shared/api/client';
import type { PracticeMode, WordData } from '@/shared/practice';

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
  mode: PracticeMode,
  wordId: number | null = null,
): Promise<PracticeWordResponse> {
  const url = `${BACKEND_URL}/api/telegram-app/words/${mode}`;
  const body = mode === 'repeat' && wordId !== null ? { word_id: wordId } : {};

  console.log('Загрузка слова:', { mode, wordId });

  const response = await authorizedFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const data = await readResponse(response);

  console.log('Ответ на загрузку слова:', { status: response.status });

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

type AnswerRequest = {
  wordId: number;
  answerLanguage: NonNullable<WordData['answerLanguage']>;
  textAnswer: string;
  recordedAudio: Blob | null;
  skip: boolean;
};

export async function sendPracticeAnswer(answer: AnswerRequest): Promise<unknown> {
  const { wordId, answerLanguage, textAnswer, recordedAudio, skip } = answer;
  const request: RequestInit = { method: 'POST' };

  if (recordedAudio && !skip) {
    const formData = new FormData();
    formData.append('word_id', String(wordId));
    formData.append('answer_type', 'audio');
    formData.append('answer_language', answerLanguage);
    formData.append('skip', 'false');
    formData.append('audio_file', recordedAudio, 'answer.webm');
    request.body = formData;
  } else {
    request.headers = { 'Content-Type': 'application/json' };
    request.body = JSON.stringify({
      word_id: wordId,
      answer_type: 'text',
      answer_language: answerLanguage,
      ...(skip ? {} : { text_answer: textAnswer }),
      skip,
    });
  }

  const response = await authorizedFetch(`${BACKEND_URL}/api/telegram-app/words/answer`, request);
  const data = await readResponse(response);
  if (!response.ok) throw new PracticeApiError(response.status, data);
  return data;
}

export async function sendWordToManualReview(wordId: number): Promise<void> {
  const response = await authorizedFetch(
    `${BACKEND_URL}/api/telegram-app/words/${wordId}/manual-review`,
    { method: 'PATCH' },
  );
  const data = await readResponse(response);
  if (!response.ok) throw new PracticeApiError(response.status, data);
}
