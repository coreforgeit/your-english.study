const assert = require('node:assert/strict');
const { test } = require('node:test');
const vue = require('vue');
const { load } = require('./helpers/loadFrontend.cjs');

const word = {
  id: 42, word: 'apple', translations: ['яблоко'], pronunciation: null,
  partOfSpeech: null, audioUrl: null, level: null, answerLanguage: null,
};
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});
const pending = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const plain = (value) => JSON.parse(JSON.stringify(value));

function mountSession(t, { mode = 'repeat', onRequest, autoStart = false, stored = new Map() } = {}) {
  const requests = [];
  const routeChanges = [];
  const props = vue.reactive({ mode });
  let preloadCount = 0;
  let reloadCount = 0;
  const component = load('src/views/PracticeView.vue', {
    '@lucide/vue': {},
    'vue-router': {
      useRoute: () => ({ query: autoStart ? { autoStart: 'true' } : {} }),
      useRouter: () => ({ replace: async (route) => { routeChanges.push(route); } }),
    },
    '@/shared/config': { BACKEND_URL: 'https://example.test' },
    '@/features/practice/composables/useIntervalRepetitionQueue': {
      useIntervalRepetitionQueue: () => ({
        loadOnce: async () => { preloadCount++; },
        reload: async () => { reloadCount++; },
        getRandomWordId: () => 43, removeWordId() {},
      }),
    },
  }, {
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (onRequest) return onRequest(url, options);
      return json({ data: { id: 43, word: 'pear', translations: ['груша'] } });
    },
    sessionStorage: {
      getItem: (key) => stored.get(key) ?? null,
      setItem: (key, value) => stored.set(key, value),
      removeItem: (key) => stored.delete(key),
    },
  }).default;
  const renderer = vue.createRenderer({
    createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null,
  });
  let state;
  let view;
  const app = renderer.createApp({
    setup() {
      view = component.setup(props, { expose() {} });
      state = view.session;
      return () => null;
    },
  });
  app.mount({});
  state.currentState.value.word ??= { ...word };
  t.after(() => app.unmount());
  return {
    state, view, requests, stored, props, routeChanges, unmount: () => app.unmount(),
    get preloadCount() { return preloadCount; },
    get reloadCount() { return reloadCount; },
  };
}

test('text answer keeps the wire format and maps the answer into the session', async (t) => {
  const h = mountSession(t, { onRequest: async () => json({ data: {
    is_correct: false, answer: 'яблако', correct_answer: ['яблоко'], comment: '  Подсказка  ',
    has_typo: true, typo: { index: 3, type: 'replace', expected: 'о', actual: 'а' },
  } }) });
  h.state.currentState.value.answerText = '  яблако  ';
  await h.state.submitCurrentAnswer();
  assert.deepEqual(JSON.parse(h.requests[0].options.body), {
    word_id: 42, answer_type: 'text', answer_language: 'ru', text_answer: 'яблако', skip: false,
  });
  const state = h.state.currentState.value;
  assert.equal(state.answerStatus, 'incorrect');
  assert.equal(state.submittedAnswer, 'яблако');
  assert.equal(state.answerTypo.type, 'replace');
  assert.deepEqual(plain(state.correctAnswers), ['яблоко']);
  assert.equal(state.answerComment, 'Подсказка');
  assert.equal(state.answerText, '');
  assert.equal(state.answerSubmitted, true);
  assert.equal(state.showAnswer, true);
  assert.equal(h.state.isSendingAnswer.value, false);
});

test('regular skip still sends skip=true without text or audio', async (t) => {
  const h = mountSession(t, { onRequest: async () => json({ data: { skip: true } }) });
  h.state.currentState.value.recordedAudio = new Blob(['voice']);
  await h.state.handleNextButton();
  assert.deepEqual(JSON.parse(h.requests[0].options.body), {
    word_id: 42, answer_type: 'text', answer_language: 'ru', skip: true,
  });
  assert.equal(h.state.currentState.value.answerSkipped, true);
});

test('voice timeout skip only loads a word and ignores the late answer', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const answer = pending();
  const h = mountSession(t, { onRequest: (url) => url.endsWith('/answer')
    ? answer.promise : json({ data: { id: 43, word: 'pear' } }) });
  h.state.currentState.value.recordedAudio = new Blob(['voice'], { type: 'audio/webm' });
  const sending = h.state.submitCurrentAnswer();
  assert.equal(h.state.voiceAnswerDialogState.value, 'checking');
  const form = h.requests[0].options.body;
  assert.equal(form.get('word_id'), '42');
  assert.equal(form.get('answer_type'), 'audio');
  assert.equal(form.get('answer_language'), 'ru');
  assert.equal(form.get('audio_file').name, 'answer.webm');
  t.mock.timers.tick(9_999);
  assert.equal(h.state.voiceAnswerDialogState.value, 'checking');
  t.mock.timers.tick(1);
  assert.equal(h.state.voiceAnswerDialogState.value, 'error');
  await h.state.skipTimedOutVoiceAnswer();
  assert.equal(h.requests.length, 2);
  assert.ok(h.requests[1].url.endsWith('/repeat'));
  assert.equal(h.state.currentWord.value.id, 43);
  answer.resolve(json({ data: { is_correct: true, answer: 'old answer' } }));
  await sending;
  assert.equal(h.state.currentState.value.answerSubmitted, false);
  assert.equal(h.state.currentState.value.submittedAnswer, '');
  assert.equal(h.state.voiceAnswerDialogState.value, 'hidden');
});

test('retry sends the same blob; an older response cannot replace the retry result', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const first = pending();
  let count = 0;
  const h = mountSession(t, { onRequest: () => ++count === 1
    ? first.promise : json({ data: { is_correct: true, answer: 'яблоко' } }) });
  h.state.currentState.value.recordedAudio = new Blob(['voice']);
  const firstSending = h.state.submitCurrentAnswer();
  t.mock.timers.tick(10_000);
  await h.state.retryVoiceAnswer();
  assert.equal(h.requests.length, 2);
  assert.equal(await h.requests[1].options.body.get('audio_file').text(), 'voice');
  assert.equal(h.state.currentState.value.answerStatus, 'correct');
  first.resolve(json({ data: { is_correct: false } }));
  await firstSending;
  assert.equal(h.state.currentState.value.answerStatus, 'correct');
});

test('voice HTTP error preserves the blob and exposes the retry dialog', async (t) => {
  const h = mountSession(t, { onRequest: () => json({ detail: 'Ошибка проверки' }, 503) });
  h.state.currentState.value.recordedAudio = new Blob(['voice']);
  await h.state.submitCurrentAnswer();
  assert.equal(h.state.voiceAnswerDialogState.value, 'error');
  assert.match(h.state.answerDebugReport.value, /HTTP=503/);
  assert.match(h.state.answerDebugReport.value, /Ошибка проверки/);
  assert.equal(h.state.currentState.value.recordedAudio.size, 5);
  assert.equal(h.state.isSendingAnswer.value, false);
});

test('unmount invalidates an in-flight answer', async (t) => {
  const answer = pending();
  const h = mountSession(t, { onRequest: () => answer.promise });
  h.state.currentState.value.answerText = 'яблоко';
  const sending = h.state.submitCurrentAnswer();
  h.unmount();
  answer.resolve(json({ data: { is_correct: true } }));
  await sending;
  assert.equal(h.state.currentState.value.answerSubmitted, false);
});

test('manual review uses PATCH and only marks successfully submitted words', async (t) => {
  let status = 503;
  const h = mountSession(t, { onRequest: () => status === 200 ? json({ data: { id: 42, status: 'manual_review' } }) : json({ detail: 'Позже' }, status) });
  await h.state.sendCurrentWordToManualReview();
  assert.equal(h.state.manuallyReviewedWordIds.value.has(42), false);
  assert.equal(h.state.errorMessage.value, 'Позже');
  status = 200;
  await h.state.sendCurrentWordToManualReview();
  assert.equal(h.requests[1].options.method, 'PATCH');
  assert.ok(h.requests[1].url.endsWith('/words/42/manual-review'));
  assert.equal(h.state.manuallyReviewedWordIds.value.has(42), true);
  assert.equal(h.state.manualReviewLoadingWordId.value, null);
});

test('changing modes preserves separate cards and updates start dialogs', async (t) => {
  const h = mountSession(t);
  h.state.currentState.value.answerText = 'черновик';
  h.props.mode = 'learn';
  await vue.nextTick();
  assert.equal(h.state.currentWord.value, null);
  assert.equal(h.state.showLearnStartDialog.value, true);
  await h.state.startLearning();
  assert.equal(h.state.currentWord.value.id, 43);
  assert.equal(h.state.currentState.value.answerSubmitted, true);
  h.props.mode = 'repeat';
  await vue.nextTick();
  assert.equal(h.state.currentWord.value.id, 42);
  assert.equal(h.state.currentState.value.answerText, 'черновик');
});

test('reminder entry clears the route query and reloads the repetition queue', async (t) => {
  const h = mountSession(t, { autoStart: true });
  for (let i = 0; i < 20; i++) await Promise.resolve();
  assert.deepEqual(plain(h.routeChanges), [{ name: 'repeat' }]);
  assert.equal(h.preloadCount, 0);
  assert.equal(h.reloadCount, 1);
  assert.equal(h.state.showRepeatStartDialog.value, false);
  assert.equal(h.requests.length, 1);
});

test('storage round-trip excludes audio and keeps defaults for older cache entries', () => {
  const stored = new Map();
  const storage = load('src/features/practice/practiceStorage.ts', { '@/shared/api/client': {} }, {
    sessionStorage: {
      getItem: (key) => stored.get(key) ?? null,
      setItem: (key, value) => stored.set(key, value),
      removeItem: (key) => stored.delete(key),
    },
  });
  const state = {
    word, displayDirection: 'en-ru', showAnswer: true, answerSubmitted: true,
    answerText: '', answerStatus: 'correct', answerTypo: null, submittedAnswer: 'яблоко',
    recordedAudio: new Blob(['voice']),
  };
  storage.saveRepeatSessionState(state);
  assert.equal(stored.get('practice:last-repeat-state').includes('recordedAudio'), false);
  const restored = storage.restoreRepeatSessionState();
  assert.equal(restored.recordedAudio, null);
  assert.equal(restored.answerSkipped, false);
  assert.deepEqual(plain(restored.correctAnswers), []);
  assert.equal(restored.answerComment, null);
  storage.saveLearnSessionWord(word, 'en-ru');
  assert.equal(storage.restoreLearnSessionWord().word.id, 42);
});

test('blocked browser storage does not prevent restore or save', () => {
  const globals = {};
  Object.defineProperty(globals, 'sessionStorage', { enumerable: true, value: {
    getItem() { throw new DOMException('Blocked', 'SecurityError'); },
    setItem() { throw new DOMException('Blocked', 'SecurityError'); },
    removeItem() { throw new DOMException('Blocked', 'SecurityError'); },
  } });
  const storage = load('src/features/practice/practiceStorage.ts', { '@/shared/api/client': {} }, globals);
  assert.equal(storage.restoreLearnSessionWord(), null);
  assert.equal(storage.restoreRepeatSessionState(), null);
  assert.doesNotThrow(() => storage.saveLearnSessionWord(word, 'en-ru'));
});

test('answer mapper uses validated data and retains legacy correct and fallback text', () => {
  const { normalizeAnswer } = load('src/features/practice/api/practiceMappers.ts');
  const { answerResponseSchema } = load('src/features/practice/api/practiceSchemas.ts');
  const data = answerResponseSchema(false).parse({
    correct: true, correct_answer: ['', 'one', 'two', 'three', 'four'], comment: '  ',
  });
  const result = normalizeAnswer(data, 'fallback');
  assert.equal(result.answerStatus, 'correct');
  assert.equal(result.answerTypo, null);
  assert.equal(result.submittedAnswer, 'fallback');
  assert.equal(result.answerComment, null);
  assert.deepEqual(plain(result.correctAnswers), ['one', 'two', 'three']);
});

test('answer formatting preserves Unicode, missing, extra and replaced letters', () => {
  const { buildAnswerParts } = load('src/features/practice/answerFormatting.ts');
  assert.equal(buildAnswerParts('😀a', null, 'submitted').length, 2);
  for (const type of ['missing', 'extra', 'replace']) {
    const typo = { index: 1, type, expected: 'b', actual: 'a' };
    const parts = buildAnswerParts('cat', typo, 'submitted');
    assert.equal(parts[1].state, type);
    assert.equal(parts.length, type === 'missing' ? 4 : 3);
    assert.equal(typo.index, 1);
  }
  assert.equal(buildAnswerParts('cat', { index: 1, type: 'missing', expected: 'a' }, 'correct-0')[1].state, 'expected');
});

for (const answerType of ['text', 'audio']) {
  test(`invalid ${answerType} result keeps the answer available for retry`, async (t) => {
    let valid = false;
    const h = mountSession(t, { onRequest: () => json({ data: valid
      ? { is_correct: true, answer: 'яблоко', new_field: 'allowed' }
      : { answer: 'яблоко' } }) });
    h.state.currentState.value.answerText = 'яблоко';
    if (answerType === 'audio') h.state.currentState.value.recordedAudio = new Blob(['voice']);
    await h.state.submitCurrentAnswer();
    assert.equal(h.state.currentState.value.answerSubmitted, false);
    assert.equal(h.state.currentState.value.showAnswer, false);
    assert.equal(h.state.currentState.value.answerText, 'яблоко');
    assert.equal(h.state.isSendingAnswer.value, false);
    if (answerType === 'audio') {
      assert.equal(h.state.voiceAnswerDialogState.value, 'error');
      assert.equal(h.state.currentState.value.recordedAudio.size, 5);
    } else {
      assert.match(h.state.errorMessage.value, /результат проверки/);
    }
    valid = true;
    await (answerType === 'audio' ? h.state.retryVoiceAnswer() : h.state.submitCurrentAnswer());
    assert.equal(h.state.currentState.value.answerStatus, 'correct');
    assert.equal(h.state.currentState.value.answerSubmitted, true);
  });
}
