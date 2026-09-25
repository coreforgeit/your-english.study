export type PracticeMode = 'learn' | 'repeat';
export type DisplayDirection = 'ru-en' | 'en-ru';
export type AnswerStatus = 'correct' | 'incorrect' | null;
export type TypoType = 'replace' | 'missing' | 'extra';
export type VoiceAnswerDialogState = 'hidden' | 'checking' | 'error';

export type AnswerTypo = {
  index: number;
  type: TypoType;
  expected: string | null;
  actual: string | null;
};

export type AnswerCharState = 'normal' | 'replace' | 'extra' | 'missing' | 'expected';

export type AnswerCharPart = {
  key: string;
  value: string;
  state: AnswerCharState;
};

export type WordData = {
  id: number;
  word: string;
  pronunciation: string | null;
  translations: string[];
  partOfSpeech: string | null;
  audioUrl: string | null;
  level: string | null;
  answerLanguage: 'en' | 'ru' | null;
};

export type WordInfo = {
  text: string;
  pronunciation?: string | null;
  partOfSpeech?: string | null;
  audioUrl?: string | null;
};

export type PracticeState = {
  word: WordData | null;
  displayDirection: DisplayDirection;
  showAnswer: boolean;
  answerSubmitted: boolean;
  answerText: string;
  answerStatus: AnswerStatus;
  answerSkipped: boolean;
  answerTypo: AnswerTypo | null;
  submittedAnswer: string;
  correctAnswers: string[];
  answerComment: string | null;
  recordedAudio: Blob | null;
};

