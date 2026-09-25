import type { PracticeWordResponse } from '@/features/practice/api/practiceApi';
import type { AnswerStatus, AnswerTypo, TypoType, WordData } from '@/shared/practice';

function getResponseData(data: unknown) {
  if (data && typeof data === 'object' && 'data' in data && data.data && typeof data.data === 'object') {
    return data.data;
  }

  return data;
}

function isTypoType(value: unknown): value is TypoType {
  return value === 'replace' || value === 'missing' || value === 'extra';
}

function getAnswerTypo(data: unknown): AnswerTypo | null {
  const responseData = getResponseData(data);

  if (!responseData || typeof responseData !== 'object') {
    return null;
  }

  if (!('has_typo' in responseData) || responseData.has_typo !== true) {
    return null;
  }

  if (!('typo' in responseData) || !responseData.typo || typeof responseData.typo !== 'object') {
    return null;
  }

  const typo = responseData.typo;

  if (
    !('index' in typo) ||
    typeof typo.index !== 'number' ||
    !('type' in typo) ||
    !isTypoType(typo.type)
  ) {
    return null;
  }

  return {
    index: typo.index,
    type: typo.type,
    expected: 'expected' in typo && typeof typo.expected === 'string' ? typo.expected : null,
    actual: 'actual' in typo && typeof typo.actual === 'string' ? typo.actual : null,
  };
}

export function normalizeWordData(data: PracticeWordResponse): WordData {
  const wordData = data.data;

  return {
    id: wordData.id,
    word: wordData.word,
    pronunciation:
      'pronunciation' in wordData && typeof wordData.pronunciation === 'string' ? wordData.pronunciation : null,
    translations: getWordTranslations(wordData),
    partOfSpeech:
      'part_of_speech' in wordData && typeof wordData.part_of_speech === 'string' ? wordData.part_of_speech : null,
    audioUrl: 'audio_url' in wordData && typeof wordData.audio_url === 'string' ? wordData.audio_url : null,
    level: 'level' in wordData && typeof wordData.level === 'string' ? wordData.level : null,
    answerLanguage:
      'answer_language' in wordData && (wordData.answer_language === 'en' || wordData.answer_language === 'ru')
        ? wordData.answer_language
        : null,
  };
}

function getWordTranslations(wordData: object): string[] {
  if ('translations' in wordData && Array.isArray(wordData.translations)) {
    const translations = wordData.translations.filter(
      (translation): translation is string => typeof translation === 'string' && translation.trim().length > 0,
    );
    if (translations.length > 0) {
      return translations;
    }
  }

  return ['Перевод не пришёл'];
}

export function getBackendErrorMessage(data: unknown, fallback: string) {
  if (data && typeof data === 'object') {
    if ('detail' in data && typeof data.detail === 'string') {
      return data.detail;
    }

    if ('message' in data && typeof data.message === 'string') {
      return data.message;
    }

    if ('error' in data && typeof data.error === 'string') {
      return data.error;
    }
  }

  if (typeof data === 'string' && data.trim()) {
    return data;
  }

  return fallback;
}

function getAnswerResult(data: unknown): AnswerStatus {
  const responseData = getResponseData(data);

  if (!responseData || typeof responseData !== 'object') {
    return null;
  }

  if ('is_correct' in responseData && typeof responseData.is_correct === 'boolean') {
    return responseData.is_correct ? 'correct' : 'incorrect';
  }

  if ('correct' in responseData && typeof responseData.correct === 'boolean') {
    return responseData.correct ? 'correct' : 'incorrect';
  }

  return null;
}

function getAnswerSkipped(data: unknown) {
  const responseData = getResponseData(data);

  return Boolean(
    responseData &&
      typeof responseData === 'object' &&
      'skip' in responseData &&
      responseData.skip === true
  );
}

function getSubmittedAnswerFromResponse(data: unknown, fallback: string) {
  const responseData = getResponseData(data);

  if (responseData && typeof responseData === 'object' && 'answer' in responseData && typeof responseData.answer === 'string') {
    return responseData.answer;
  }

  return fallback;
}

function getCorrectAnswersFromResponse(data: unknown, fallback: string[]) {
  const responseData = getResponseData(data);

  if (
    responseData &&
    typeof responseData === 'object' &&
    'correct_answer' in responseData &&
    Array.isArray(responseData.correct_answer)
  ) {
    const correctAnswers = responseData.correct_answer
      .filter((answer): answer is string => typeof answer === 'string' && answer.trim().length > 0)
      .slice(0, 3);

    if (correctAnswers.length > 0) {
      return correctAnswers;
    }
  }

  return fallback;
}

function getAnswerCommentFromResponse(data: unknown) {
  const responseData = getResponseData(data);

  if (
    responseData &&
    typeof responseData === 'object' &&
    'comment' in responseData &&
    typeof responseData.comment === 'string'
  ) {
    return responseData.comment.trim() || null;
  }

  return null;
}

export function normalizeAnswer(data: unknown, submittedAnswer: string, correctAnswers: string[]) {
  return {
    answerStatus: getAnswerResult(data),
    answerSkipped: getAnswerSkipped(data),
    answerTypo: getAnswerTypo(data),
    submittedAnswer: getSubmittedAnswerFromResponse(data, submittedAnswer),
    correctAnswers: getCorrectAnswersFromResponse(data, correctAnswers),
    answerComment: getAnswerCommentFromResponse(data),
  };
}
