// DeepShield — Live Surveillance Controller Module
// Master Coordinator: Connects ApiClient, MediaCaptureManager, LiveWebSocketClient, and UIManager

class LiveSurveillanceController {
  constructor(uiManager) {
    this.ui = uiManager;
    this.media = new MediaCaptureManager();
    this.wsClient = new LiveWebSocketClient();

    this.sessionId = null;
    this.isActive = false;
    this.isStarting = false;
    this.frameIntervalTimer = null;
    this.renderLoopId = null;

    // Rolling statistics for timeline chart
    this.confidenceHistory = Array.from({ length: 30 }, () => 85);
    this.framesProcessed = 0;
    this.authenticFrames = 0;
    this.suspiciousFrames = 0;

    this._bindEvents();
  }

  _bindEvents() {
    // 1. Audio Chunks from MediaCaptureManager -> WebSocket
    this.media.setAudioChunkCallback((base64Audio) => {
      if (this.isActive && this.wsClient.isConnected()) {
        this.wsClient.sendAudioChunk(base64Audio);
      }
    });

    // 2. Hardware Disconnect Notification
    this.media.setDeviceDisconnectedCallback((trackKind) => {
      console.warn(`[Surveillance] Hardware track disconnected: ${trackKind}`);
      this.ui.updateHardwareBadges(this.media.cameraActive, this.media.micActive, true);
      if (window.showToast) {
        window.showToast(`Warning: ${trackKind === 'video' ? 'Camera' : 'Microphone'} unplugged or disconnected!`, 'warning');
      }
    });

    // 3. WebSocket State Machine Changes
    this.wsClient.onStateChange = (state, detail) => {
      this.ui.updateConnectionStatus(state, detail);

      if (state === Config.CONNECTION_STATES.LIVE) {
        this.ui.updateHardwareBadges(this.media.cameraActive, this.media.micActive, true);
        this._startStreamingTimers();
      } else if (state === Config.CONNECTION_STATES.RECONNECTING) {
        this._stopStreamingTimers();
      } else if (state === Config.CONNECTION_STATES.ERROR || state === Config.CONNECTION_STATES.DISCONNECTED) {
        this._stopStreamingTimers();
      }
    };

    // 4. WebSocket Analysis Payload Received from Backend
    this.wsClient.onAnalysisData = (payload) => {
      this.framesProcessed++;
      const fusedScore = payload.fused ? payload.fused.score : 0;
      const isSus = (payload.fused && (payload.fused.level === 'CRITICAL' || payload.fused.level === 'HIGH'));

      if (isSus) {
        this.suspiciousFrames++;
      } else {
        this.authenticFrames++;
      }

      // Rolling confidence timeline
      const authVal = Math.round(100 - fusedScore);
      this.confidenceHistory.shift();
      this.confidenceHistory.push(authVal);

      // Render analysis on dashboard
      this.ui.renderAnalysisResult(payload);

      // Append log entry
      if (window.appendLogRow && payload.video && payload.video.face_detected) {
        const timeStr = new Date().toTimeString().split(' ')[0];
        window.appendLogRow(
          this.framesProcessed,
          timeStr,
          `${authVal}%`,
          payload.video.liveness_score ? (payload.video.liveness_score / 100.0).toFixed(3) : '0.995',
          payload.fused.label || payload.video.label,
          isSus ? 'sus' : 'auth'
        );
      }

      // Update stat counters in UI
      const framesEl = document.getElementById('sv-frames');
      if (framesEl) framesEl.textContent = this.framesProcessed.toLocaleString();
      const authEl = document.getElementById('sv-auth');
      if (authEl) authEl.textContent = this.authenticFrames.toLocaleString();
      const susEl = document.getElementById('sv-sus');
      if (susEl) susEl.textContent = this.suspiciousFrames.toLocaleString();
    };

    this.wsClient.onConnectionAck = (ack) => {
      console.log('[Surveillance] Backend Stream Ack:', ack.message);
      if (window.showToast) {
        window.showToast('Live AI Surveillance Session Engaged', 'success');
      }
    };
  }

  async startSurveillance() {
    // Prevent duplicate stream starts if user clicks twice rapidly
    if (this.isActive || this.isStarting) {
      console.warn('[Surveillance] Start requested while already starting or running.');
      return;
    }

    this.isStarting = true;
    this.ui.updateConnectionStatus(Config.CONNECTION_STATES.CONNECTING);

    const toggleBtn = this.ui.el.toggleDetectionBtn;
    if (toggleBtn) {
      toggleBtn.innerHTML = '⏳ Initializing...';
      toggleBtn.disabled = true;
    }

    try {
      // 1. Verify Backend Health
      let health = null;
      try {
        health = await ApiClient.checkHealth();
        this.ui.updateHardwareBadges(false, false, true);
      } catch (healthErr) {
        this.ui.updateHardwareBadges(false, false, false);
        throw new Error('Backend AI server is offline. Please launch backend on port 8050.');
      }

      // 2. Request Camera & Microphone Permissions
      const videoEl = this.ui.el.webcamVideo;
      const mediaRes = await this.media.startCapture(videoEl);
      this.ui.updateHardwareBadges(mediaRes.camera, mediaRes.microphone, true);

      // Show video feed
      if (this.ui.el.videoPlaceholder) this.ui.el.videoPlaceholder.style.display = 'none';
      if (this.ui.el.overlayCanvas) this.ui.el.overlayCanvas.style.display = 'block';
      if (this.ui.el.scanLine) this.ui.el.scanLine.style.display = 'block';
      if (this.ui.el.hudInfo) this.ui.el.hudInfo.style.display = 'flex';

      // 3. Create Backend Surveillance Session
      const sensitivity = (window.state && window.state.threshold) ? window.state.threshold : 60.0;
      const sessionData = await ApiClient.createSession(sensitivity);
      this.sessionId = sessionData.session_id;
      console.log(`[Surveillance] Established backend session: ${this.sessionId}`);

      // 4. Connect Authoritative WebSocket
      this.wsClient.connect(this.sessionId);

      this.isActive = true;
      this.isStarting = false;

      if (toggleBtn) {
        toggleBtn.disabled = false;
        toggleBtn.innerHTML = '⏹ Stop Surveillance';
        toggleBtn.style.background = 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)';
      }

      // Start continuous HUD render loop
      this._startRenderLoop();

    } catch (err) {
      console.error('[Surveillance] Initialization failed:', err);
      this.isStarting = false;
      this.stopSurveillance();

      if (toggleBtn) {
        toggleBtn.disabled = false;
        toggleBtn.innerHTML = '▶ Start Detection';
        toggleBtn.style.background = '';
      }

      this.ui.updateConnectionStatus(Config.CONNECTION_STATES.ERROR, err.message);
      if (window.showToast) {
        window.showToast(`Surveillance failed to start: ${err.message}`, 'warning');
      }
    }
  }

  async stopSurveillance() {
    this.isActive = false;
    this.isStarting = false;

    // 1. Stop video streaming intervals
    this._stopStreamingTimers();

    // 2. Stop HUD render loop
    if (this.renderLoopId) {
      cancelAnimationFrame(this.renderLoopId);
      this.renderLoopId = null;
    }

    // 3. Clean up MediaRecorder and camera/mic tracks
    this.media.stopCapture();

    // 4. Close WebSocket cleanly (sets intentionalStop)
    this.wsClient.stop();

    // 5. Terminate session on backend
    if (this.sessionId) {
      const closingSessionId = this.sessionId;
      this.sessionId = null;
      ApiClient.deleteSession(closingSessionId).catch(() => {});
    }

    // 6. Reset UI components
    this.ui.resetUI();
    this.ui.updateHardwareBadges(false, false, true);

    if (window.showToast) {
      window.showToast('Live surveillance stopped. All media tracks released.', 'info');
    }
  }

  _startStreamingTimers() {
    this._stopStreamingTimers();

    // Stream video frame at ~1.4 FPS (Config.STREAM.FRAME_INTERVAL_MS = 700ms)
    this.frameIntervalTimer = setInterval(() => {
      if (this.isActive && this.wsClient.isConnected()) {
        const frameB64 = this.media.captureFrameBase64();
        if (frameB64) {
          this.wsClient.sendVideoFrame(frameB64);
        }
      }
    }, Config.STREAM.FRAME_INTERVAL_MS);
  }

  _stopStreamingTimers() {
    if (this.frameIntervalTimer) {
      clearInterval(this.frameIntervalTimer);
      this.frameIntervalTimer = null;
    }
  }

  _startRenderLoop() {
    const canvas = this.ui.el.overlayCanvas;
    const video = this.ui.el.webcamVideo;

    const render = () => {
      if (!this.isActive) return;

      if (canvas && video && video.videoWidth > 0) {
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        this.ui.drawOverlays(canvas, true);
      }

      this.renderLoopId = requestAnimationFrame(render);
    };

    render();
  }
}

window.LiveSurveillanceController = LiveSurveillanceController;
