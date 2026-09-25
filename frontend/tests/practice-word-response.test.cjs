const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const vue = require('vue');
const { parse, compileScript } = require('vue/compiler-sfc');

const frontendRoot = path.resolve(__dirname, '..');
const quietConsole = { log() {}, warn() {}, error() {} };
const sources = new Map();

function load(relativePath, imports, globals = {}) {
  if (!sources.has(relativePath)) {
    let source = readFileSync(path.join(frontendRoot, relativePath), 'utf8');
    if (relativePath.endsWith('.vue')) {
      source = compileScript(parse(source).descriptor, { id: 'word-response-test' }).content;
    }
    sources.set(relativePath, ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText);
  }
  const exports = {};
  vm.runInNewContext(sources.get(relativePath), {
    exports, Error, console: quietConsole, ...globals,
    require(name) {
      assert.ok(name in imports, `Unexpected import: ${name}`);
      return imports[name];
    },
  });
  return exports;
}

function createApi(body, status = 200) {
  return load('src/features/practice/api/practiceApi.ts', {
    zod: require('zod'),
    '@/shared/api/client': {
      BACKEND_URL: 'https://example.test',
      authorizedFetch: async () => new Response(JSON.stringify(body), {
        status, headers: { 'Content-Type': 'application/json' },
      }),
    },
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

test('required fields suffice; optional and new fields are preserved', async () => {
  for (const data of [
    { id: 42, word: 'apple' },
    { id: 42, word: 'apple', audio_url: '/apple.mp3', translations: ['яблоко'], future_field: true },
  ]) {
    const api = createApi({ data });
    for (const result of [await api.fetchLearnWord(), await api.fetchRepeatWord(42)]) {
      assert.equal(JSON.stringify(result.data), JSON.stringify(data));
    }
  }
});

test('HTTP failures retain status and backend error details', async () => {
  const api = createApi({ detail: 'Word not found' }, 404);
  await assert.rejects(() => api.fetchLearnWord(), (error) => {
    assert.ok(error instanceof api.PracticeApiError);
    assert.equal(error.status, 404);
    assert.equal(error.responseData.detail, 'Word not found');
    return true;
  });
});

function mountPractice(t, { mode = 'repeat', responses = [], stored = new Map() } = {}) {
  const removedIds = [];
  const api = createApi({ data: { id: 42, word: 'apple' } });
  const nextWord = () => {
    assert.ok(responses.length, 'Unexpected word request');
    return createApi(responses.shift()).fetchLearnWord();
  };
  api.fetchLearnWord = nextWord;
  api.fetchRepeatWord = nextWord;
  const repeatSession = load('src/features/practice/composables/useRepeatSession.ts', {
    '@/features/practice/api/practiceApi': api,
    '@/features/practice/composables/useIntervalRepetitionQueue': {
      useIntervalRepetitionQueue: () => ({
        loadOnce: async () => {}, reload: async () => {},
        getRandomWordId: () => 42, removeWordId: (id) => removedIds.push(id),
      }),
    },
  });
  const component = load('src/views/PracticeView.vue', {
    vue, zod: require('zod'), '@lucide/vue': {},
    'vue-router': { useRoute: () => ({ query: {} }), useRouter: () => ({ replace: async () => {} }) },
    '@/features/practice/api/practiceApi': api,
    '@/features/practice/composables/useRepeatSession': repeatSession,
    '@/features/practice/components/AudioWaveform.vue': {},
    '@/features/practice/components/WordCard.vue': {},
    '@/shared/api/client': {},
    '@/shared/limits': load('src/shared/limits.ts', {}),
    '@/shared/navigation/appLaunch': load('src/shared/navigation/appLaunch.ts', {}),
  }, {
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
      state = component.setup({ mode }, { expose() {} });
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
