// DeepShield — Media Capture Manager Module
// Handles camera & microphone acquisition, MediaRecorder audio chunking, and offscreen frame extraction

class MediaCaptureManager {
  constructor() {
    this.stream = null;
    this.mediaRecorder = null;
    this.videoElement = null;
    this.captureCanvas = document.createElement('canvas');
    this.captureCanvas.width = Config.STREAM.VIDEO_WIDTH;
    this.captureCanvas.height = Config.STREAM.VIDEO_HEIGHT;
    this.captureCtx = this.captureCanvas.getContext('2d');

    this.onAudioChunkCallback = null;
    this.onDeviceDisconnectedCallback = null;
    this.cameraActive = false;
    this.micActive = false;
  }

  setAudioChunkCallback(callback) {
    this.onAudioChunkCallback = callback;
  }

  setDeviceDisconnectedCallback(callback) {
    this.onDeviceDisconnectedCallback = callback;
  }

  async startCapture(videoElement) {
    this.videoElement = videoElement;

    // Reset previous states
    this.stopCapture();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (window.location.protocol === 'file:') {
        throw new Error('Camera & Mic access is restricted on file:// URLs by your browser. Please open http://localhost:8050');
      }
      throw new Error('Camera & Mic are not supported or blocked in this browser context. Please use Chrome/Edge on http://localhost:8050');
    }

    let stream = null;
    let cameraAllowed = false;
    let micAllowed = false;

    // 1. Attempt combined audio + video capture
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: Config.STREAM.VIDEO_WIDTH },
          height: { ideal: Config.STREAM.VIDEO_HEIGHT },
          facingMode: 'user'
        },
        audio: {
          echoCancellation: true,
          noiseSuppression: true
        }
      });
      cameraAllowed = true;
      micAllowed = true;
    } catch (err) {
      console.warn('[MediaManager] Combined getUserMedia failed, checking individual devices:', err);

      // 2. Fallback: Try Video only
      try {
        const videoStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: Config.STREAM.VIDEO_WIDTH },
            height: { ideal: Config.STREAM.VIDEO_HEIGHT },
            facingMode: 'user'
          }
        });
        stream = videoStream;
        cameraAllowed = true;
      } catch (vidErr) {
        throw new Error(`Camera access failed: ${vidErr.name || vidErr.message}`);
      }

      // 3. Fallback: Try Audio separately
      try {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStream.getAudioTracks().forEach(track => stream.addTrack(track));
        micAllowed = true;
      } catch (audErr) {
        console.warn('[MediaManager] Microphone access denied or unavailable:', audErr);
        micAllowed = false;
      }
    }

    this.stream = stream;
    this.cameraActive = cameraAllowed;
    this.micActive = micAllowed;

    // Bind to video element
    if (this.videoElement) {
      this.videoElement.srcObject = this.stream;
      this.videoElement.style.display = 'block';
      await this.videoElement.play().catch(e => console.warn('Video play warning:', e));
    }

    // Monitor hardware track disconnection (e.g. webcam unplugged)
    this.stream.getTracks().forEach(track => {
      track.addEventListener('ended', () => {
        console.warn(`[MediaManager] Device track ${track.kind} ended.`);
        if (track.kind === 'video') this.cameraActive = false;
        if (track.kind === 'audio') this.micActive = false;
        if (this.onDeviceDisconnectedCallback) {
          this.onDeviceDisconnectedCallback(track.kind);
        }
      });
    });

    // 4. Initialize MediaRecorder for ~2-second audio slices
    if (micAllowed && this.stream.getAudioTracks().length > 0) {
      try {
        const mimeType = this._getSupportedAudioMime();
        this.mediaRecorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : {});

        this.mediaRecorder.ondataavailable = async (event) => {
          if (event.data && event.data.size > 0 && this.onAudioChunkCallback) {
            try {
              const wavBlob = window.audioBlobToWav ? await window.audioBlobToWav(event.data) : event.data;
              const base64Audio = await this._blobToBase64(wavBlob);
              this.onAudioChunkCallback(base64Audio);
            } catch (err) {
              console.warn('[MediaManager] Failed to encode audio chunk:', err);
            }
          }
        };

        this.mediaRecorder.start(Config.STREAM.AUDIO_CHUNK_MS);
        console.log(`[MediaManager] MediaRecorder started with ${Config.STREAM.AUDIO_CHUNK_MS}ms timeslice.`);
      } catch (recErr) {
        console.warn('[MediaManager] MediaRecorder init failed:', recErr);
      }
    }

    return {
      camera: this.cameraActive,
      microphone: this.micActive
    };
  }

  captureFrameBase64() {
    if (!this.stream || !this.videoElement || !this.cameraActive) {
      return null;
    }

    const vw = this.videoElement.videoWidth || Config.STREAM.VIDEO_WIDTH;
    const vh = this.videoElement.videoHeight || Config.STREAM.VIDEO_HEIGHT;

    if (vw === 0 || vh === 0) return null;

    // Draw downscaled 640x360 frame
    this.captureCtx.drawImage(
      this.videoElement,
      0, 0, vw, vh,
      0, 0, Config.STREAM.VIDEO_WIDTH, Config.STREAM.VIDEO_HEIGHT
    );

    return this.captureCanvas.toDataURL('image/jpeg', Config.STREAM.JPEG_QUALITY);
  }

  stopCapture() {
    if (this.mediaRecorder) {
      try {
        if (this.mediaRecorder.state !== 'inactive') {
          this.mediaRecorder.stop();
        }
      } catch (_) {}
      this.mediaRecorder = null;
    }

    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        try { track.stop(); } catch (_) {}
      });
      this.stream = null;
    }

    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.srcObject = null;
    }

    this.cameraActive = false;
    this.micActive = false;
  }

  _getSupportedAudioMime() {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4'
    ];
    for (const mime of candidates) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) {
        return mime;
      }
    }
    return '';
  }

  _blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }
}

window.MediaCaptureManager = MediaCaptureManager;
