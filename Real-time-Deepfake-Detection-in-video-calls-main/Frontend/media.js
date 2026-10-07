// DeepShield — Media Capture Manager Module
// Handles camera & microphone acquisition, Web Audio 16kHz PCM streaming, and offscreen frame extraction

class MediaCaptureManager {
  constructor() {
    this.stream = null;
    this.audioOnlyStream = null;
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

    // Web Audio Direct PCM streaming nodes
    this.audioSourceNode = null;
    this.audioScriptNode = null;
    this.pcmBuffer = [];
    this.micVolume = 0;
  }

  setAudioChunkCallback(callback) {
    this.onAudioChunkCallback = callback;
  }

  setDeviceDisconnectedCallback(callback) {
    this.onDeviceDisconnectedCallback = callback;
  }

  async startCapture(videoElement) {
    this.videoElement = videoElement;

    // Reset previous states cleanly
    this.stopCapture();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (window.location.protocol === 'file:') {
        throw new Error('Camera & Mic access is restricted on file:// URLs by your browser. Please open http://localhost:8050');
      }
      throw new Error('Camera & Mic are not supported or blocked in this browser context. Please use Chrome or Edge on http://localhost:8050');
    }

    let cameraAllowed = false;
    let micAllowed = false;
    let videoStream = null;
    let audioStream = null;

    // 1. Independent Camera Acquisition
    try {
      videoStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: Config.STREAM.VIDEO_WIDTH },
          height: { ideal: Config.STREAM.VIDEO_HEIGHT },
          facingMode: 'user'
        }
      });
      cameraAllowed = true;
    } catch (vidErr) {
      console.warn('[MediaManager] Video camera unavailable or denied:', vidErr);
      cameraAllowed = false;
    }

    // 2. Independent Microphone Acquisition
    try {
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      micAllowed = true;
    } catch (audErr) {
      console.warn('[MediaManager] Microphone access unavailable or denied:', audErr);
      micAllowed = false;
    }

    if (!cameraAllowed && !micAllowed) {
      throw new Error('Neither Camera nor Microphone could be accessed. Please check device permissions in your browser address bar.');
    }

    // 3. Assemble unified composite stream
    const compositeStream = new MediaStream();
    if (videoStream) {
      videoStream.getVideoTracks().forEach(t => compositeStream.addTrack(t));
    }
    if (audioStream) {
      audioStream.getAudioTracks().forEach(t => compositeStream.addTrack(t));
    }

    this.stream = compositeStream;
    this.cameraActive = cameraAllowed;
    this.micActive = micAllowed;

    // Bind to video element if video is available
    if (this.videoElement && cameraAllowed) {
      this.videoElement.srcObject = this.stream;
      this.videoElement.style.display = 'block';
      await this.videoElement.play().catch(e => console.warn('[MediaManager] Video play warning:', e));
    }

    // Monitor hardware track disconnection (e.g. webcam or mic unplugged)
    this.stream.getTracks().forEach(track => {
      track.addEventListener('ended', () => {
        console.warn(`[MediaManager] Device track ${track.kind} ended.`);
        if (track.kind === 'video') this.cameraActive = false;
        if (track.kind === 'audio') {
          this.micActive = false;
          this._stopAudioProcessor();
        }
        if (this.onDeviceDisconnectedCallback) {
          this.onDeviceDisconnectedCallback(track.kind);
        }
      });
    });

    // 4. Initialize Live Microphone Streamer
    if (micAllowed && this.stream.getAudioTracks().length > 0) {
      this._startAudioProcessor();
    }

    return {
      camera: this.cameraActive,
      microphone: this.micActive
    };
  }

  _startAudioProcessor() {
    this._stopAudioProcessor();

    const audioTracks = this.stream.getAudioTracks();
    if (audioTracks.length === 0) return;

    try {
      // Audio-only stream to avoid video mime conflicts
      this.audioOnlyStream = new MediaStream(audioTracks);

      const audioCtx = window.getSharedAudioContext
        ? window.getSharedAudioContext()
        : new (window.AudioContext || window.webkitAudioContext)();

      if (audioCtx.state === 'suspended') {
        audioCtx.resume().catch(() => {});
      }

      const source = audioCtx.createMediaStreamSource(this.audioOnlyStream);
      const bufferSize = 4096;
      const scriptNode = audioCtx.createScriptProcessor(bufferSize, 1, 1);
      this.audioSourceNode = source;
      this.audioScriptNode = scriptNode;

      const targetSampleRate = 16000;
      const inputSampleRate = audioCtx.sampleRate;
      const ratio = inputSampleRate / targetSampleRate;
      this.pcmBuffer = [];
      const targetChunkSamples = targetSampleRate * 2; // ~2.0 seconds = 32,000 samples

      scriptNode.onaudioprocess = async (event) => {
        if (!this.micActive) return;
        const inputData = event.inputBuffer.getChannelData(0);

        // Calculate current microphone RMS volume
        let sumSq = 0;
        for (let i = 0; i < inputData.length; i++) {
          sumSq += inputData[i] * inputData[i];
        }
        this.micVolume = Math.sqrt(sumSq / inputData.length);

        // Downsample to 16kHz
        for (let i = 0; i < inputData.length; i += ratio) {
          this.pcmBuffer.push(inputData[Math.floor(i)]);
        }

        // When ~2.0 seconds accumulated, dispatch pristine 16-bit PCM WAV chunk
        if (this.pcmBuffer.length >= targetChunkSamples) {
          const chunkPcm = new Float32Array(this.pcmBuffer.slice(0, targetChunkSamples));
          this.pcmBuffer = this.pcmBuffer.slice(targetChunkSamples);

          try {
            const wavBlob = window.pcmToWavBlob ? window.pcmToWavBlob(chunkPcm, targetSampleRate) : null;
            if (wavBlob && this.onAudioChunkCallback) {
              const base64Audio = await this._blobToBase64(wavBlob);
              this.onAudioChunkCallback(base64Audio);
            }
          } catch (encodeErr) {
            console.warn('[MediaManager] Audio PCM WAV encode error:', encodeErr);
          }
        }
      };

      source.connect(scriptNode);
      scriptNode.connect(audioCtx.destination);
      console.log('[MediaManager] Direct Web Audio 16kHz Mono PCM live microphone pipeline engaged.');

    } catch (procErr) {
      console.warn('[MediaManager] Direct Web Audio processor failed, falling back to MediaRecorder:', procErr);
      this._startFallbackMediaRecorder(audioTracks);
    }
  }

  _startFallbackMediaRecorder(audioTracks) {
    try {
      this.audioOnlyStream = new MediaStream(audioTracks);
      const mimeType = this._getSupportedAudioMime();
      this.mediaRecorder = new MediaRecorder(this.audioOnlyStream, mimeType ? { mimeType } : {});

      this.mediaRecorder.ondataavailable = async (event) => {
        if (event.data && event.data.size > 0 && this.onAudioChunkCallback) {
          try {
            const wavBlob = window.audioBlobToWav ? await window.audioBlobToWav(event.data) : event.data;
            const base64Audio = await this._blobToBase64(wavBlob);
            this.onAudioChunkCallback(base64Audio);
          } catch (err) {
            console.warn('[MediaManager] Fallback audio chunk encode error:', err);
          }
        }
      };

      this.mediaRecorder.start(Config.STREAM.AUDIO_CHUNK_MS || 2000);
      console.log('[MediaManager] Fallback MediaRecorder active.');
    } catch (recErr) {
      console.warn('[MediaManager] Fallback MediaRecorder also failed:', recErr);
    }
  }

  _stopAudioProcessor() {
    if (this.audioSourceNode && this.audioScriptNode) {
      try {
        this.audioSourceNode.disconnect();
        this.audioScriptNode.disconnect();
      } catch (_) {}
      this.audioSourceNode = null;
      this.audioScriptNode = null;
    }
    this.pcmBuffer = [];
    this.micVolume = 0;
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
    this._stopAudioProcessor();

    if (this.mediaRecorder) {
      try {
        if (this.mediaRecorder.state !== 'inactive') {
          this.mediaRecorder.stop();
        }
      } catch (_) {}
      this.mediaRecorder = null;
    }

    if (this.audioOnlyStream) {
      this.audioOnlyStream.getTracks().forEach(track => {
        try { track.stop(); } catch (_) {}
      });
      this.audioOnlyStream = null;
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
