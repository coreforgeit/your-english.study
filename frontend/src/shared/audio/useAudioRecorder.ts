import { onUnmounted, ref, shallowRef } from 'vue';
export type RecordingStopReason = 'manual' | 'silence' | 'duration';
export type RecordingLimits = {
  maxDurationMs: number;
  minDurationMs: number;
  silenceDurationMs: number;
  silenceThreshold: number;
};
export type RecordedAudio = { blob: Blob; reason: RecordingStopReason };
type ActiveRecording = {
  recorder: MediaRecorder;
  chunks: BlobPart[];
  reason: RecordingStopReason;
  onComplete: (result: RecordedAudio) => void;
};

const voiceAudioBitsPerSecond = 48_000;
const voiceAudioConstraints: MediaTrackConstraints = {
  channelCount: { ideal: 1 },
  sampleRate: { ideal: 48_000 },
  echoCancellation: { ideal: true },
  noiseSuppression: { ideal: true },
  autoGainControl: { ideal: true },
};
const voiceMimeTypes = ['audio/webm;codecs=opus', 'audio/webm'];


export function useAudioRecorder(limits: RecordingLimits) {
  const isRecording = ref(false);
  const isStartingRecording = ref(false);
  const recordingStream = shallowRef<MediaStream | null>(null);
  const recordingAudioContext = shallowRef<AudioContext | null>(null);
  const recordingAnalyser = shallowRef<AnalyserNode | null>(null);
  const voiceDetectionFrame = ref<number | null>(null);
  let recordingTimeout: ReturnType<typeof setTimeout> | null = null;
  let activeRecording: ActiveRecording | null = null;
  let isUnmounted = false;
  let voiceDetected = false;
  let silenceStartedAt: number | null = null;
  let recordingStartedAt = 0;

  function setRecordingStreamEnabled(enabled: boolean) {
    recordingStream.value?.getAudioTracks().forEach((track) => {
      track.enabled = enabled;
    });
  }

  async function getRecordingStream() {
    if (recordingStream.value && recordingStream.value.active) {
      setRecordingStreamEnabled(true);
      return recordingStream.value;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: voiceAudioConstraints,
    });
    recordingStream.value = stream;
    setRecordingStreamEnabled(true);

    return stream;
  }

  function createVoiceMediaRecorder(stream: MediaStream) {
    const mimeType = voiceMimeTypes.find((type) => MediaRecorder.isTypeSupported(type));
    const options: MediaRecorderOptions = {
      audioBitsPerSecond: voiceAudioBitsPerSecond,
      ...(mimeType ? { mimeType } : {}),
    };

    try {
      return new MediaRecorder(stream, options);
    } catch (error) {
      if (!(error instanceof DOMException) || error.name !== 'NotSupportedError') {
        throw error;
      }

      console.warn(
        'Настройки аудиозаписи:',
        'WebView не поддерживает выбранные настройки записи, используются настройки по умолчанию.',
      );
      return new MediaRecorder(stream);
    }
  }

  function releaseRecordingStream() {
    recordingStream.value?.getTracks().forEach((track) => track.stop());
    recordingStream.value = null;
  }

  function stopVoiceDetection() {
    if (voiceDetectionFrame.value !== null) {
      cancelAnimationFrame(voiceDetectionFrame.value);
      voiceDetectionFrame.value = null;
    }

    recordingAudioContext.value?.close().catch((error: unknown) => {
      console.error('Ошибка закрытия аудиоконтекста:', error);
    });
    recordingAudioContext.value = null;
    recordingAnalyser.value = null;
    voiceDetected = false;
    silenceStartedAt = null;
    recordingStartedAt = 0;
  }

  function getVoiceVolume(analyser: AnalyserNode) {
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);

    let sum = 0;
    for (const value of data) {
      const normalizedValue = (value - 128) / 128;
      sum += normalizedValue * normalizedValue;
    }

    return Math.sqrt(sum / data.length);
  }

  function startVoiceDetection() {
    const analyser = recordingAnalyser.value;

    if (!analyser) {
      return;
    }

    const checkVoice = () => {
      const volume = getVoiceVolume(analyser);
      const now = performance.now();

      if (volume >= limits.silenceThreshold) {
        voiceDetected = true;
        silenceStartedAt = null;
      } else if (voiceDetected) {
        silenceStartedAt ??= now;

        if (
          now - silenceStartedAt >= limits.silenceDurationMs &&
          now - recordingStartedAt >= limits.minDurationMs
        ) {
          stopRecording('silence');
          return;
        }
      }

      voiceDetectionFrame.value = requestAnimationFrame(checkVoice);
    };

    voiceDetectionFrame.value = requestAnimationFrame(checkVoice);
  }


  function stopRecording(reason: RecordingStopReason = 'manual', discard = false) {
    if (recordingTimeout !== null) {
      clearTimeout(recordingTimeout);
      recordingTimeout = null;
    }
    stopVoiceDetection();
    const recording = activeRecording;
    activeRecording = null;
    if (recording) {
      recording.reason = reason;
      if (discard) {
        recording.recorder.onstop = null;
        recording.recorder.ondataavailable = null;
      }
      if (recording.recorder.state !== 'inactive') {
        recording.recorder.stop();
      }
    }
    setRecordingStreamEnabled(false);
    isRecording.value = false;
  }

  async function startRecording(onComplete: (result: RecordedAudio) => void) {
    if (isUnmounted || isStartingRecording.value || isRecording.value) {
      return;
    }
    isStartingRecording.value = true;
    try {
      const stream = await getRecordingStream();
      if (isUnmounted) {
        releaseRecordingStream();
        return;
      }

      const recorder = createVoiceMediaRecorder(stream);
      const audioContext = new AudioContext();
      recordingAudioContext.value = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      recordingAnalyser.value = analyser;

      const recording: ActiveRecording = { recorder, chunks: [], reason: 'manual', onComplete };
      activeRecording = recording;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recording.chunks.push(event.data);
      };
      recorder.onstop = () => {
        if (isUnmounted) return;
        const blob = new Blob(recording.chunks, { type: recorder.mimeType || 'audio/webm' });
        recording.onComplete({ blob, reason: recording.reason });
      };
      recorder.start();
      // Таймер работает и без речи, и без кадров визуализатора.
      recordingTimeout = setTimeout(() => stopRecording('duration'), limits.maxDurationMs);
      voiceDetected = false;
      silenceStartedAt = null;
      recordingStartedAt = performance.now();
      isRecording.value = true;
      startVoiceDetection();
    } catch (error) {
      stopRecording('manual', true);
      releaseRecordingStream();
      throw error;
    } finally {
      isStartingRecording.value = false;
    }
  }

  onUnmounted(() => {
    isUnmounted = true;
    stopRecording('manual', true);
    releaseRecordingStream();
  });

  return { isRecording, isStartingRecording, recordingAnalyser, startRecording, stopRecording };
}
