import { z } from 'zod';
import { wordIdentitySchema } from '@/features/practice/api/practiceApi';
import type { DisplayDirection, PracticeState, WordData } from '@/shared/practice';

const wordDataStorageSchema = wordIdentitySchema.extend({
  pronunciation: z.string().nullable(),
  translations: z.array(z.string()),
  partOfSpeech: z.string().nullable(),
  audioUrl: z.string().nullable(),
  level: z.string().nullable(),
  answerLanguage: z.enum(['en', 'ru']).nullable().default(null),
});

const answerTypoStorageSchema = z.object({
  index: z.number(),
  type: z.enum(['replace', 'missing', 'extra']),
  expected: z.string().nullable(),
  actual: z.string().nullable(),
});

const learnSessionWordSchema = z.object({
  word: wordDataStorageSchema,
  displayDirection: z.enum(['ru-en', 'en-ru']),
});

const repeatSessionStateSchema = z.object({
  word: wordDataStorageSchema,
  displayDirection: z.enum(['ru-en', 'en-ru']),
  showAnswer: z.boolean(),
  answerSubmitted: z.boolean(),
  answerText: z.string(),
  answerStatus: z.enum(['correct', 'incorrect']).nullable(),
  answerSkipped: z.boolean().default(false),
  answerTypo: answerTypoStorageSchema.nullable(),
  submittedAnswer: z.string(),
  correctAnswers: z.array(z.string()).default([]),
  answerComment: z.string().nullable().default(null),
});

const LEARN_SESSION_WORD_STORAGE_KEY = 'practice:last-learn-word';
const REPEAT_SESSION_STATE_STORAGE_KEY = 'practice:last-repeat-state';

function readStored<T extends z.ZodTypeAny>(key: string, schema: T): z.output<T> | null {
  try {
    const value = sessionStorage.getItem(key);
    return value ? schema.parse(JSON.parse(value)) : null;
  } catch {
    // Повреждённый кэш удаляем; недоступное хранилище не мешает работе в памяти.
    try {
      sessionStorage.removeItem(key);
    } catch {
      // Сам доступ к sessionStorage может быть запрещён браузером.
    }
    return null;
  }
}

export function restoreLearnSessionWord() {
  return readStored(LEARN_SESSION_WORD_STORAGE_KEY, learnSessionWordSchema);
}

export function restoreRepeatSessionState(): PracticeState | null {
  const stored = readStored(REPEAT_SESSION_STATE_STORAGE_KEY, repeatSessionStateSchema);
  return stored ? { ...stored, recordedAudio: null } : null;
}

export function saveLearnSessionWord(word: WordData, displayDirection: DisplayDirection) {
  try {
    sessionStorage.setItem(
      LEARN_SESSION_WORD_STORAGE_KEY,
      JSON.stringify({ word, displayDirection }),
    );
  } catch {
    // Если хранилище недоступно, состояние остаётся в памяти.
  }
}

export function saveRepeatSessionState(state: PracticeState) {
  if (!state.word) {
    return;
  }

  try {
    sessionStorage.setItem(
      REPEAT_SESSION_STATE_STORAGE_KEY,
      JSON.stringify({
        word: state.word,
        displayDirection: state.displayDirection,
        showAnswer: state.showAnswer,
        answerSubmitted: state.answerSubmitted,
        answerText: state.answerText,
        answerStatus: state.answerStatus,
        answerSkipped: state.answerSkipped,
        answerTypo: state.answerTypo,
        submittedAnswer: state.submittedAnswer,
        correctAnswers: state.correctAnswers,
        answerComment: state.answerComment,
      }),
    );
  } catch {
    // Если хранилище недоступно, состояние остаётся в памяти.
  }
}
