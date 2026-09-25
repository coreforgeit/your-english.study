/** Ограничения фронтенда. Длительности заданы в миллисекундах. */
export const APP_LIMITS = {
  // Ограничения тренажёра слов; будущий тренажёр диалога получит отдельную группу.
  wordPractice: {
    recording: {
      maxDurationMs: 20_000,
      minDurationMs: 500,
      silenceDurationMs: 1_200,
      // Порог громкости RMS (0–1), выше которого считаем, что слышим речь.
      silenceThreshold: 0.025,
    },
    voiceAnswerTimeoutMs: 10_000,
  },
} as const;
