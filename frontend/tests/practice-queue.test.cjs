const assert = require('node:assert/strict');
const { test } = require('node:test');
const vue = require('vue');
const { load } = require('./helpers/loadFrontend.cjs');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function fixture({ fetchIds = async () => [1, 2, 3], fetchWord = async (id) => ({ id, word: 'word' }) } = {}) {
  const session = vue.shallowRef({ userId: 101, id: 1 });
  const notifications = [];
  const removedKeys = [];
  let requests = 0;
  const imports = {
    '@/shared/auth/session': { authenticatedSession: session },
    '@/features/practice/api/practiceApi': {
      fetchIntervalRepetitionWordIds: () => { requests++; return fetchIds(); },
      fetchRepeatWord: fetchWord,
    },
    '@/shared/notifications/useNotificationCenter': {
      useNotificationCenter: () => ({ addNotification: (value) => notifications.push(value) }),
    },
  };
  const globals = {
    localStorage: { removeItem: (key) => removedKeys.push(key), getItem() { assert.fail('Must not restore persisted queue'); } },
    sessionStorage: { removeItem: (key) => removedKeys.push(key), getItem() { assert.fail('Must not restore persisted flag'); } },
  };
  const queueModule = load('src/features/practice/composables/useIntervalRepetitionQueue.ts', imports, globals);
  return {
    session, imports, globals, queueModule, notifications, removedKeys,
    get requests() { return requests; },
  };
}

test('queue belongs to a user/session and concurrent consumers share one load', async () => {
  const response = deferred();
  const h = fixture({ fetchIds: () => response.promise });
  const a = h.queueModule.useIntervalRepetitionQueue();
  const b = h.queueModule.useIntervalRepetitionQueue();
  const visit = a.beginVisit();
  assert.equal(visit.owner.userId, 101);
  const first = a.loadOnce(visit);
  const second = b.loadOnce(visit);
  response.resolve([42, 42]);
  await Promise.all([first, second]);
  assert.equal(h.requests, 1);
  a.removeWordId(visit, 42);
  assert.equal(b.getRandomWordId(visit), null);
  await b.loadOnce(visit);
  assert.equal(h.requests, 1);
  assert.equal(h.notifications.length, 1);
  assert.deepEqual(h.removedKeys, [
    'practice:interval-repetition-word-ids', 'practice:interval-repetitions-requested',
  ]);
});

test('leaving discards the queue; reopening loads a fresh list', async () => {
  let ids = [42];
  const h = fixture({ fetchIds: async () => ids });
  const queue = h.queueModule.useIntervalRepetitionQueue();
  const first = queue.beginVisit();
  await queue.loadOnce(first);
  queue.endVisit(first);
  assert.equal(first.wordIds.length, 0);
  assert.throws(() => queue.getRandomWordId(first), (error) => error.kind === 'aborted');
  ids = [43];
  const second = queue.beginVisit();
  await queue.loadOnce(second);
  assert.equal(queue.getRandomWordId(second), 43);
  assert.equal(h.requests, 2);
});

test('a late old load cannot overwrite the new visit or its pending request', async () => {
  const firstResponse = deferred();
  const secondResponse = deferred();
  let count = 0;
  const h = fixture({ fetchIds: () => ++count === 1 ? firstResponse.promise : secondResponse.promise });
  const queue = h.queueModule.useIntervalRepetitionQueue();
  const first = queue.beginVisit();
  const firstLoading = queue.loadOnce(first);
  const rejected = assert.rejects(firstLoading, (error) => error.kind === 'aborted');
  queue.endVisit(first);
  const second = queue.beginVisit();
  const secondLoading = queue.loadOnce(second);
  firstResponse.resolve([42]);
  await rejected;
  const anotherConsumer = queue.loadOnce(second);
  assert.equal(h.requests, 2);
  secondResponse.resolve([43]);
  await Promise.all([secondLoading, anotherConsumer]);
  assert.equal(queue.getRandomWordId(second), 43);
  queue.endVisit(first);
  assert.equal(queue.getRandomWordId(second), 43);
  assert.equal(h.notifications.length, 0);
});

test('both user changes and new sessions of the same user invalidate previous data', async () => {
  for (const owner of [{ userId: 202, id: 2 }, { userId: 101, id: 2 }]) {
    const h = fixture({ fetchIds: async () => [42] });
    const queue = h.queueModule.useIntervalRepetitionQueue();
    const visit = queue.beginVisit();
    await queue.loadOnce(visit);
    h.session.value = owner;
    assert.throws(() => queue.getRandomWordId(visit), (error) => error.kind === 'aborted');
    assert.throws(() => queue.removeWordId(visit, 42), (error) => error.kind === 'aborted');
    assert.equal(h.notifications.length, 0);
    const next = queue.beginVisit();
    await queue.loadOnce(next);
    assert.equal(next.owner.userId, owner.userId);
    assert.equal(h.requests, 2);
  }
});

test('load failures can retry, empty results do not trigger repeated loads', async () => {
  let fail = true;
  const h = fixture({ fetchIds: async () => {
    if (fail) throw new Error('Нет сети');
    return [];
  } });
  const queue = h.queueModule.useIntervalRepetitionQueue();
  const visit = queue.beginVisit();
  await assert.rejects(queue.loadOnce(visit), /Нет сети/);
  fail = false;
  await queue.loadOnce(visit);
  await queue.loadOnce(visit);
  assert.equal(h.requests, 2);
  assert.equal(queue.getRandomWordId(visit), null);
  assert.equal(h.notifications.length, 0);
});

test('blocked browser storage does not prevent queue operation', async () => {
  const h = fixture({ fetchIds: async () => [42] });
  h.globals.localStorage.removeItem = () => { throw new Error('Blocked'); };
  h.globals.sessionStorage.removeItem = () => { throw new Error('Blocked'); };
  const queue = h.queueModule.useIntervalRepetitionQueue();
  const visit = queue.beginVisit();
  await queue.loadOnce(visit);
  assert.equal(queue.getRandomWordId(visit), 42);
});

function mountRepeat(t, h) {
  const { useRepeatSession } = load('src/features/practice/composables/useRepeatSession.ts', {
    ...h.imports,
    '@/features/practice/composables/useIntervalRepetitionQueue': h.queueModule,
  }, h.globals);
  const mode = vue.ref('repeat');
  let repeat;
  const renderer = vue.createRenderer({
    createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null,
  });
  const app = renderer.createApp({
    setup() { repeat = useRepeatSession(() => mode.value); return () => null; },
  });
  app.mount({});
  t.after(() => app.unmount());
  return { repeat, mode, unmount: () => app.unmount() };
}

test('mode changes reload on return, not on each next word', async (t) => {
  const h = fixture();
  const { repeat, mode } = mountRepeat(t, h);
  await repeat.preloadIntervalRepetitions();
  await repeat.requestNextWord();
  await repeat.requestNextWord();
  assert.equal(h.requests, 1);
  mode.value = 'learn';
  mode.value = 'repeat';
  await repeat.preloadIntervalRepetitions();
  assert.equal(h.requests, 2);
});

test('page unmount invalidates a pending word and suppresses progress notifications', async (t) => {
  const response = deferred();
  const h = fixture({ fetchIds: async () => [42], fetchWord: () => response.promise });
  const { repeat, unmount } = mountRepeat(t, h);
  await repeat.preloadIntervalRepetitions();
  const requesting = repeat.requestNextWord();
  for (let i = 0; i < 5; i++) await Promise.resolve();
  unmount();
  response.resolve({ id: 42, word: 'old' });
  await assert.rejects(requesting, (error) => error.kind === 'aborted');
  assert.equal(h.notifications.length, 0);
});

test('new authentication resets the active visit even for the same user', async (t) => {
  const h = fixture({ fetchIds: async () => [42] });
  const { repeat } = mountRepeat(t, h);
  await repeat.preloadIntervalRepetitions();
  h.session.value = { userId: 101, id: 2 };
  await repeat.preloadIntervalRepetitions();
  assert.equal(h.requests, 2);
});

test('reminder requires a queue, ordinary repetition retains server fallback', async (t) => {
  const wordIds = [];
  const h = fixture({ fetchIds: async () => [], fetchWord: async (id) => {
    wordIds.push(id); return { id: 42, word: 'word' };
  } });
  const { repeat } = mountRepeat(t, h);
  await assert.rejects(repeat.requestNextWord({ requireIntervalRepetitions: true }),
    /нет слов для интервального повторения/);
  assert.equal(wordIds.length, 0);
  await repeat.requestNextWord();
  assert.deepEqual(wordIds, [null]);
  assert.equal(h.requests, 1);
});

test('session identity is parsed only as a local tag and changes on each login', () => {
  const auth = load('src/shared/auth/session.ts');
  const data = new URLSearchParams({ user: JSON.stringify({ id: 101, first_name: 'Test' }) }).toString();
  auth.startAuthenticatedSession(data);
  const first = auth.authenticatedSession.value;
  assert.equal(first.userId, 101);
  auth.startAuthenticatedSession(data);
  assert.notEqual(auth.authenticatedSession.value.id, first.id);
  auth.clearAuthenticatedSession();
  assert.equal(auth.authenticatedSession.value, null);
  auth.startAuthenticatedSession('user=invalid-json');
  assert.equal(auth.authenticatedSession.value.userId, null);
});

test('failed login never attaches a user; successful login starts a new local session', async () => {
  for (const accepted of [false, true]) {
    const events = [];
    const api = load('src/shared/api/auth.ts', {
      '@/shared/api/client': { authenticateTelegramSession: async () => accepted },
      '@/shared/auth/session': {
        clearAuthenticatedSession: () => events.push('clear'),
        startAuthenticatedSession: (data) => events.push(data),
      },
    });
    assert.equal(await api.authenticateTelegram('init-data'), accepted);
    assert.deepEqual(events, accepted ? ['clear', 'init-data'] : ['clear']);
  }
});

function mountPractice(t, h) {
  const props = vue.reactive({ mode: 'repeat' });
  const component = load('src/views/PracticeView.vue', {
    ...h.imports,
    '@/features/practice/composables/useIntervalRepetitionQueue': h.queueModule,
    '@/shared/config': { BACKEND_URL: 'https://example.test' },
    '@lucide/vue': {},
    'vue-router': {
      useRoute: () => ({ query: {} }),
      useRouter: () => ({ replace: async () => {} }),
    },
  }, {
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  }).default;
  let state;
  const renderer = vue.createRenderer({
    createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null,
  });
  const app = renderer.createApp({
    setup() {
      state = component.setup(props, { expose() {} }).session;
      return () => null;
    },
  });
  app.mount({});
  t.after(() => app.unmount());
  return { state, props, unmount: () => app.unmount() };
}

test('PracticeView loads on each entry and shares the initial request with Start', async (t) => {
  const h = fixture({ fetchIds: async () => [42] });
  const { state, props } = mountPractice(t, h);
  assert.equal(h.requests, 1);
  await state.startRepeating();
  assert.equal(h.requests, 1);
  props.mode = 'learn';
  assert.equal(h.requests, 1);
  props.mode = 'repeat';
  assert.equal(h.requests, 2);
  await state.requestWord();
  assert.equal(h.requests, 2);
});

test('a previous visit cannot replace the new card or clear its loading state', async (t) => {
  const oldWord = deferred();
  const oldStarted = deferred();
  let count = 0;
  const h = fixture({
    fetchIds: async () => [42],
    fetchWord: async () => {
      if (++count === 1) { oldStarted.resolve(); return oldWord.promise; }
      return { id: 43, word: 'new', answerLanguage: null };
    },
  });
  const { state, props } = mountPractice(t, h);
  const first = state.requestWord();
  await oldStarted.promise;
  props.mode = 'learn';
  props.mode = 'repeat';
  await state.requestWord();
  assert.equal(state.currentWord.value.id, 43);
  oldWord.resolve({ id: 42, word: 'old', answerLanguage: null });
  await first;
  assert.equal(state.currentWord.value.id, 43);
  assert.equal(state.errorMessage.value, null);
  assert.equal(state.isLoading.value, false);
});

test('a late queue response after unmount never causes a fallback word request', async (t) => {
  const response = deferred();
  let words = 0;
  const h = fixture({
    fetchIds: () => response.promise,
    fetchWord: async () => { words++; return { id: 42, word: 'word' }; },
  });
  const { repeat, unmount } = mountRepeat(t, h);
  const requesting = repeat.requestNextWord();
  const rejected = assert.rejects(requesting, (error) => error.kind === 'aborted');
  unmount();
  response.resolve([42]);
  await rejected;
  assert.equal(words, 0);
  assert.equal(h.notifications.length, 0);
});
