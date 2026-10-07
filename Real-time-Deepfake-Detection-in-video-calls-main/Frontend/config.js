// DeepShield — Centralized Configuration Module
// Automatically derives REST and WebSocket URLs based on environment and protocol

const Config = (() => {
  const isHttps = window.location.protocol === 'https:';
  const restProto = isHttps ? 'https:' : 'http:';
  const wsProto = isHttps ? 'wss:' : 'ws:';

  // If served directly from FastAPI server (default on port 8050)
  const isSameOrigin = window.location.port === '8050' || window.location.port === '';
  const defaultHost = isSameOrigin ? window.location.host : 'localhost:8050';

  const API_BASE = isSameOrigin ? '' : `${restProto}//${defaultHost}`;
  const WS_BASE = `${wsProto}//${defaultHost}`;

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
