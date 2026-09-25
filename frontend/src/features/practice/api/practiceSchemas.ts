import { z } from 'zod';
import { MANUAL_REVIEW_STATUS } from '@/shared/practice';

export const wordIdentitySchema = z.object({
  id: z.number().int().positive(),
  word: z.string().refine((value) => value.trim().length > 0, 'Слово не должно быть пустым'),
});

// Обязательны только id и слово; дополнительная информация остаётся необязательной.
export const wordResponseSchema = z.object({ data: wordIdentitySchema.passthrough() });
export type PracticeWordResponse = z.infer<typeof wordResponseSchema>;
export const intervalRepetitionsResponseSchema = z.object({
  data: z.array(z.number().int().positive()),
});

const answerTypoSchema = z.object({
  index: z.number().int().nonnegative(),
  type: z.enum(['replace', 'missing', 'extra']),
  expected: z.string().nullable().default(null),
  actual: z.string().nullable().default(null),
});

const answerDataSchema = z.object({
  success: z.literal(true).optional(),
  answer: z.string().optional(),
  is_correct: z.boolean().nullable().optional(),
  correct: z.boolean().optional(),
  skip: z.boolean().default(false),
  correct_answer: z.array(z.string()).default([]),
  has_typo: z.boolean().default(false),
  typo: answerTypoSchema.nullable().default(null),
  comment: z.string().nullable().default(null),
});
export type PracticeAnswerData = z.output<typeof answerDataSchema>;

export function answerResponseSchema(skip: boolean) {
  // Сохраняем поддержку старого плоского ответа и поля correct в одном месте.
  const response = z.preprocess((value) => {
    if (value && typeof value === 'object' && 'data' in value) return value.data;
    return value;
  }, answerDataSchema);
  return response.superRefine((data, context) => {
    if (data.skip !== skip) {
      context.addIssue({ code: 'custom', message: 'Результат не соответствует типу отправленного ответа', path: ['skip'] });
    }
    if (!skip && typeof data.is_correct !== 'boolean' && typeof data.correct !== 'boolean') {
      context.addIssue({ code: 'custom', message: 'Отсутствует результат проверки ответа', path: ['is_correct'] });
    }
    if (data.has_typo && !data.typo) {
      context.addIssue({ code: 'custom', message: 'Отсутствуют сведения об опечатке', path: ['typo'] });
    }
  });
}

export function manualReviewResponseSchema(wordId: number) {
  return z.object({
    data: z.object({
      id: z.literal(wordId),
      status: z.literal(MANUAL_REVIEW_STATUS),
    }),
  });
}
