<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  analyser: AnalyserNode | null;
  isRecording: boolean;
}>();

const canvasElement = ref<HTMLCanvasElement | null>(null);
const elapsedTime = ref('0:00');

const levels = Array.from({ length: 56 }, () => 0.04);
let samples = new Uint8Array(1024);

let animationFrame: number | null = null;
let resizeObserver: ResizeObserver | null = null;
let startedAt = 0;
let lastLevelAt = 0;
let lastElapsedSecond = -1;
let smoothedLevel = 0;
let waveformColor = '#2164aa';

function resizeCanvas() {
  const canvas = canvasElement.value;
  if (!canvas) {
    return;
  }

  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
  const height = Math.max(1, Math.round(canvas.clientHeight * ratio));

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  waveformColor = getComputedStyle(canvas).getPropertyValue('--color-primary-text').trim() || waveformColor;
}

function getVolume() {
  const analyser = props.analyser;
  if (!analyser || !props.isRecording) {
    return 0;
  }

  if (samples.length !== analyser.fftSize) {
    samples = new Uint8Array(analyser.fftSize);
  }

  analyser.getByteTimeDomainData(samples);

  let sum = 0;
  for (const sample of samples) {
    const normalizedSample = (sample - 128) / 128;
    sum += normalizedSample * normalizedSample;
  }

  return Math.sqrt(sum / samples.length);
}

function drawWaveform() {
  const canvas = canvasElement.value;
  const context = canvas?.getContext('2d');
  if (!canvas || !context) {
    return;
  }

  const width = canvas.width;
  const height = canvas.height;
  const centerY = height / 2;
  const gap = width / levels.length;

  context.clearRect(0, 0, width, height);
  context.strokeStyle = waveformColor;
  context.globalAlpha = 0.55;
  context.lineCap = 'round';
  context.lineWidth = Math.max(2, gap * 0.28);

  levels.forEach((level, index) => {
    const barHeight = Math.max(context.lineWidth, level * height * 0.82);
    const x = gap * index + gap / 2;

    context.beginPath();
    context.moveTo(x, centerY - barHeight / 2);
    context.lineTo(x, centerY + barHeight / 2);
    context.stroke();
  });
}

function updateFrame(now: number) {
  const elapsedSeconds = props.isRecording ? Math.floor((now - startedAt) / 1000) : 0;
  if (elapsedSeconds !== lastElapsedSecond) {
    lastElapsedSecond = elapsedSeconds;
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = String(elapsedSeconds % 60).padStart(2, '0');
    elapsedTime.value = `${minutes}:${seconds}`;
  }

  const volume = Math.min(1, getVolume() * 7);
  smoothedLevel = smoothedLevel * 0.72 + volume * 0.28;

  if (now - lastLevelAt >= 45) {
    levels.shift();
    levels.push(Math.max(0.04, smoothedLevel));
    lastLevelAt = now;
  }

  drawWaveform();
  animationFrame = requestAnimationFrame(updateFrame);
}

watch(
  () => props.isRecording,
  (isRecording) => {
    levels.fill(0.04);
    smoothedLevel = 0;
    lastElapsedSecond = -1;
    elapsedTime.value = '0:00';

    if (isRecording) {
      startedAt = performance.now();
      lastLevelAt = startedAt;
    }
  },
);

onMounted(() => {
  const canvas = canvasElement.value;
  if (!canvas) {
    return;
  }

  resizeObserver = new ResizeObserver(resizeCanvas);
  resizeObserver.observe(canvas);
  resizeCanvas();
  startedAt = performance.now();
  lastLevelAt = startedAt;
  animationFrame = requestAnimationFrame(updateFrame);
});

onBeforeUnmount(() => {
  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame);
  }
  resizeObserver?.disconnect();
});
</script>

<template>
  <aside
    class="audio-waveform"
    role="status"
    aria-live="off"
    :aria-label="isRecording ? 'Идёт запись' : 'Визуализатор записи'"
  >
    <span class="audio-waveform-time">{{ elapsedTime }}</span>
    <canvas ref="canvasElement" class="audio-waveform-canvas" aria-hidden="true" />
  </aside>
</template>
