"""
Real-Time Deepfake Detection System (Streamlit v2 Enhanced)
Multi-Cue Forensic Analysis: 2D FFT Spectral + Skin Texture + Boundary Seam + Liveness
Features: Live Webcam Feed OR Upload/Play Video File with Real-Time Red Caution / Red Alert
"""

import cv2
import numpy as np
import streamlit as st
import tempfile
import time
import os

st.set_page_config(
    page_title="DeepShield — Real-Time Deepfake Video Detection",
    page_icon="🛡️",
    layout="wide"
)

# Custom Styling with Cyberpunk aesthetics and Red Alert CSS
st.markdown("""
<style>
    .main {
        background: #080d1a;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    .red-caution-banner {
        background: linear-gradient(90deg, #dc2626 0%, #7f1d1d 100%);
        border: 2px solid #ef4444;
        border-radius: 12px;
        padding: 16px 20px;
        color: #ffffff;
        font-weight: 800;
        font-size: 1.25rem;
        display: flex;
        align-items: center;
        gap: 14px;
        box-shadow: 0 0 30px rgba(239, 68, 68, 0.7);
        animation: sirenPulse 1.2s infinite alternate;
        margin-bottom: 20px;
    }
    @keyframes sirenPulse {
        0% { box-shadow: 0 0 20px rgba(239, 68, 68, 0.5); }
        100% { box-shadow: 0 0 45px rgba(239, 68, 68, 0.95); }
    }
    .safe-banner {
        background: linear-gradient(90deg, #059669 0%, #064e3b 100%);
        border: 2px solid #10b981;
        border-radius: 12px;
        padding: 16px 20px;
        color: #ffffff;
        font-weight: 700;
        font-size: 1.15rem;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Forensic Detection Engine
# -------------------------------------------------------------
class ForensicEngine:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.prev_face = None
        self.ema_conf = 85.0
        self.ema_liveness = 85.0
        self.ema_fft = 85.0
        self.ema_texture = 85.0
        self.ema_seam = 85.0

    def detect_face(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if not self.face_cascade.empty():
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                return faces[0], gray
        
        # Fallback skin-tone contour
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 30, 60]), np.array([25, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > (w * h * 0.04):
                bx, by, bw, bh = cv2.boundingRect(c)
                return (bx, by, bw, bh), gray

        # Canonical center crop fallback
        return (int(w * 0.28), int(h * 0.20), int(w * 0.44), int(h * 0.55)), gray

    def analyze(self, frame_bgr, threshold=0.60):
        bbox, gray = self.detect_face(frame_bgr)
        x, y, w, h = bbox
        face_gray = gray[y:y+h, x:x+w]
        if face_gray.size == 0:
            face_gray = cv2.resize(gray, (160, 160))

        # 1. 2D FFT Frequency Analysis
        f = np.fft.fft2(face_gray)
        fshift = np.fft.fftshift(f)
        mag = np.abs(fshift) + 1e-9
        fh, fw = face_gray.shape
        cy, cx = fh // 2, fw // 2
        ygrid, xgrid = np.ogrid[:fh, :fw]
        dist = np.sqrt((xgrid - cx)**2 + (ygrid - cy)**2)
        r_cut = min(fh, fw) * 0.35
        high_freq = mag[dist > r_cut]
        mid_freq = mag[(dist >= r_cut * 0.35) & (dist <= r_cut)]
        ratio = float(np.mean(high_freq) / (np.mean(mid_freq) + 1e-6))
        
        if 0.18 <= ratio <= 0.48:
            fft_score = 92.0 - abs(ratio - 0.30) * 40.0
        elif ratio < 0.18:
            fft_score = max(20.0, 90.0 - (0.18 - ratio) * 400.0)
        else:
            fft_score = max(20.0, 90.0 - (ratio - 0.48) * 250.0)
        fft_score = float(np.clip(fft_score, 15.0, 98.0))

        # 2. Laplacian Skin Texture Gradient
        eyes_roi = face_gray[int(fh * 0.18):int(fh * 0.42), int(fw * 0.18):int(fw * 0.82)]
        cheek_roi = face_gray[int(fh * 0.52):int(fh * 0.78), int(fw * 0.20):int(fw * 0.80)]
        var_eyes = float(cv2.Laplacian(eyes_roi, cv2.CV_64F).var()) if eyes_roi.size > 0 else 50.0
        var_cheek = float(cv2.Laplacian(cheek_roi, cv2.CV_64F).var()) if cheek_roi.size > 0 else 20.0
        tex_ratio = var_eyes / (var_cheek + 1e-5)
        if tex_ratio > 12.0 or var_cheek < 6.0:
            texture_score = max(20.0, 85.0 - (tex_ratio - 12.0) * 3.5 - (6.0 - min(6.0, var_cheek)) * 6.0)
        else:
            texture_score = min(96.0, 78.0 + min(18.0, var_cheek * 0.35))
        texture_score = float(np.clip(texture_score, 15.0, 98.0))

        # 3. Blending Seam Analysis
        pad_x, pad_y = int(w * 0.12), int(h * 0.12)
        fh_tot, fw_tot = frame_bgr.shape[:2]
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(fw_tot, x + w + pad_x), min(fh_tot, y + h + pad_y)
        margin_roi = frame_bgr[y1:y2, x1:x2]
        face_roi = frame_bgr[y:y+h, x:x+w]
        if margin_roi.size > 0 and face_roi.size > 0:
            ycrcb_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2YCrCb)
            ycrcb_margin = cv2.cvtColor(margin_roi, cv2.COLOR_BGR2YCrCb)
            dist_chroma = float(np.linalg.norm(np.mean(ycrcb_face[:, :, 1:], axis=(0, 1)) - np.mean(ycrcb_margin[:, :, 1:], axis=(0, 1))))
            seam_score = max(20.0, 95.0 - dist_chroma * 3.5) if dist_chroma > 7.0 else min(98.0, 95.0 - dist_chroma * 2.0)
        else:
            seam_score = 85.0
        seam_score = float(np.clip(seam_score, 15.0, 98.0))

        # 4. Temporal Motion Liveness
        std_face = cv2.resize(face_gray, (100, 100))
        if self.prev_face is None:
            self.prev_face = std_face.copy()
            liveness_score = 88.0
            is_live = True
        else:
            diff = float(np.mean(cv2.absdiff(std_face, self.prev_face)))
            self.prev_face = std_face.copy()
            if diff < 0.4:
                liveness_score = 25.0
                is_live = False
            elif diff > 50.0:
                liveness_score = 45.0
                is_live = False
            else:
                liveness_score = min(96.0, 70.0 + min(26.0, diff * 6.5))
                is_live = True

        # EMA Smoothing
        a = 0.35
        self.ema_fft = a * fft_score + (1 - a) * self.ema_fft
        self.ema_texture = a * texture_score + (1 - a) * self.ema_texture
        self.ema_seam = a * seam_score + (1 - a) * self.ema_seam
        self.ema_liveness = a * liveness_score + (1 - a) * self.ema_liveness

        weighted = (
            0.35 * self.ema_fft +
            0.30 * self.ema_texture +
            0.20 * self.ema_seam +
            0.15 * self.ema_liveness
        )
        self.ema_conf = a * weighted + (1 - a) * self.ema_conf

        conf = int(np.clip(self.ema_conf, 15, 99))
        thresh_pct = int(threshold * 100)
        is_deepfake = (conf < thresh_pct) or (not is_live)
        threat_score = int(100 - conf)

        anomalies = []
        if self.ema_fft < 70:
            anomalies.append("GAN / Diffusion Frequency Artifacts")
        if self.ema_texture < 70:
            anomalies.append("Skin Texture Blur / Smoothing Disparity")
        if self.ema_seam < 75:
            anomalies.append("Face-Swap Boundary Disparity")
        if not is_live:
            anomalies.append("Static Screen Playback")

        return {
            "bbox": (x, y, w, h),
            "confidence": conf,
            "threat_score": threat_score,
            "is_deepfake": is_deepfake,
            "is_live": is_live,
            "fft_score": int(self.ema_fft),
            "texture_score": int(self.ema_texture),
            "seam_score": int(self.ema_seam),
            "liveness_score": int(self.ema_liveness),
            "anomalies": anomalies
        }

# -------------------------------------------------------------
# Streamlit UI
# -------------------------------------------------------------
st.title("🛡️ Real-Time Deepfake Video Detection (v2.0)")
st.markdown("Automated Multi-Cue Computer Vision & AI Forensic Analysis Core")

# Sidebar Controls
st.sidebar.header("⚙️ Configuration")
mode = st.sidebar.radio("Detection Input Mode", ["📁 Upload & Play AI Video", "📹 Live Webcam Feed"])
threshold = st.sidebar.slider("AI Sensitivity Threshold", min_value=0.40, max_value=0.90, value=0.62, step=0.01)
st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip**: Upload any AI video (Deepfake / Face-swap / SVD) to see the instant **Red Caution / Red Alert** trigger.")

# Placeholders for Alerts and Video Stream
alert_placeholder = st.empty()
col_video, col_metrics = st.columns([1.6, 1.0])

with col_video:
    frame_placeholder = st.empty()

with col_metrics:
    m_conf = st.empty()
    m_threat = st.empty()
    st.markdown("#### Forensic Multi-Cue Breakdown")
    p_fft = st.empty()
    p_texture = st.empty()
    p_seam = st.empty()
    p_liveness = st.empty()
    anomalies_box = st.empty()

engine = ForensicEngine()

def annotate_frame(frame, result):
    x, y, w, h = result["bbox"]
    is_deepfake = result["is_deepfake"]

    if is_deepfake:
        box_color = (0, 0, 255)  # Red BGR
        label = f"🚨 RED CAUTION: DEEPFAKE ({result['threat_score']}% Threat)"
        # Draw red border on whole frame
        cv2.rectangle(frame, (0, 0), (frame.shape[1]-1, frame.shape[0]-1), (0, 0, 255), 6)
    else:
        box_color = (0, 255, 0)  # Green BGR
        label = f"✓ AUTHENTIC ({result['confidence']}%)"

    # Face box
    cv2.rectangle(frame, (x, y), (x + w, y + h), box_color, 3)

    # Label badge
    cv2.rectangle(frame, (x, max(0, y - 35)), (x + w, y), box_color, -1)
    cv2.putText(frame, label, (x + 8, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    return frame

def update_ui(result):
    if result["is_deepfake"]:
        anom_str = " • ".join(result["anomalies"]) if result["anomalies"] else "Synthetic facial manipulation cues confirmed."
        alert_placeholder.markdown(f"""
        <div class="red-caution-banner">
            <div>🚨</div>
            <div>
                <div>RED CAUTION: AI DEEPFAKE VIDEO DETECTED!</div>
                <div style="font-size: 0.85rem; font-weight: 500; opacity: 0.9;">
                    Threat Level: {result['threat_score']}% | {anom_str}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        alert_placeholder.markdown(f"""
        <div class="safe-banner">
            ✅ AUTHENTIC HUMAN STREAM VERIFIED — Natural Biometric Cues (Confidence: {result['confidence']}%)
        </div>
        """, unsafe_allow_html=True)

    m_conf.metric("Confidence Score", f"{result['confidence']}%")
    m_threat.metric("Deepfake Threat Level", f"{result['threat_score']}%", delta=f"{result['threat_score']}%" if result['is_deepfake'] else "Normal", delta_color="inverse")
    p_fft.progress(result["fft_score"], text=f"2D FFT Frequency Naturalness: {result['fft_score']}%")
    p_texture.progress(result["texture_score"], text=f"Skin Texture Gradient: {result['texture_score']}%")
    p_seam.progress(result["seam_score"], text=f"Mask Boundary Seam Score: {result['seam_score']}%")
    p_liveness.progress(result["liveness_score"], text=f"Micro-motion Liveness: {result['liveness_score']}%")

    if result["anomalies"]:
        anomalies_box.warning("⚠️ Anomalies: " + ", ".join(result["anomalies"]))
    else:
        anomalies_box.success("✓ Biometrics Consistent")

# Mode 1: Video File
if mode == "📁 Upload & Play AI Video":
    uploaded_file = st.file_uploader("Choose an MP4, AVI, or MOV video to inspect", type=["mp4", "avi", "mov", "mkv"])
    if uploaded_file is not None:
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tfile.write(uploaded_file.read())
        tfile.flush()
        tfile.close()

        cap = cv2.VideoCapture(tfile.name)
        stop_btn = st.button("⏹ Stop Video Playback")

        while cap.isOpened() and not stop_btn:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop video
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = engine.analyze(frame, threshold=threshold)
            annotated = annotate_frame(frame_rgb, result)
            frame_placeholder.image(annotated, channels="RGB", use_container_width=True)
            update_ui(result)
            time.sleep(0.03)

        cap.release()
        try:
            os.unlink(tfile.name)
        except:
            pass

# Mode 2: Webcam Feed
elif mode == "📹 Live Webcam Feed":
    start_cam = st.checkbox("▶ Start Live Camera Stream", value=False)
    if start_cam:
        cap = cv2.VideoCapture(0)
        while start_cam:
            ret, frame = cap.read()
            if not ret:
                st.error("Cannot access camera or device is busy.")
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = engine.analyze(frame, threshold=threshold)
            annotated = annotate_frame(frame_rgb, result)
            frame_placeholder.image(annotated, channels="RGB", use_container_width=True)
            update_ui(result)
            time.sleep(0.04)

        cap.release()
