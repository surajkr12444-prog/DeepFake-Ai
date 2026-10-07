// DeepShield — Centralized Configuration Module
// Automatically derives REST and WebSocket URLs based on environment and protocol

const Config = (() => {
  const isFileProto = window.location.protocol === 'file:';
  const isHttps = window.location.protocol === 'https:';
  const restProto = isHttps ? 'https:' : 'http:';
  const wsProto = isHttps ? 'wss:' : 'ws:';

  let API_BASE = '';
  let WS_BASE = '';

  if (isFileProto) {
    // When opened directly as a local file (file:///...)
    API_BASE = 'http://localhost:8050';
    WS_BASE = 'ws://localhost:8050';
  } else if (window.location.port === '8050') {
    // When served directly by the FastAPI backend on port 8050
    API_BASE = '';
    WS_BASE = `${wsProto}//${window.location.host}`;
  } else {
    // When served from Live Server (e.g. port 5500, 3000, 8080)
    API_BASE = 'http://localhost:8050';
    WS_BASE = 'ws://localhost:8050';
  }

  return {
    API_BASE,
    WS_BASE,

    // Endpoints
    ENDPOINTS: {
      HEALTH: `${API_BASE}/api/health`,
      SESSIONS: `${API_BASE}/api/sessions`,
      STATUS: `${API_BASE}/api/status`,
      STATS: `${API_BASE}/api/stats`,
      LOGS: `${API_BASE}/api/logs`,
      SETTINGS: `${API_BASE}/api/settings`,
      ENROLL: `${API_BASE}/api/enroll`,
      DETECT: `${API_BASE}/api/detect`,
      VOICE_PREDICT: `${API_BASE}/api/voice/predict`,
      EXPORT_CSV: `${API_BASE}/api/export_csv`,

      REPORT: `${API_BASE}/api/report`,
      WS_LIVE: (sessionId) => `${WS_BASE}/ws/live/${sessionId}`
    },

    // Streaming & Capture Profiles
    STREAM: {
      VIDEO_WIDTH: 640,
      VIDEO_HEIGHT: 360,
      FRAME_INTERVAL_MS: 700,    // ~1.4 FPS to avoid backend congestion
      AUDIO_CHUNK_MS: 2000,      // ~2 second audio chunks via MediaRecorder
      JPEG_QUALITY: 0.75
    },

    // WebSocket Resilience & Reconnection
    RECONNECT: {
      INITIAL_DELAY_MS: 1000,
      MAX_DELAY_MS: 16000,
      FACTOR: 2,
      MAX_ATTEMPTS: 5
    },

    // Connection States
    CONNECTION_STATES: {
      DISCONNECTED: 'DISCONNECTED',
      CONNECTING: 'CONNECTING',
      LIVE: 'LIVE',
      RECONNECTING: 'RECONNECTING',
      ERROR: 'ERROR',
      STOPPED: 'STOPPED'
    }
  };
})();

// Convert browser WebM/Opus or any audio blob to 16kHz 16-bit Mono WAV PCM
async function audioBlobToWav(audioBlob) {
  try {
    const arrayBuffer = await audioBlob.arrayBuffer();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return audioBlob;
    const tempCtx = new AudioCtx();
    const audioBuffer = await tempCtx.decodeAudioData(arrayBuffer);

    const sampleRate = 16000;
    const numChannels = 1;
    // Resample / downmix to 16kHz mono
    const ratio = audioBuffer.sampleRate / sampleRate;
    const targetLength = Math.round(audioBuffer.length / ratio);
    const pcmData = new Float32Array(targetLength);

    const ch0 = audioBuffer.getChannelData(0);
    const ch1 = audioBuffer.numberOfChannels > 1 ? audioBuffer.getChannelData(1) : null;

    for (let i = 0; i < targetLength; i++) {
      const srcIdx = Math.min(Math.round(i * ratio), audioBuffer.length - 1);
      const val = ch1 ? (ch0[srcIdx] + ch1[srcIdx]) / 2.0 : ch0[srcIdx];
      pcmData[i] = val;
    }

    try { tempCtx.close(); } catch (_) {}

    // Encode standard 44-byte RIFF/WAV header
    const wavBuffer = new ArrayBuffer(44 + targetLength * 2);
    const view = new DataView(wavBuffer);
    const writeStr = (offset, str) => {
      for (let j = 0; j < str.length; j++) view.setUint8(offset + j, str.charCodeAt(j));
    };

    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + targetLength * 2, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, numChannels, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // Bits per sample
    writeStr(36, 'data');
    view.setUint32(40, targetLength * 2, true);

    let offset = 44;
    for (let i = 0; i < targetLength; i++) {
      const s = Math.max(-1, Math.min(1, pcmData[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
  } catch (err) {
    console.warn('[AudioWav] Conversion fallback to original blob:', err);
    return audioBlob;
  }
}

window.Config = Config;
window.audioBlobToWav = audioBlobToWav;
