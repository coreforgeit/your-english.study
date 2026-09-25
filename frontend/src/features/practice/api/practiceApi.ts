import { apiRequest } from '@/shared/api/client';
import type { PracticeMode, WordData } from '@/shared/practice';
import {
  answerResponseSchema,
  intervalRepetitionsResponseSchema,
  manualReviewResponseSchema,
  wordResponseSchema,
} from '@/features/practice/api/practiceSchemas';
import { normalizeAnswer, normalizeWordData } from '@/features/practice/api/practiceMappers';

async function requestWord(mode: PracticeMode, wordId: number | null = null): Promise<WordData> {
  const response = await apiRequest(
    `/api/telegram-app/words/${mode}`,
    wordResponseSchema,
    {
      method: 'POST',
      json: mode === 'repeat' && wordId !== null ? { word_id: wordId } : {},
      invalidResponseMessage: 'Не удалось загрузить слово. Попробуйте ещё раз.',
    },
  );
  return normalizeWordData(response);
}

export function fetchLearnWord(): Promise<WordData> {
  return requestWord('learn');
}

export function fetchRepeatWord(wordId: number | null): Promise<WordData> {
  return requestWord('repeat', wordId);
}

export async function fetchIntervalRepetitionWordIds(): Promise<number[]> {
  const response = await apiRequest(
    '/api/telegram-app/words/interval-repetitions',
    intervalRepetitionsResponseSchema,
  );
  return response.data;
}

type AnswerRequest = {
  wordId: number;
  answerLanguage: NonNullable<WordData['answerLanguage']>;
  textAnswer: string;
  recordedAudio: Blob | null;
  skip: boolean;
};

export async function sendPracticeAnswer(answer: AnswerRequest) {
  const { wordId, answerLanguage, textAnswer, recordedAudio, skip } = answer;
  const schema = answerResponseSchema(skip);
  const options = {
    method: 'POST',
    invalidResponseMessage: 'Не удалось получить результат проверки. Попробуйте ещё раз.',
  };
  const path = '/api/telegram-app/words/answer';
  let data;

  if (recordedAudio && !skip) {
    const formData = new FormData();
    formData.append('word_id', String(wordId));
    formData.append('answer_type', 'audio');
    formData.append('answer_language', answerLanguage);
    formData.append('skip', 'false');
    formData.append('audio_file', recordedAudio, 'answer.webm');
    data = await apiRequest(path, schema, { ...options, body: formData });
  } else {
    data = await apiRequest(path, schema, {
      ...options,
      json: {
        word_id: wordId,
        answer_type: 'text',
        answer_language: answerLanguage,
        ...(skip ? {} : { text_answer: textAnswer }),
        skip,
      },
    });
  }
  return normalizeAnswer(data, skip ? '' : textAnswer);
}

export async function sendWordToManualReview(wordId: number): Promise<void> {
  await apiRequest(
    `/api/telegram-app/words/${wordId}/manual-review`,
    manualReviewResponseSchema(wordId),
    { method: 'PATCH' },
  );
}
