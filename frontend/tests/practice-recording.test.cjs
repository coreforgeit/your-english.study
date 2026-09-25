const assert = require('node:assert/strict');
const { test } = require('node:test');
const vue = require('vue');
const { load } = require('./helpers/loadFrontend.cjs');

// Mount the real component's setup using Vue's renderer, without a browser or API.
// Only browser media/timing APIs and external feature services are replaced.
function mountPractice(t, { deferPermission = false, failStart = false, standaloneLimits = null } = {}) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let now = 0;
  let volume = 128;
  let frameSequence = 0;
  let resolvePermission;
  const frames = new Map();
  const requests = [];
  const recorders = [];
  const contexts = [];
  const track = { enabled: true, stopped: false, stop() { this.stopped = true; }, getSettings: () => ({}) };
  const stream = { active: true, getAudioTracks: () => [track], getTracks: () => [track] };
  const permission = deferPermission ? new Promise((resolve) => { resolvePermission = resolve; }) : Promise.resolve(stream);

  class FakeMediaRecorder {
    static isTypeSupported() { return true; }
    state = 'inactive';
    mimeType = 'audio/webm';
    stopCalls = 0;
    constructor() { recorders.push(this); }
    start() {
      if (failStart) throw new Error('Не удалось запустить запись');
      this.state = 'recording';
    }
    stop() {
      this.stopCalls++;
      this.state = 'inactive';
      queueMicrotask(() => {
        this.ondataavailable?.({ data: new Blob(['voice'], { type: this.mimeType }) });
        this.onstop?.();
      });
    }
  }

  class FakeAudioContext {
    closed = false;
    constructor() { contexts.push(this); }
    createMediaStreamSource() { return { connect() {} }; }
    createAnalyser() { return { fftSize: 1024, getByteTimeDomainData: (samples) => samples.fill(volume) }; }
    async close() { this.closed = true; }
  }

  const imports = {
    vue,
    zod: require('zod'),
    '@lucide/vue': {},
    'vue-router': { useRoute: () => ({ query: {} }), useRouter: () => ({ replace: async () => {} }) },
    '@/shared/navigation/appLaunch': { AppLaunchQuery: { AUTO_START: 'autoStart' }, APP_LAUNCH_AUTO_START_VALUE: 'true' },
    '@/shared/config': { BACKEND_URL: 'https://example.test' },
    '@/features/practice/components/AudioWaveform.vue': {},
    '@/features/practice/components/WordCard.vue': {},
    '@/features/practice/composables/useRepeatSession': {
      useRepeatSession: () => ({ preloadIntervalRepetitions: async () => {} }),
    },
  };
  const globals = {
    fetch: (...args) => {
      requests.push(args);
      return new Promise(() => {});
    },
    console: { log() {}, warn() {}, error() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    navigator: { mediaDevices: { getUserMedia: () => permission } },
    MediaRecorder: FakeMediaRecorder,
    AudioContext: FakeAudioContext,
    Blob,
    FormData,
    DOMException,
    performance: { now: () => now },
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (callback) => { frames.set(++frameSequence, callback); return frameSequence; },
    cancelAnimationFrame: (id) => frames.delete(id),
  };
  const component = standaloneLimits
    ? { setup: () => load('src/shared/audio/useAudioRecorder.ts', imports, globals).useAudioRecorder(standaloneLimits) }
    : load('src/views/PracticeView.vue', imports, globals).default;

  const renderer = vue.createRenderer({
    createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null,
  });
  let state;
  const app = renderer.createApp({
    setup() {
      const setup = component.setup({ mode: 'repeat' }, { expose() {} });
      state = standaloneLimits ? setup : setup.session;
      return () => null;
    },
  });
  app.mount({});
  if (!standaloneLimits) state.currentState.value.word = { id: 42, word: 'word', translations: ['слово'] };
  t.after(() => app.unmount());

  return {
    state, requests, recorders, contexts, track,
    unmount: () => app.unmount(),
    grantPermission: () => resolvePermission(stream),
    async tick(ms) {
      now += ms;
      t.mock.timers.tick(ms);
      await Promise.resolve();
    },
    frame(sample) {
      volume = sample;
      const pendingFrames = [...frames.values()];
      frames.clear();
      pendingFrames.forEach((callback) => callback(now));
    },
  };
}

for (const sample of [128, 160]) {
  test(`recording stops and submits at 20 seconds (audio sample ${sample})`, async (t) => {
    const h = mountPractice(t);
    await h.state.startRecording();
    h.frame(sample);
    await h.tick(19_999);
    assert.equal(h.recorders[0].state, 'recording');
    assert.equal(h.requests.length, 0);
    await h.tick(1);
    assert.equal(h.recorders[0].stopCalls, 1);
    assert.equal(h.state.isRecording.value, false);
    assert.equal(h.track.enabled, false);
    assert.equal(h.contexts[0].closed, true);
    assert.equal(h.requests.length, 1);
    assert.equal(h.requests[0][1].body.get('word_id'), '42');
    await h.tick(20_000);
    assert.equal(h.requests.length, 1);
  });
}

test('manual stop cancels the timer; the next recording gets a fresh 20 seconds', async (t) => {
  const h = mountPractice(t);
  await h.state.startRecording();
  await h.tick(5_000);
  h.state.stopRecording();
  await Promise.resolve();
  assert.equal(h.requests.length, 0);
  await h.state.startRecording();
  await h.tick(15_000);
  assert.equal(h.recorders[1].state, 'recording');
  await h.tick(5_000);
  assert.equal(h.recorders[0].stopCalls, 1);
  assert.equal(h.recorders[1].stopCalls, 1);
  assert.equal(h.requests.length, 1);
});

test('silence still stops early and cancels the duration timer', async (t) => {
  const h = mountPractice(t);
  await h.state.startRecording();
  h.frame(160);
  await h.tick(500);
  h.frame(128);
  await h.tick(1_200);
  h.frame(128);
  await Promise.resolve();
  assert.equal(h.requests.length, 1);
  await h.tick(20_000);
  assert.equal(h.recorders[0].stopCalls, 1);
  assert.equal(h.requests.length, 1);
});

test('unmount stops the recording and prevents timed submission', async (t) => {
  const h = mountPractice(t);
  await h.state.startRecording();
  h.unmount();
  await h.tick(20_000);
  assert.equal(h.recorders[0].stopCalls, 1);
  assert.equal(h.track.stopped, true);
  assert.equal(h.requests.length, 0);
});

test('permission delay is not counted; repeated start does not create extra timers', async (t) => {
  const h = mountPractice(t, { deferPermission: true });
  const starting = h.state.startRecording();
  await h.state.startRecording();
  await h.tick(30_000);
  assert.equal(h.recorders.length, 0);
  h.grantPermission();
  await starting;
  assert.equal(h.recorders.length, 1);
  await h.tick(19_999);
  assert.equal(h.recorders[0].state, 'recording');
  await h.tick(1);
  assert.equal(h.requests.length, 1);
});

test('permission granted after unmount cannot start recording or its timer', async (t) => {
  const h = mountPractice(t, { deferPermission: true });
  const starting = h.state.startRecording();
  h.unmount();
  h.grantPermission();
  await starting;
  await h.tick(20_000);
  assert.equal(h.recorders.length, 0);
  assert.equal(h.track.stopped, true);
  assert.equal(h.requests.length, 0);
});

test('failed start releases resources without leaving a submission timer', async (t) => {
  const h = mountPractice(t, { failStart: true });
  await h.state.startRecording();
  await h.tick(20_000);
  assert.equal(h.state.isStartingRecording.value, false);
  assert.equal(h.state.isRecording.value, false);
  assert.equal(h.track.stopped, true);
  assert.equal(h.contexts[0].closed, true);
  assert.equal(h.requests.length, 0);
});

test('standalone recorder uses its supplied limit and returns audio without an API request', async (t) => {
  const h = mountPractice(t, { standaloneLimits: {
    maxDurationMs: 60_000, minDurationMs: 500, silenceDurationMs: 1_200, silenceThreshold: 0.025,
  } });
  const completed = [];
  await h.state.startRecording((result) => completed.push(result));
  await h.tick(20_000);
  assert.equal(h.state.isRecording.value, true);
  await h.tick(40_000);
  assert.equal(h.state.isRecording.value, false);
  assert.equal(completed.length, 1);
  assert.equal(completed[0].reason, 'duration');
  assert.equal(await completed[0].blob.text(), 'voice');
  assert.equal(h.requests.length, 0);
});

test('standalone manual stop reports its reason and keeps recordings separate', async (t) => {
  const h = mountPractice(t, { standaloneLimits: {
    maxDurationMs: 20_000, minDurationMs: 500, silenceDurationMs: 1_200, silenceThreshold: 0.025,
  } });
  const completed = [];
  await h.state.startRecording((result) => completed.push(result));
  h.state.stopRecording();
  const nextRecording = h.state.startRecording((result) => completed.push(result));
  await nextRecording;
  await h.tick(20_000);
  assert.equal(completed.length, 2);
  assert.equal(completed[0].reason, 'manual');
  assert.equal(completed[1].reason, 'duration');
  assert.equal(await completed[0].blob.text(), 'voice');
  assert.equal(await completed[1].blob.text(), 'voice');
});
