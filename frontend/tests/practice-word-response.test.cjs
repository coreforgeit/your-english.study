const assert = require('node:assert/strict');
const { test } = require('node:test');
const vue = require('vue');
const { load } = require('./helpers/loadFrontend.cjs');

function createApi(body, status = 200) {
  return load('src/features/practice/api/practiceApi.ts', {
    zod: require('zod'),
    '@/shared/config': { BACKEND_URL: 'https://example.test' },
  }, {
    fetch: async () => new Response(JSON.stringify(body), {
      status, headers: { 'Content-Type': 'application/json' },
    }),
  });
}

const invalidResponses = [
  ['missing id', { data: { word: 'apple' } }],
  ['null id', { data: { id: null, word: 'apple' } }],
  ['string id', { data: { id: '42', word: 'apple' } }],
  ['zero id', { data: { id: 0, word: 'apple' } }],
  ['negative id', { data: { id: -1, word: 'apple' } }],
  ['fractional id', { data: { id: 1.5, word: 'apple' } }],
  ['missing word', { data: { id: 42 } }],
  ['null word', { data: { id: 42, word: null } }],
  ['numeric word', { data: { id: 42, word: 123 } }],
  ['empty word', { data: { id: 42, word: '' } }],
  ['whitespace word', { data: { id: 42, word: ' \t\n ' } }],
  ['missing envelope', { id: 42, word: 'apple' }],
  ['null data', { data: null }],
  ['array data', { data: [] }],
  ['null response', null],
];

for (const [label, body] of invalidResponses) {
  test(`both word endpoints reject ${label}`, async () => {
    const api = createApi(body);
    for (const request of [() => api.fetchLearnWord(), () => api.fetchRepeatWord(42)]) {
      await assert.rejects(request, (error) => {
        assert.equal(error.message, 'Не удалось загрузить слово. Попробуйте ещё раз.');
        assert.ok(error.cause instanceof require('zod').ZodError);
        return true;
      });
    }
  });
}

test('required fields suffice; optional fields are mapped and new fields are tolerated', async () => {
  for (const data of [
    { id: 42, word: 'apple' },
    { id: 42, word: 'apple', audio_url: '/apple.mp3', translations: ['яблоко'], future_field: true },
  ]) {
    const api = createApi({ data });
    for (const result of [await api.fetchLearnWord(), await api.fetchRepeatWord(42)]) {
      assert.equal(result.id, data.id);
      assert.equal(result.word, data.word);
      assert.equal(result.audioUrl, data.audio_url ?? null);
    }
  }
});

test('HTTP failures retain status and backend error details', async () => {
  const api = createApi({ detail: 'Word not found' }, 404);
  await assert.rejects(() => api.fetchLearnWord(), (error) => {
    assert.equal(error.kind, 'http');
    assert.equal(error.status, 404);
    assert.equal(error.responseData.detail, 'Word not found');
    return true;
  });
});

function mountPractice(t, { mode = 'repeat', responses = [], stored = new Map() } = {}) {
  const removedIds = [];
  const component = load('src/views/PracticeView.vue', {
    vue, '@lucide/vue': {},
    'vue-router': { useRoute: () => ({ query: {} }), useRouter: () => ({ replace: async () => {} }) },
    '@/shared/config': { BACKEND_URL: 'https://example.test' },
    '@/features/practice/composables/useIntervalRepetitionQueue': {
      useIntervalRepetitionQueue: () => ({
        loadOnce: async () => {}, reload: async () => {},
        getRandomWordId: () => 42, removeWordId: (id) => removedIds.push(id),
      }),
    },
  }, {
    fetch: async () => {
      assert.ok(responses.length, 'Unexpected word request');
      return new Response(JSON.stringify(responses.shift()), {
        headers: { 'Content-Type': 'application/json' },
      });
    },
    sessionStorage: {
      getItem: (key) => stored.get(key) ?? null,
      setItem: (key, value) => stored.set(key, value),
      removeItem: (key) => stored.delete(key),
    },
  }).default;
  let state;
  const renderer = vue.createRenderer({
    createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null,
  });
  const app = renderer.createApp({
    setup() {
      state = component.setup({ mode }, { expose() {} }).session;
      return () => null;
    },
  });
  app.mount({});
  t.after(() => app.unmount());
  return { state, removedIds, stored };
}

for (const mode of ['learn', 'repeat']) {
  test(`${mode}: invalid first response shows an error; next click can retry`, async (t) => {
    const h = mountPractice(t, { mode, responses: [
      { data: { word: 'invalid' } },
      { data: { id: 42, word: 'apple', audio_url: '/apple.mp3' } },
    ] });
    await h.state.requestWord();
    assert.equal(h.state.currentState.value.word, null);
    assert.equal(h.state.errorMessage.value, 'Не удалось загрузить слово. Попробуйте ещё раз.');
    assert.equal(h.state.isLoading.value, false);
    assert.deepEqual(h.removedIds, []);
    assert.equal(h.stored.size, 0);
    await h.state.handleNextButton();
    assert.equal(h.state.currentState.value.word.id, 42);
    assert.equal(h.state.currentState.value.word.word, 'apple');
    assert.equal(h.state.currentState.value.word.audioUrl, '/apple.mp3');
    assert.equal(h.state.errorMessage.value, null);
    assert.deepEqual(h.removedIds, mode === 'repeat' ? [42] : []);
  });

  test(`${mode}: invalid response preserves the previous valid card`, async (t) => {
    const h = mountPractice(t, { mode, responses: [
      { data: { id: 42, word: 'apple' } },
      { data: { id: null, word: 'broken' } },
    ] });
    await h.state.requestWord();
    const previousWord = h.state.currentState.value.word;
    await h.state.requestWord();
    assert.equal(h.state.currentState.value.word, previousWord);
    assert.equal(h.state.isLoading.value, false);
    assert.deepEqual(h.removedIds, mode === 'repeat' ? [42] : []);
  });

  test(`${mode}: old cached placeholder is discarded`, (t) => {
    const key = mode === 'learn' ? 'practice:last-learn-word' : 'practice:last-repeat-state';
    const stored = new Map([[key, JSON.stringify({
      word: {
        id: null, word: 'Ответ без слова', pronunciation: null, translations: [],
        partOfSpeech: null, audioUrl: null, level: null, answerLanguage: null,
      },
      displayDirection: 'en-ru', showAnswer: false, answerSubmitted: false,
      answerText: '', answerStatus: null, answerTypo: null, submittedAnswer: '',
    })]]);
    const h = mountPractice(t, { mode, stored });
    assert.equal(h.state.currentState.value.word, null);
    assert.equal(h.stored.has(key), false);
  });
}
