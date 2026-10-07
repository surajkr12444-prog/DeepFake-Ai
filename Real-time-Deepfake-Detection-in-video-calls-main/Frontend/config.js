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

window.Config = Config;
