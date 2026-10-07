// DeepShield — Centralized Configuration Module
// Automatically derives REST and WebSocket URLs based on environment and protocol

const Config = (() => {
  const isFileProto = window.location.protocol === 'file:';
  const isHttps = window.location.protocol === 'https:';
  const restProto = isHttps ? 'https:' : 'http:';
  const wsProto = isHttps ? 'wss:' : 'ws:';
  const isGithubPages = window.location.hostname.endsWith('github.io');

  // Check URL parameters first (?api= or ?backend=), then localStorage
  const urlParams = new URLSearchParams(window.location.search);
  const paramApi = urlParams.get('api') || urlParams.get('backend');
  const storedApi = localStorage.getItem('deepshield_api_url');

  let API_BASE = '';
  let WS_BASE = '';
  let activeMode = 'STANDALONE'; // 'LIVE' | 'STANDALONE'

  function deriveBases(customUrl) {
    if (customUrl) {
      API_BASE = customUrl.replace(/\/+$/, '');
      const isCustomHttps = API_BASE.startsWith('https:');
      const wsScheme = isCustomHttps ? 'wss:' : 'ws:';
      WS_BASE = API_BASE.replace(/^https?:/, wsScheme);
      return;
    }

    if (isFileProto) {
      API_BASE = 'http://localhost:8050';
      WS_BASE = 'ws://localhost:8050';
    } else if (window.location.port === '8050') {
      API_BASE = '';
      WS_BASE = `${wsProto}//${window.location.host}`;
    } else if (window.location.hostname.includes('.app.github.dev')) {
      // GitHub Codespaces port forwarding pattern
      const codespaceHost = window.location.hostname.replace(/-\d+\.app\.github\.dev/, '-8050.app.github.dev');
      API_BASE = `https://${codespaceHost}`;
      WS_BASE = `wss://${codespaceHost}`;
    } else if (isGithubPages) {
      // GitHub Pages static hosting: defaults to standalone, allows custom API
      API_BASE = storedApi || 'http://localhost:8050';
      WS_BASE = API_BASE.startsWith('https:') ? API_BASE.replace(/^https:/, 'wss:') : 'ws://localhost:8050';
    } else {
      API_BASE = 'http://localhost:8050';
      WS_BASE = 'ws://localhost:8050';
    }
  }

  deriveBases(paramApi || storedApi);

  const obj = {
    get API_BASE() { return API_BASE; },
    get WS_BASE() { return WS_BASE; },
    get activeMode() { return activeMode; },
    get isGithubPages() { return isGithubPages; },

    setActiveMode(mode) {
      activeMode = mode;
      console.log(`[Config] Operating mode transitioned to: ${mode}`);
    },

    setApiBase(newUrl) {
      if (newUrl) {
        localStorage.setItem('deepshield_api_url', newUrl);
        deriveBases(newUrl);
      } else {
        localStorage.removeItem('deepshield_api_url');
        deriveBases(null);
      }
      console.log(`[Config] API_BASE reconfigured to: ${API_BASE}`);
    },

    // Endpoints
    get ENDPOINTS() {
      return {
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
      };
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
      STANDALONE: 'STANDALONE',
      RECONNECTING: 'RECONNECTING',
      ERROR: 'ERROR',
      STOPPED: 'STOPPED'
    }
  };

  return obj;
})();

// Singleton AudioContext helper to prevent exceeding browser hardware context limits
let _sharedAudioCtx = null;
function getSharedAudioContext() {
  if (!_sharedAudioCtx || _sharedAudioCtx.state === 'closed') {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      _sharedAudioCtx = new AudioCtx();
    }
  }
  if (_sharedAudioCtx && _sharedAudioCtx.state === 'suspended') {
    _sharedAudioCtx.resume().catch(() => {});
  }
  return _sharedAudioCtx;
}

// Direct Float32Array PCM to 16-bit Mono WAV Blob encoder (RIFF/WAV standard)
function pcmToWavBlob(pcmData, sampleRate = 16000) {
  const numChannels = 1;
  const targetLength = pcmData.length;
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
}

// Convert browser WebM/Opus or any audio blob to 16kHz 16-bit Mono WAV PCM
async function audioBlobToWav(audioBlob) {
  try {
    const arrayBuffer = await audioBlob.arrayBuffer();
    const ctx = getSharedAudioContext();
    if (!ctx) return audioBlob;

    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
    const sampleRate = 16000;
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

    return pcmToWavBlob(pcmData, sampleRate);
  } catch (err) {
    console.warn('[AudioWav] Conversion fallback to original blob:', err);
    return audioBlob;
  }
}

window.Config = Config;
window.getSharedAudioContext = getSharedAudioContext;
window.pcmToWavBlob = pcmToWavBlob;
window.audioBlobToWav = audioBlobToWav;
