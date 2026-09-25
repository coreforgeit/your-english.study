import type { z } from 'zod';
import { ApiError, getHttpErrorMessage } from '@/shared/api/errors';

export type ApiRequestOptions = Omit<RequestInit, 'body'> & {
  invalidResponseMessage?: string;
} & (
  | { json: unknown; body?: never }
  | { json?: never; body?: BodyInit | null }
);

type FetchResponse = (url: string, init?: RequestInit) => Promise<Response>;

export async function fetchResponse(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (cause) {
    const aborted = init?.signal?.aborted ||
      (cause instanceof Error && cause.name === 'AbortError');
    throw new ApiError(
      aborted ? 'aborted' : 'network',
      aborted ? 'Запрос отменён' : 'Не удалось связаться с сервером. Проверьте соединение.',
      { cause },
    );
  }
}

async function readResponse(response: Response, invalidMessage: string): Promise<unknown> {
  let text: string;
  try {
    text = await response.text();
  } catch (cause) {
    if (!response.ok) {
      throw new ApiError('http', getHttpErrorMessage(null, response.status), { status: response.status, cause });
    }
    const aborted = cause instanceof Error && cause.name === 'AbortError';
    throw new ApiError(
      aborted ? 'aborted' : 'network',
      aborted ? 'Запрос отменён' : 'Не удалось прочитать ответ сервера.',
      { status: response.status, cause },
    );
  }

  if (!text.trim()) return undefined;
  const contentType = response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() ?? '';
  const isJson = contentType === 'application/json' || contentType.endsWith('+json');
  if (!isJson) return text;

  try {
    return JSON.parse(text);
  } catch (cause) {
    // Некорректный JSON при HTTP-ошибке не должен скрывать её статус.
    if (!response.ok) return undefined;
    throw new ApiError('invalid-response', invalidMessage, { status: response.status, cause });
  }
}

// Общий транспорт ничего не знает о словах, настройках или Vue.
export async function requestWithSchema<S extends z.ZodTypeAny>(
  url: string,
  schema: S,
  options: ApiRequestOptions = {},
  send: FetchResponse = fetchResponse,
): Promise<z.output<S>> {
  const { json, invalidResponseMessage = 'Сервер вернул некорректные данные. Попробуйте ещё раз.', ...init } = options;
  const headers = new Headers(init.headers);
  let body = init.body;
  if ('json' in options) {
    body = JSON.stringify(json);
    headers.set('Content-Type', 'application/json');
  } else if (body instanceof FormData) {
    // Boundary устанавливает браузер, даже если вызывающий код передал JSON-заголовок.
    headers.delete('Content-Type');
  }
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');

  const response = await send(url, { ...init, headers, body });
  const data = await readResponse(response, invalidResponseMessage);
  if (!response.ok) {
    throw new ApiError('http', getHttpErrorMessage(data, response.status), {
      status: response.status, responseData: data,
    });
  }

  const result = schema.safeParse(data);
  if (!result.success) {
    throw new ApiError('invalid-response', invalidResponseMessage, {
      status: response.status, cause: result.error,
    });
  }
  return result.data;
}
