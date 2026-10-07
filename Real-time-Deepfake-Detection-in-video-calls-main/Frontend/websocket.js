// DeepShield — Authoritative Live WebSocket Client Module
// Manages connection lifecycle, ping/pong heartbeats, exponential backoff, and packet dispatching

class LiveWebSocketClient {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.state = Config.CONNECTION_STATES.DISCONNECTED;
    this.intentionalStop = false;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.pingTimer = null;

    // Event hooks
    this.onStateChange = null;
    this.onAnalysisData = null;
    this.onConnectionAck = null;
    this.onError = null;
  }

  setState(newState, detail = null) {
    if (this.state !== newState) {
      this.state = newState;
      console.log(`[LiveWS] State -> ${newState}`, detail || '');
      if (this.onStateChange) {
        this.onStateChange(this.state, detail);
      }
    }
  }

  connect(sessionId) {
    if (!sessionId) {
      throw new Error('[LiveWS] Cannot connect without valid sessionId');
    }

    // Clean up any existing connection
    this.cleanup(false);
    this.sessionId = sessionId;
    this.intentionalStop = false;

    this.setState(Config.CONNECTION_STATES.CONNECTING);
    const wsUrl = Config.ENDPOINTS.WS_LIVE(sessionId);
    console.log(`[LiveWS] Connecting to: ${wsUrl}`);

    try {
      this.ws = new WebSocket(wsUrl);
    } catch (err) {
      this.setState(Config.CONNECTION_STATES.ERROR, err.message);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('[LiveWS] WebSocket connection opened.');
      this.reconnectAttempts = 0;
      this.setState(Config.CONNECTION_STATES.LIVE);
      this._startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'analysis') {
          if (this.onAnalysisData) this.onAnalysisData(payload);
        } else if (payload.type === 'connection_ack') {
          if (this.onConnectionAck) this.onConnectionAck(payload);
        } else if (payload.type === 'pong') {
          // Heartbeat acknowledged
        }
      } catch (err) {
        console.warn('[LiveWS] Non-JSON or malformed message received:', event.data);
      }
    };

    this.ws.onerror = (event) => {
      console.warn('[LiveWS] Socket encountered error:', event);
      if (this.onError) this.onError(event);
      this.setState(Config.CONNECTION_STATES.ERROR, 'Socket error');
    };

    this.ws.onclose = (event) => {
      console.log(`[LiveWS] Socket closed (code=${event.code}, reason=${event.reason})`);
      this._stopHeartbeat();

      if (this.intentionalStop) {
        this.setState(Config.CONNECTION_STATES.STOPPED);
      } else {
        this.setState(Config.CONNECTION_STATES.DISCONNECTED);
        this._scheduleReconnect();
      }
    };
  }

  sendVideoFrame(base64Image, timestamp = Date.now()) {
    if (this.isConnected()) {
      try {
        this.ws.send(JSON.stringify({
          type: 'video_frame',
          image: base64Image,
          timestamp: timestamp
        }));
      } catch (err) {
        console.warn('[LiveWS] Failed to send video frame:', err);
      }
    }
  }

  sendAudioChunk(base64Audio, timestamp = Date.now()) {
    if (this.isConnected()) {
      try {
        this.ws.send(JSON.stringify({
          type: 'audio_chunk',
          audio: base64Audio,
          timestamp: timestamp
        }));
      } catch (err) {
        console.warn('[LiveWS] Failed to send audio chunk:', err);
      }
    }
  }

  sendPing() {
    if (this.isConnected()) {
      try {
        this.ws.send(JSON.stringify({
          type: 'ping',
          timestamp: Date.now()
        }));
      } catch (_) {}
    }
  }

  stop() {
    this.intentionalStop = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this._stopHeartbeat();

    if (this.ws) {
      try {
        this.ws.send(JSON.stringify({ type: 'stop' }));
        this.ws.close(1000, 'User stopped surveillance');
      } catch (_) {}
      this.ws = null;
    }

    this.setState(Config.CONNECTION_STATES.STOPPED);
  }

  cleanup(markStopped = true) {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this._stopHeartbeat();
    if (this.ws) {
      try { this.ws.close(); } catch (_) {}
      this.ws = null;
    }
    if (markStopped) {
      this.setState(Config.CONNECTION_STATES.STOPPED);
    }
  }

  isConnected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingTimer = setInterval(() => {
      this.sendPing();
    }, 10000);
  }

  _stopHeartbeat() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.intentionalStop) return;

    if (this.reconnectAttempts >= Config.RECONNECT.MAX_ATTEMPTS) {
      console.warn('[LiveWS] Max reconnect attempts reached.');
      this.setState(Config.CONNECTION_STATES.ERROR, 'Connection lost permanently.');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      Config.RECONNECT.INITIAL_DELAY_MS * Math.pow(Config.RECONNECT.FACTOR, this.reconnectAttempts - 1),
      Config.RECONNECT.MAX_DELAY_MS
    );

    this.setState(Config.CONNECTION_STATES.RECONNECTING, `Attempt ${this.reconnectAttempts} in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => {
      if (!this.intentionalStop && this.sessionId) {
        console.log(`[LiveWS] Reconnecting (attempt ${this.reconnectAttempts})...`);
        this.connect(this.sessionId);
      }
    }, delay);
  }
}

window.LiveWebSocketClient = LiveWebSocketClient;
