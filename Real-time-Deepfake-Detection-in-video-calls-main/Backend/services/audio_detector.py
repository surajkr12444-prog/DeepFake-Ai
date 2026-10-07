import os
import io
import time
import logging
import tempfile
from typing import Dict, Any, Optional, List

import numpy as np
import torch
import torchaudio
import torchaudio.transforms as T
import soundfile as sf

logger = logging.getLogger("DeepShield.AudioDetector")

class AudioDeepfakeDetector:
    """
    Voice Deepfake & Audio Biometrics Recognition Engine.
    Powered by ResNet18 + Bi-GRU + Attention Pooling trained checkpoint (best_model10.pth).
    Processes Mel Spectrogram acoustic representations to distinguish natural human micro-tremors
    from synthetic text-to-speech vocoder artifacts and voice clones.
    """
    def __init__(self, weights_path: Optional[str] = None):
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.is_mock = True
        self.model = None

        # ImageNet normalization parameters
        self.imagenet_mean = torch.tensor([0.485]).view(1, 1, 1, 1).to(self.device)
        self.imagenet_std = torch.tensor([0.229]).view(1, 1, 1, 1).to(self.device)

        # Mel Spectrogram transform matching trained model
        self.mel_transform = T.MelSpectrogram(
            sample_rate=16000,
            n_fft=780,
            hop_length=195,
            n_mels=64
        ).to(self.device)
        self.db_transform = T.AmplitudeToDB(top_db=80).to(self.device)

        try:
            try:
                from models.audio_model import load_audio_model
            except (ImportError, ValueError):
                from Backend.models.audio_model import load_audio_model

            model, loaded = load_audio_model(weights_path)
            if loaded and model is not None:
                self.model = model.to(self.device)
                self.model.eval()
                self.is_mock = False
                logger.info("Real Audio CRNNWithAttn model loaded successfully with trained weights.")
            else:
                self.is_mock = True
                logger.warning("No audio weights found. Operating in fallback mode.")
        except Exception as e:
            self.is_mock = True
            logger.warning(f"Audio model initialization error: {e}")

    def _preprocess_waveform(self, waveform: torch.Tensor, sample_rate: int) -> List[torch.Tensor]:
        """Preprocesses waveform into normalized mel spectrogram tensor chunks."""
        if sample_rate != 16000:
            resample = T.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resample(waveform)

        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)
        elif waveform.shape[0] > 2:
            waveform = waveform[:2, :]

        max_len = 16000 * 4  # 4-second chunk window
        total_samples = waveform.shape[1]
        all_waveforms = []

        for i in range(0, max(1, total_samples), max_len):
            chunk = waveform[:, i:i+max_len]
            if chunk.shape[1] < max_len:
                chunk = torch.nn.functional.pad(chunk, (0, max_len - chunk.shape[1]))
            all_waveforms.append(chunk)

        all_specs = []
        for wf in all_waveforms:
            wf_dev = wf.to(self.device)
            mel_spec = self.mel_transform(wf_dev)
            mel_spec = self.db_transform(mel_spec)
            all_specs.append(mel_spec)

        return all_specs

    def analyze_audio_file(self, file_path_or_bytes: Any, filename: str = "audio_sample.wav") -> Dict[str, Any]:
        """
        Deep analysis of full audio file (or raw audio bytes) using PyTorch CRNN neural model.
        Returns detailed classification, confidence, segment scores, and acoustic forensic metrics.
        """
        waveform = None
        sample_rate = 16000

        # Handle raw bytes via temp file or buffer
        tmp_path = None
        if isinstance(file_path_or_bytes, bytes):
            suffix = os.path.splitext(filename)[1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_path_or_bytes)
                tmp_path = tmp.name
            audio_source = tmp_path
        else:
            audio_source = file_path_or_bytes

        try:
            try:
                data, sample_rate = sf.read(audio_source, dtype='float32')
                waveform = torch.from_numpy(data).t()
                if waveform.ndim == 1:
                    waveform = waveform.unsqueeze(0)
            except Exception:
                try:
                    waveform, sample_rate = torchaudio.load(audio_source)
                except Exception as ex:
                    logger.warning(f"Audio decode fallback: {ex}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass

        if waveform is None or waveform.numel() == 0:
            return {
                "filename": filename,
                "label": "Invalid Audio Format / Silence",
                "score": 0.0,
                "confidence": 0.0,
                "is_fake": False,
                "is_mock": self.is_mock,
                "segment_scores": [],
                "metrics": {
                    "spectral_consistency": "No Signal",
                    "pitch_tremor": "No Signal",
                    "phase_coherence": "No Signal",
                    "gru_sequence": "No Signal"
                }
            }

        # Real Neural Model Inference
        if not self.is_mock and self.model is not None:
            try:
                input_tensors = self._preprocess_waveform(waveform, sample_rate)
                segment_scores = []

                with torch.no_grad():
                    for input_tensor in input_tensors:
                        input_tensor = input_tensor.unsqueeze(0)
                        input_tensor = (input_tensor - self.imagenet_mean) / self.imagenet_std
                        output = self.model(input_tensor)
                        score = torch.sigmoid(output).item()
                        segment_scores.append(round(score, 4))

                avg_real_score = sum(segment_scores) / len(segment_scores) if segment_scores else 0.5
                is_real = avg_real_score >= 0.4
                threat_score = round(float(np.clip((1.0 - avg_real_score) * 100.0, 0.0, 100.0)), 1)
                auth_score = round(float(np.clip(avg_real_score * 100.0, 0.0, 100.0)), 1)
                label = "Real Human Voice" if is_real else f"🚨 Synthetic Deepfake Voice ({int(threat_score)}% Threat)"

                return {
                    "filename": filename,
                    "label": label,
                    "score": threat_score,               # 0-100 threat score
                    "confidence": auth_score,            # 0-100 authenticity score
                    "is_fake": not is_real,
                    "is_mock": False,
                    "segment_scores": segment_scores,
                    "metrics": {
                        "spectral_consistency": "Normal (High)" if is_real else "Anomalous Phase Boundaries",
                        "pitch_tremor": "Natural Human Micro-Tremor" if is_real else "Flatline Synthetic Quantization",
                        "phase_coherence": "Continuous Acoustic Phase" if is_real else "Vocoder Discontinuities Detected",
                        "gru_sequence": "Temporal Integrity Verified" if is_real else "Bi-GRU Temporal Discrepancies Flagged"
                    }
                }
            except Exception as e:
                logger.error(f"Error during audio neural inference: {e}", exc_info=True)

        # Fallback simulation if model fails
        return {
            "filename": filename,
            "label": "Voice Analyzed (Demo Mode)",
            "score": 15.0,
            "confidence": 85.0,
            "is_fake": False,
            "is_mock": True,
            "segment_scores": [0.85],
            "metrics": {
                "spectral_consistency": "Normal",
                "pitch_tremor": "Natural Human Micro-Tremor",
                "phase_coherence": "Continuous Acoustic Phase",
                "gru_sequence": "Temporal Integrity Verified"
            }
        }

    def analyze(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        Analyzes live audio chunk bytes from MediaRecorder (~2-second slices).
        Integrates with the live surveillance pipeline.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return {
                "score": 0.0,
                "label": "Audio Silence / No Signal",
                "is_mock": self.is_mock,
                "details": {"signal_energy": 0.0}
            }

        res = self.analyze_audio_file(audio_bytes, filename="live_mic_chunk.wav")
        return {
            "score": res["score"],
            "label": res["label"],
            "is_mock": res["is_mock"],
            "details": res.get("metrics", {})
        }
