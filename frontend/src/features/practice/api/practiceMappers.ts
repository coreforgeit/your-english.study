import type { PracticeWordResponse, PracticeAnswerData } from '@/features/practice/api/practiceSchemas';
import type { PracticeState, WordData } from '@/shared/practice';

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

type AnswerResult = Pick<PracticeState,
  'answerStatus' | 'answerSkipped' | 'answerTypo' | 'submittedAnswer' | 'correctAnswers' | 'answerComment'
>;

export function normalizeAnswer(data: PracticeAnswerData, submittedAnswer: string): AnswerResult {
  const correct = data.is_correct ?? data.correct;
  return {
    answerStatus: typeof correct === 'boolean' ? (correct ? 'correct' : 'incorrect') : null,
    answerSkipped: data.skip,
    answerTypo: data.has_typo ? data.typo : null,
    submittedAnswer: data.answer ?? submittedAnswer,
    correctAnswers: data.correct_answer.filter((answer) => answer.trim()).slice(0, 3),
    answerComment: data.comment?.trim() || null,
  };
}
