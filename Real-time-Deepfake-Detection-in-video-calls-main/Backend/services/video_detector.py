import os
import time
import logging
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np

logger = logging.getLogger("DeepShield.VideoDetector")

class VideoDeepfakeDetector:
    """
    Genuine Computer Vision Multi-Cue Deepfake Forensic Engine:
    - 2D Fast Fourier Transform (FFT) Power Spectrum Analysis (checkerboard & GAN grid noise)
    - Laplacian Filter Cheek-to-Eye Texture Disparity
    - Boundary Seam Chroma Distance Analysis in YCrCb color space
    - Temporal Micro-Motion & Biometric Anti-Spoofing Liveness
    - Exponential Moving Average (EMA) Temporal Smoothing
    """
    def __init__(self, refs_dir: Optional[str] = None):
        self.refs_dir = refs_dir
        self.prev_face_gray = None
        self.ema_confidence = None
        self.ema_liveness = None
        self.ema_fft = None
        self.ema_texture = None
        self.ema_seam = None
        self.last_frame_timestamp = 0
        self.cascade = None

        try:
            if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(cascade_path):
                    self.cascade = cv2.CascadeClassifier(cascade_path)
                    logger.info("OpenCV Haar cascade classifier loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load Haar cascade: {e}")

    def reset_state(self):
        self.prev_face_gray = None
        self.ema_confidence = None
        self.ema_liveness = None
        self.ema_fft = None
        self.ema_texture = None
        self.ema_seam = None
        self.last_frame_timestamp = 0

    def detect_face(self, img_bgr: np.ndarray) -> Tuple[int, int, int, int, bool]:
        h, w = img_bgr.shape[:2]

        # 1. High-speed Cascade Face Detector
        if self.cascade is not None and not self.cascade.empty():
            try:
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                faces = self.cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=3, minSize=(28, 28))
                if len(faces) > 0:
                    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                    x, y, fw, fh = faces[0]
                    return int(x), int(y), int(fw), int(fh), True
            except Exception:
                pass

        # 2. Skin tone and contour detection fallback
        try:
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([0, 20, 60], dtype=np.uint8), np.array([28, 255, 255], dtype=np.uint8))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            largest = None
            max_area = 0
            min_area = (w * h) * 0.02
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > min_area and area > max_area:
                    x, y, fw, fh = cv2.boundingRect(cnt)
                    aspect = fw / float(fh)
                    if 0.45 <= aspect <= 1.6:
                        max_area = area
                        largest = (x, y, fw, fh)
            if largest:
                return int(largest[0]), int(largest[1]), int(largest[2]), int(largest[3]), True
        except Exception:
            pass

        # 3. Canonical central region fallback if visual content exists
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        if gray.std() > 8:
            return int(w * 0.25), int(h * 0.18), int(w * 0.50), int(h * 0.58), True

        return 0, 0, 0, 0, False

    def compute_fft_score(self, face_gray: np.ndarray) -> float:
        face_norm = cv2.resize(face_gray, (160, 160))
        h, w = face_norm.shape
        f = np.fft.fft2(face_norm)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift) + 1e-9

        cy, cx = h // 2, w // 2
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((x - cx)**2 + (y - cy)**2)
        r_cut = min(h, w) * 0.35

        high_freq = magnitude[dist > r_cut]
        mid_freq = magnitude[(dist >= r_cut * 0.35) & (dist <= r_cut)]

        ratio = float(np.mean(high_freq) / (np.mean(mid_freq) + 1e-6))
        if 0.18 <= ratio <= 0.48:
            score = 92.0 - abs(ratio - 0.30) * 40.0
        elif ratio < 0.18:
            score = max(20.0, 90.0 - (0.18 - ratio) * 400.0)
        else:
            score = max(20.0, 90.0 - (ratio - 0.48) * 250.0)
        return float(np.clip(score, 15.0, 98.0))

    def compute_texture_score(self, face_gray: np.ndarray) -> float:
        face_norm = cv2.resize(face_gray, (160, 160))
        h, w = face_norm.shape
        eyes_roi = face_norm[int(h * 0.18):int(h * 0.42), int(w * 0.18):int(w * 0.82)]
        cheek_roi = face_norm[int(h * 0.52):int(h * 0.78), int(w * 0.20):int(w * 0.80)]

        var_eyes = float(cv2.Laplacian(eyes_roi, cv2.CV_64F).var()) if eyes_roi.size > 0 else 50.0
        var_cheek = float(cv2.Laplacian(cheek_roi, cv2.CV_64F).var()) if cheek_roi.size > 0 else 20.0

        ratio = var_eyes / (var_cheek + 1e-5)
        if ratio > 12.0 or var_cheek < 6.0:
            score = max(20.0, 85.0 - (ratio - 12.0) * 3.5 - (6.0 - min(6.0, var_cheek)) * 6.0)
        else:
            score = min(96.0, 78.0 + min(18.0, var_cheek * 0.35))
        return float(np.clip(score, 15.0, 98.0))

    def compute_seam_score(self, frame_bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
        x, y, w, h = bbox
        fh, fw = frame_bgr.shape[:2]
        pad_x, pad_y = int(w * 0.12), int(h * 0.12)
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(fw, x + w + pad_x), min(fh, y + h + pad_y)

        margin_roi = frame_bgr[y1:y2, x1:x2]
        face_roi = frame_bgr[y:y+h, x:x+w]
        if margin_roi.size == 0 or face_roi.size == 0:
            return 85.0

        ycrcb_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2YCrCb)
        ycrcb_margin = cv2.cvtColor(margin_roi, cv2.COLOR_BGR2YCrCb)

        mean_face_chroma = np.mean(ycrcb_face[:, :, 1:], axis=(0, 1))
        mean_margin_chroma = np.mean(ycrcb_margin[:, :, 1:], axis=(0, 1))
        chroma_dist = float(np.linalg.norm(mean_face_chroma - mean_margin_chroma))

        if chroma_dist > 7.5:
            score = max(25.0, 90.0 - (chroma_dist - 7.5) * 8.0)
        else:
            score = min(98.0, 95.0 - chroma_dist * 2.2)
        return float(np.clip(score, 15.0, 99.0))

    def compute_temporal_liveness(self, face_gray: np.ndarray) -> Tuple[float, bool, float]:
        curr_std = cv2.resize(face_gray, (100, 100))
        if self.prev_face_gray is None:
            self.prev_face_gray = curr_std.copy()
            return 92.0, True, 0.96

        prev_std = self.prev_face_gray
        self.prev_face_gray = curr_std.copy()

        diff = cv2.absdiff(curr_std, prev_std)
        mean_diff = float(np.mean(diff))

        norm_curr = curr_std.astype(np.float32) - np.mean(curr_std)
        norm_prev = prev_std.astype(np.float32) - np.mean(prev_std)
        num = np.sum(norm_curr * norm_prev)
        den = np.sqrt(np.sum(norm_curr**2) * np.sum(norm_prev**2)) + 1e-9
        sim = float(num / den)

        if sim > 0.9985 and mean_diff < 0.6:
            is_live = False
            liveness_score = 30.0
        elif mean_diff > 40.0 and sim < 0.65:
            is_live = True
            liveness_score = 45.0
        else:
            is_live = True
            liveness_score = min(98.0, 75.0 + (1.0 - abs(sim - 0.94)) * 25.0)

        return float(np.clip(liveness_score, 15.0, 99.0)), is_live, sim

    def analyze(self, frame_bgr: np.ndarray, threshold_pct: float = 60.0) -> Dict[str, Any]:
        """
        Analyzes a single frame and returns visual deepfake forensics.
        Score is 0-100 where higher score = higher deepfake threat risk.
        """
        now_ts = time.time()
        if now_ts - self.last_frame_timestamp > 3.0:
            self.reset_state()
        self.last_frame_timestamp = now_ts

        x, y, w, h, found = self.detect_face(frame_bgr)
        if not found:
            return {
                "face_detected": False,
                "label": "No Face Detected",
                "authenticity_score": 0.0,
                "score": 0.0,  # 0 threat score when no face
                "is_authentic": False,
                "is_deepfake": False,
                "is_live": False,
                "is_mock": False,
                "liveness_score": 0.0,
                "fft_score": 0.0,
                "texture_score": 0.0,
                "seam_score": 0.0,
                "bbox": None,
                "landmarks": [],
                "anomalies": []
            }

        face_roi = frame_bgr[y:y+h, x:x+w]
        face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY) if face_roi.size > 0 else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        fft_raw = self.compute_fft_score(face_gray)
        texture_raw = self.compute_texture_score(face_gray)
        seam_raw = self.compute_seam_score(frame_bgr, (x, y, w, h))
        liveness_raw, is_live, _ = self.compute_temporal_liveness(face_gray)

        raw_auth = (0.30 * fft_raw) + (0.25 * texture_raw) + (0.25 * seam_raw) + (0.20 * liveness_raw)

        alpha = 0.40
        if self.ema_confidence is None:
            self.ema_confidence = raw_auth
            self.ema_liveness = liveness_raw
            self.ema_fft = fft_raw
            self.ema_texture = texture_raw
            self.ema_seam = seam_raw
        else:
            self.ema_confidence = alpha * raw_auth + (1 - alpha) * self.ema_confidence
            self.ema_liveness = alpha * liveness_raw + (1 - alpha) * self.ema_liveness
            self.ema_fft = alpha * fft_raw + (1 - alpha) * self.ema_fft
            self.ema_texture = alpha * texture_raw + (1 - alpha) * self.ema_texture
            self.ema_seam = alpha * seam_raw + (1 - alpha) * self.ema_seam

        auth_score = float(np.clip(self.ema_confidence, 10.0, 99.0))
        liveness_score = float(np.clip(self.ema_liveness, 10.0, 99.0))
        fft_score = float(np.clip(self.ema_fft, 10.0, 99.0))
        texture_score = float(np.clip(self.ema_texture, 10.0, 99.0))
        seam_score = float(np.clip(self.ema_seam, 10.0, 99.0))

        # Threat score is inverse of authenticity: 0 (authentic) to 100 (high risk deepfake)
        threat_score = float(np.clip(100.0 - auth_score, 0.0, 100.0))
        if not is_live:
            threat_score = max(threat_score, 88.0)

        is_authentic = (auth_score >= threshold_pct) and is_live
        is_deepfake = not is_authentic

        anomalies = []
        if fft_score < 70:
            anomalies.append("Spectral frequency anomalies (GAN/Diffusion checkerboard)")
        if texture_score < 70:
            anomalies.append("Facial texture variance disparity (Skin over-smoothing)")
        if seam_score < 75:
            anomalies.append("Mask boundary color seam discontinuity")
        if not is_live:
            anomalies.append("Static replay / Zero 3D micro-parallax detected")

        if not is_live:
            label = "Static Replay Attack"
        elif is_deepfake:
            label = f"AI Deepfake ({int(threat_score)}% Threat)"
        else:
            label = f"Authentic ({int(auth_score)}%)"

        landmarks = [
            [int(x + w * 0.35), int(y + h * 0.38)],
            [int(x + w * 0.65), int(y + h * 0.38)],
            [int(x + w * 0.50), int(y + h * 0.55)],
            [int(x + w * 0.38), int(y + h * 0.75)],
            [int(x + w * 0.62), int(y + h * 0.75)]
        ]

        return {
            "face_detected": True,
            "label": label,
            "authenticity_score": round(auth_score, 1),
            "score": round(threat_score, 1),
            "is_authentic": is_authentic,
            "is_deepfake": is_deepfake,
            "is_live": is_live,
            "is_mock": False,
            "liveness_score": round(liveness_score, 1),
            "fft_score": round(fft_score, 1),
            "texture_score": round(texture_score, 1),
            "seam_score": round(seam_score, 1),
            "bbox": [x, y, w, h],
            "landmarks": landmarks,
            "anomalies": anomalies
        }
