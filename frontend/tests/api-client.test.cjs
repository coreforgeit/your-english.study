const assert = require('node:assert/strict');
const { test } = require('node:test');
const { z } = require('zod');
const { load } = require('./helpers/loadFrontend.cjs');

const json = (body, status = 200, contentType = 'application/json') =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } });
const schema = z.object({ data: z.number() }).transform((value) => value.data);
const config = { '@/shared/config': { BACKEND_URL: 'https://example.test' } };
function client(fetch) {
  return load('src/shared/api/client.ts', config, {
    fetch, window: { Telegram: { WebApp: { initData: 'test-init-data' } } },
  });
}
function isError(api, kind, status) {
  return (error) => {
    assert.ok(error instanceof api.ApiError);
    assert.equal(error.kind, kind);
    assert.equal(error.status, status);
    return true;
  };
}

test('JSON request preserves headers, credentials, signal and schema transformations', async () => {
  const controller = new AbortController();
  const api = client(async (url, init) => {
    assert.equal(url, 'https://example.test/example');
    assert.equal(init.method, 'PATCH');
    assert.equal(init.credentials, 'include');
    assert.equal(init.signal, controller.signal);
    assert.equal(init.headers.get('Content-Type'), 'application/json');
    assert.equal(init.headers.get('X-Test'), 'yes');
    assert.deepEqual(JSON.parse(init.body), { enabled: true });
    return json({ data: 42, future: true });
  });
  assert.equal(await api.apiRequest('/example', schema, {
    method: 'PATCH', json: { enabled: true },
    headers: new Headers({ 'X-Test': 'yes' }), signal: controller.signal,
  }), 42);
});

test('FormData leaves its boundary to the browser and accepts tuple headers', async () => {
  const body = new FormData();
  body.append('audio', new Blob(['sound']), 'voice.webm');
  const api = client(async (_url, init) => {
    assert.equal(init.body, body);
    assert.equal(init.headers.has('Content-Type'), false);
    assert.equal(init.headers.get('X-Test'), 'yes');
    return json({ data: 1 });
  });
  await api.apiRequest('/audio', schema, {
    method: 'POST', body, headers: [['Content-Type', 'application/json'], ['X-Test', 'yes']],
  });
});

test('HTTP JSON details and status survive; HTML is not shown as a user message', async () => {
  for (const response of [
    json({ detail: 'Недостаточно прав' }, 403, 'application/problem+json'),
    new Response('<html>proxy failed</html>', { status: 502, headers: { 'Content-Type': 'text/html' } }),
    new Response('{broken', { status: 500, headers: { 'Content-Type': 'application/json' } }),
  ]) {
    const api = client(async () => response);
    await assert.rejects(api.apiRequest('/example', schema), (error) => {
      assert.ok(isError(api, 'http', response.status)(error));
      assert.equal(error.message, response.status === 403 ? 'Недостаточно прав' : 'Сервер вернул ошибку ' + response.status);
      return true;
    });
  }
});

test('success with malformed JSON, wrong schema or empty body is not accepted', async () => {
  for (const response of [
    new Response('{broken', { headers: { 'Content-Type': 'application/json' } }),
    json({ data: '42' }), new Response(null, { status: 204 }),
    new Response('<html>unexpected</html>', { headers: { 'Content-Type': 'text/html' } }),
  ]) {
    const api = client(async () => response);
    await assert.rejects(api.apiRequest('/example', schema, { invalidResponseMessage: 'Некорректный результат' }), (error) => {
      assert.ok(isError(api, 'invalid-response', response.status)(error));
      assert.equal(error.message, 'Некорректный результат');
      return true;
    });
  }
});

test('empty success is explicitly accepted by a void schema; vendor JSON is parsed', async () => {
  const api = client(async (url) => url.endsWith('/empty')
    ? new Response(null, { status: 204 }) : json({ data: 9 }, 200, 'application/vnd.test+json; charset=utf-8'));
  assert.equal(await api.apiRequest('/empty', z.void()), undefined);
  assert.equal(await api.apiRequest('/vendor', schema), 9);
});

test('network errors and aborts are distinct; neither triggers an automatic retry', async () => {
  for (const [cause, kind] of [
    [new TypeError('fetch failed'), 'network'],
    [new DOMException('Aborted', 'AbortError'), 'aborted'],
  ]) {
    let calls = 0;
    const api = client(async () => { calls++; throw cause; });
    await assert.rejects(api.apiRequest('/example', schema), (error) => {
      assert.ok(isError(api, kind, null)(error));
      assert.equal(error.cause, cause);
      return true;
    });
    assert.equal(calls, 1);
  }
});

test('concurrent 401 responses renew the session once and replay each request once', async () => {
  let release;
  const renewal = new Promise((resolve) => { release = resolve; });
  let authCalls = 0;
  const requests = [];
  const attempts = new Map();
  const api = client(async (url, init) => {
    if (url.endsWith('/api/auth_tg')) {
      authCalls++;
      assert.deepEqual(JSON.parse(init.body), { init_data: 'test-init-data' });
      return renewal;
    }
    requests.push(init);
    const count = (attempts.get(url) ?? 0) + 1;
    attempts.set(url, count);
    return count === 1 ? json({}, 401) : json({ data: 42 });
  });
  const body = new FormData();
  body.append('audio', new Blob(['sound']));
  const first = api.apiRequest('/first', schema, { method: 'POST', body });
  const second = api.apiRequest('/second', schema, { method: 'POST', json: { value: 1 } });
  for (let i = 0; i < 10; i++) await Promise.resolve();
  assert.equal(authCalls, 1);
  release(json(true));
  assert.deepEqual(await Promise.all([first, second]), [42, 42]);
  assert.equal(requests.length, 4);
  assert.equal(requests[0].body, requests[2].body);
  assert.equal(requests[1].body, requests[3].body);
});

test('failed renewal or a second 401 cannot cause a retry loop', async () => {
  for (const accepted of [false, true]) {
    let calls = 0;
    let authCalls = 0;
    const api = client(async (url) => {
      if (url.endsWith('/api/auth_tg')) { authCalls++; return json(accepted); }
      calls++;
      return json({ detail: 'Требуется вход' }, 401);
    });
    await assert.rejects(api.apiRequest('/example', schema), isError(api, 'http', 401));
    assert.equal(authCalls, 1);
    assert.equal(calls, accepted ? 2 : 1);
  }
});

test('authentication itself uses validation and never attempts recursive renewal', async () => {
  let calls = 0;
  const api = client(async () => { calls++; return json('true'); });
  await assert.rejects(api.authenticateTelegramSession('test'), isError(api, 'invalid-response', 200));
  assert.equal(calls, 1);
});

test('word answer contract validates ordinary answers and skips separately', async () => {
  const invalid = [
    {}, { data: {} }, { data: { is_correct: null } }, { data: { is_correct: 'true' } },
    { data: { is_correct: true, success: false } }, { data: { skip: true } },
    { data: { is_correct: true, has_typo: true, typo: null } },
    { data: { is_correct: true, typo: { index: -1, type: 'extra' } } },
    { data: null, correct: true },
  ];
  for (const body of invalid) {
    const api = load('src/features/practice/api/practiceApi.ts', config, { fetch: async () => json(body) });
    await assert.rejects(api.sendPracticeAnswer({
      wordId: 42, answerLanguage: 'ru', textAnswer: 'яблоко', recordedAudio: null, skip: false,
    }), (error) => error.kind === 'invalid-response');
  }
  const api = load('src/features/practice/api/practiceApi.ts', config, {
    fetch: async () => json({ data: { skip: true, is_correct: null, future: true } }),
  });
  const result = await api.sendPracticeAnswer({
    wordId: 42, answerLanguage: 'ru', textAnswer: '', recordedAudio: null, skip: true,
  });
  assert.equal(result.answerSkipped, true);
  assert.equal(result.answerStatus, null);
});

test('manual review validates confirmation for the requested word', async () => {
  for (const data of [{}, { id: 43, status: 'manual_review' }, { id: 42, status: 'approved' }]) {
    const api = load('src/features/practice/api/practiceApi.ts', config, { fetch: async () => json({ data }) });
    await assert.rejects(api.sendWordToManualReview(42), (error) => error.kind === 'invalid-response');
  }
});

test('settings share transport, validation, JSON updates and structured errors', async () => {
  const settings = {
    selected_language_level_id: 1, system_language_level_id: null,
    reminders_enabled: true, timezone: 'Asia/Tbilisi', reminder_time: '12:00',
  };
  const stored = new Map();
  let status = 200;
  const api = load('src/shared/settings/userSettings.ts', config, {
    localStorage: { setItem: (key, value) => stored.set(key, value) },
    fetch: async (_url, init) => {
      assert.equal(init.headers.get('Content-Type'), 'application/json');
      assert.equal(JSON.parse(init.body).timezone, 'Asia/Tbilisi');
      return status === 200 ? json({ data: settings }) : json({ detail: 'Нет доступа' }, status);
    },
  });
  assert.equal((await api.updateAndStoreUserSettings(settings)).timezone, 'Asia/Tbilisi');
  assert.equal(JSON.parse(stored.get('user_settings')).reminders_enabled, true);
  status = 403;
  await assert.rejects(api.updateAndStoreUserSettings(settings), (error) =>
    error.kind === 'http' && error.status === 403 && error.message === 'Нет доступа');
});
