// DeepShield — User Interface & Live Dashboard Renderer Module
// Governs HUD, connection badges, risk metrics, alert siren, and visual overlays

class UIManager {
  constructor(elements) {
    this.el = elements;
    this.audioSiren = null;
    this.sirenPlaying = false;
    this.lastAlertTime = 0;

    // Smooth bounding box interpolation
    this.targetBBox = null;
    this.currentBBox = null;
    this.targetLandmarks = [];
    this.currentLandmarks = [];

    this._initAudioSiren();
  }

  _initAudioSiren() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.audioCtx = new AudioCtx();
      }
    } catch (_) {}
  }

  playSiren() {
    if (!this.el.audioAlertToggle || !this.el.audioAlertToggle.checked) return;
    const now = Date.now();
    if (now - this.lastAlertTime < 2500) return;
    this.lastAlertTime = now;

    try {
      if (!this.audioCtx) this._initAudioSiren();
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
      if (this.audioCtx) {
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(680, this.audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, this.audioCtx.currentTime + 0.3);
        osc.frequency.exponentialRampToValueAtTime(680, this.audioCtx.currentTime + 0.6);
        gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.7);
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.7);
      }
    } catch (_) {}
  }

  updateConnectionStatus(state, details = '') {
    const isLive = (state === Config.CONNECTION_STATES.LIVE);

    // Update Topbar Status Indicator
    if (this.el.liveIndicator && this.el.liveText) {
      this.el.liveIndicator.className = 'live-indicator';
      if (isLive) {
        this.el.liveIndicator.classList.add('active');
        this.el.liveText.textContent = 'LIVE SURVEILLANCE';
      } else if (state === Config.CONNECTION_STATES.CONNECTING) {
        this.el.liveIndicator.classList.add('connecting');
        this.el.liveText.textContent = 'CONNECTING CORE...';
      } else if (state === Config.CONNECTION_STATES.RECONNECTING) {
        this.el.liveIndicator.classList.add('reconnecting');
        this.el.liveText.textContent = 'RECONNECTING...';
      } else if (state === Config.CONNECTION_STATES.ERROR) {
        this.el.liveIndicator.classList.add('error');
        this.el.liveText.textContent = 'SYSTEM ERROR';
      } else {
        this.el.liveText.textContent = 'SYSTEM READY';
      }
    }

    // Sidebar LIVE badge: Strictly visible ONLY when state === 'LIVE'
    const liveBadges = document.querySelectorAll('.live-badge');
    liveBadges.forEach(badge => {
      badge.style.display = isLive ? 'inline-block' : 'none';
    });

    // Update Feed Status Text
    if (this.el.feedStatus) {
      if (isLive) {
        this.el.feedStatus.textContent = 'Active (Live WS)';
        this.el.feedStatus.style.color = '#10b981';
      } else if (state === Config.CONNECTION_STATES.CONNECTING || state === Config.CONNECTION_STATES.RECONNECTING) {
        this.el.feedStatus.textContent = state;
        this.el.feedStatus.style.color = '#f59e0b';
      } else {
        this.el.feedStatus.textContent = 'Inactive';
        this.el.feedStatus.style.color = '';
      }
    }
  }

  updateHardwareBadges(cameraActive, micActive, backendActive) {
    const camEl = document.getElementById('cam-status-indicator');
    if (camEl) {
      camEl.textContent = cameraActive ? 'CAM: ON' : 'CAM: OFF';
      camEl.style.color = cameraActive ? '#10b981' : '#ef4444';
    }

    const micEl = document.getElementById('mic-status-indicator');
    if (micEl) {
      micEl.textContent = micActive ? 'MIC: ON' : 'MIC: OFF';
      micEl.style.color = micActive ? '#10b981' : '#ef4444';
    }

    const backEl = document.getElementById('backend-status-indicator');
    if (backEl) {
      backEl.textContent = backendActive ? 'BACKEND: ON' : 'BACKEND: OFF';
      backEl.style.color = backendActive ? '#10b981' : '#ef4444';
    }
  }

  renderAnalysisResult(data) {
    if (!data || data.type !== 'analysis') return;

    const v = data.video || {};
    const a = data.audio || {};
    const f = data.fused || {};
    const latency = data.latency_ms || 0;

    // 1. Overall Authenticity & Fused Threat Assessment
    const fusedScore = f.score || 0.0;
    const authScore = Math.max(0, Math.min(100, Math.round(100 - fusedScore)));
    const level = f.level || 'LOW';
    const isCritical = (level === 'CRITICAL' || level === 'HIGH');

    // 2. Update Status Card
    if (this.el.statusLabel) this.el.statusLabel.textContent = isCritical ? 'Synthetic Anomaly Detected' : 'Authentic';
    if (this.el.statusSub) {
      const reasonText = (f.reasons && f.reasons.length > 0) ? f.reasons[0] : 'Natural biometric parameters verified';
      this.el.statusSub.textContent = reasonText;
    }
    if (this.el.statusConf) this.el.statusConf.textContent = `${authScore}%`;

    if (this.el.statusIcon) {
      this.el.statusIcon.textContent = isCritical ? '⚠️' : '✅';
    }
    if (this.el.statusIconWrap) {
      this.el.statusIconWrap.className = isCritical ? 'status-icon-wrap suspicious-bg' : 'status-icon-wrap authentic-bg';
    }

    // 3. Update Multi-Cue Progress Bars
    if (this.el.confVal) this.el.confVal.textContent = `${authScore}%`;
    if (this.el.confBar) this.el.confBar.style.width = `${authScore}%`;

    const fftVal = Math.round(v.fft_score || 0);
    if (this.el.fftVal) this.el.fftVal.textContent = `${fftVal}%`;
    if (this.el.fftBar) this.el.fftBar.style.width = `${fftVal}%`;

    const texVal = Math.round(v.texture_score || 0);
    if (this.el.textureVal) this.el.textureVal.textContent = `${texVal}%`;
    if (this.el.textureBar) this.el.textureBar.style.width = `${texVal}%`;

    const seamVal = Math.round(v.seam_score || 0);
    if (this.el.seamVal) this.el.seamVal.textContent = `${seamVal}%`;
    if (this.el.seamBar) this.el.seamBar.style.width = `${seamVal}%`;

    const liveVal = Math.round(v.liveness_score || 0);
    if (this.el.livenessVal) this.el.livenessVal.textContent = `${liveVal}%`;
    if (this.el.livenessBar) this.el.livenessBar.style.width = `${liveVal}%`;

    // 4. Update HUD Overlays & Red Caution Alerts
    if (this.el.hudLabel) {
      this.el.hudLabel.textContent = isCritical ? '🚨 RED CAUTION' : '✓ AUTHENTIC';
      this.el.hudLabel.className = isCritical ? 'hud-label-text hud-suspicious' : 'hud-label-text hud-authentic';
    }
    if (this.el.hudConfidence) {
      this.el.hudConfidence.textContent = `${authScore}% (${latency}ms)`;
    }

    // Prominent Red Caution Banner
    if (isCritical) {
      if (this.el.redAlertBanner) {
        this.el.redAlertBanner.style.display = 'flex';
        if (this.el.redAlertDesc) {
          this.el.redAlertDesc.textContent = (f.reasons && f.reasons.length > 0)
            ? f.reasons.join(' • ')
            : 'Multi-cue forensics confirmed synthetic audio/video manipulation.';
        }
      }
      if (this.el.hudRedAlertTag) this.el.hudRedAlertTag.style.display = 'block';
      if (this.el.videoWrapper) this.el.videoWrapper.classList.add('video-deepfake-alert');

      // Trigger siren sound
      this.playSiren();
    } else {
      if (this.el.redAlertBanner) this.el.redAlertBanner.style.display = 'none';
      if (this.el.hudRedAlertTag) this.el.hudRedAlertTag.style.display = 'none';
      if (this.el.videoWrapper) this.el.videoWrapper.classList.remove('video-deepfake-alert');
    }

    // Update target bounding box for smooth canvas drawing
    if (v.bbox && v.face_detected) {
      this.targetBBox = v.bbox;
      this.targetLandmarks = v.landmarks || [];
    } else {
      this.targetBBox = null;
      this.targetLandmarks = [];
    }
  }

  drawOverlays(canvas, isLive) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Smooth bounding box interpolation
    if (this.targetBBox) {
      if (!this.currentBBox) {
        this.currentBBox = [...this.targetBBox];
      } else {
        const lerp = 0.35;
        this.currentBBox[0] += (this.targetBBox[0] - this.currentBBox[0]) * lerp;
        this.currentBBox[1] += (this.targetBBox[1] - this.currentBBox[1]) * lerp;
        this.currentBBox[2] += (this.targetBBox[2] - this.currentBBox[2]) * lerp;
        this.currentBBox[3] += (this.targetBBox[3] - this.currentBBox[3]) * lerp;
      }

      const [x, y, w, h] = this.currentBBox;
      ctx.save();
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 4]);
      ctx.strokeRect(x, y, w, h);

      // Target Corner Reticles
      ctx.setLineDash([]);
      ctx.strokeStyle = '#22d3ee';
      ctx.lineWidth = 3;
      const corner = Math.min(20, w * 0.2);

      // Top-Left
      ctx.beginPath();
      ctx.moveTo(x, y + corner); ctx.lineTo(x, y); ctx.lineTo(x + corner, y);
      ctx.stroke();

      // Top-Right
      ctx.beginPath();
      ctx.moveTo(x + w - corner, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + corner);
      ctx.stroke();

      // Bottom-Left
      ctx.beginPath();
      ctx.moveTo(x, y + h - corner); ctx.lineTo(x, y + h); ctx.lineTo(x + corner, y + h);
      ctx.stroke();

      // Bottom-Right
      ctx.beginPath();
      ctx.moveTo(x + w - corner, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - corner);
      ctx.stroke();

      ctx.restore();
    }
  }

  resetUI() {
    this.targetBBox = null;
    this.currentBBox = null;
    if (this.el.redAlertBanner) this.el.redAlertBanner.style.display = 'none';
    if (this.el.hudRedAlertTag) this.el.hudRedAlertTag.style.display = 'none';
    if (this.el.videoWrapper) this.el.videoWrapper.classList.remove('video-deepfake-alert');
    if (this.el.hudInfo) this.el.hudInfo.style.display = 'none';
    if (this.el.scanLine) this.el.scanLine.style.display = 'none';
    if (this.el.webcamVideo) this.el.webcamVideo.style.display = 'none';
    if (this.el.overlayCanvas) this.el.overlayCanvas.style.display = 'none';
    if (this.el.videoPlaceholder) this.el.videoPlaceholder.style.display = 'flex';
    if (this.el.toggleDetectionBtn) {
      this.el.toggleDetectionBtn.innerHTML = '▶ Start Detection';
      this.el.toggleDetectionBtn.style.background = '';
    }
    this.updateConnectionStatus(Config.CONNECTION_STATES.STOPPED);
  }
}

window.UIManager = UIManager;
