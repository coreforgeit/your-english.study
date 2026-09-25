export type ApiErrorKind = 'network' | 'http' | 'invalid-response' | 'aborted';

type ApiErrorDetails = {
  status?: number;
  responseData?: unknown;
  cause?: unknown;
};

export class ApiError extends Error {
  readonly status: number | null;
  readonly responseData: unknown;

  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    details: ApiErrorDetails = {},
  ) {
    super(message, { cause: details.cause });
    this.name = 'ApiError';
    this.status = details.status ?? null;
    this.responseData = details.responseData;
  }
}

export function getApiErrorMessage(error: unknown, fallback = 'Не удалось выполнить запрос'): string {
  return error instanceof ApiError ? error.message : fallback;
}

// Не показываем пользователю HTML прокси или произвольное тело ответа.
export function getHttpErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    for (const key of ['detail', 'message', 'error']) {
      const value = (data as Record<string, unknown>)[key];
      if (typeof value === 'string' && value.trim()) return value;
    }
  }
  return `Сервер вернул ошибку ${status}`;
}
