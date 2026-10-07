# 🎭 DeepShield — Real-Time Deepfake Detection in Video Calls

A state-of-the-art real-time deepfake detection system that analyzes live webcam streams and pre-recorded AI video files using computer vision and multi-cue forensic AI models (2D FFT spectral analysis, Laplacian skin texture smoothness, boundary mask seams, and micro-motion liveness).

---

## 🚀 Quick Start (One-Click)

### Option 1: Modern Web Operations Center (Recommended)
You can start the full system and open the dashboard in **1 click**:

- **On Windows**: Simply double-click **`run_backend.bat`**
- **Or via Terminal**:
  ```powershell
  python run.py
  ```
This starts the AI Forensic Backend Server and automatically opens [http://localhost:8050](http://localhost:8050) in your web browser.

### Option 2: Run Backend Server Manually
```powershell
python backend_server.py
```
Then navigate to **http://localhost:8050** in your browser.

### Option 3: Streamlit Interface
```powershell
streamlit run real_time_deepfake_streamlit_v2.py
# or
streamlit run real_time_deepfake_streamlit_v6_4.py
```

---

## ✨ Features & Capabilities

- 🔍 **Multi-Cue Forensic Detection Core**:
  - **2D Fast Fourier Transform (FFT) Spectral Analysis**: Analyzes high-frequency roll-off to catch GAN, Diffusion, and StyleGAN generator artifacts.
  - **Laplacian Skin Gradient Smoothing**: Distinguishes natural skin pores from AI over-smoothing and blurring filters.
  - **Boundary Mask Seam Disparity**: Detects color disparity and edge seams around face-swapped margins.
  - **Temporal Liveness Analysis**: Flags static photo spoofing and recorded screen replays.
- 🚨 **Red Caution / Red Alert System**:
  - Prominent flashing red siren caution banner when an AI deepfake video is detected.
  - Animated flashing crimson siren borders on the video player feed.
  - Red HUD target bounding box and watermark tags directly over suspicious faces.
- 📁 **Test Pre-Recorded AI Video Files**:
  - Click **"📁 Test Video File"** on the dashboard to test downloaded MP4/WebM/AVI AI deepfake videos in a continuous loop without needing a webcam.
- 📸 **1-Click Face Enrollment**:
  - Enroll authorized faces into the reference directory (`Backend/refs/`) for identity verification.
- 📊 **Real-Time Analytics & Audit Export**:
  - Real-time confidence timeline charts, threat scoring, CSV log downloads, and audit reports.

---

## 📂 Project Architecture

```
Real-time-Deepfake-Detection/
├── run.py                              # One-click launcher (starts server + opens browser)
├── run_backend.bat                     # Windows 1-click batch launcher
├── backend_server.py                   # Root FastAPI backend entry point
├── real_time_deepfake_streamlit_v2.py   # Enhanced Streamlit app (Webcam + Video test)
├── real_time_deepfake_streamlit_v6_4.py # Streamlit v6.4 application wrapper
├── requirements.txt                    # Project dependencies
│
├── Backend/                            # Core AI Forensic & Backend Engine
│   ├── backend_server.py               # FastAPI server (port 8050)
│   ├── test_backend.py                 # Automated backend test suite (13/13 passing)
│   ├── detection_log.csv               # Historical detection audit logs
│   ├── Deepfake_Report.txt             # Forensic summary reports
│   ├── refs/                           # Trusted reference portraits
│   └── real_time_deepfake_streamlit_*.py
│
└── Frontend/                           # Cyberpunk Operations Center UI
    ├── index.html                      # Glassmorphic layout & Red Alert banner
    ├── style.css                       # Glowing cyberpunk theme & siren animations
    └── script.js                       # Deterministic vision engine & Red Caution triggers
```

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, Uvicorn, Python 3.10+
- **Computer Vision**: OpenCV, 2D FFT Frequency Analysis, SciPy
- **Frontend**: Vanilla HTML5, CSS3 Glassmorphism, JavaScript (ES6 Canvas & WebRTC)
- **Data & Reports**: NumPy, Pandas, CSV audit logging

---

## 📘 How the AI Detection Works

1. **Video Ingestion**: Reads live webcam frames via WebRTC or decoded frames from an uploaded video file.
2. **Face Extraction**: Extracts facial ROI and boundary margins using Haar Cascades with adaptive skin-tone contours.
3. **Forensic Multi-Cue Extraction**:
   - Converts to frequency domain via 2D FFT to inspect radial power spectral distribution.
   - Computes Laplacian variance across eye regions versus cheeks to detect synthetic over-smoothing.
   - Computes YCrCb color distance between face and surrounding margin to flag face-swap seams.
   - Evaluates frame-to-frame diffs for temporal liveness.
4. **Threat Scoring & Exponential Moving Average (EMA)**:
   - Weights and smooths signals ($\alpha = 0.35$) for consistent, zero-jitter predictions.
5. **Red Alert Execution**:
   - If manipulation artifacts are confirmed, system immediately executes the **Red Caution** visual alarm.

---

## 🙌 Author
**Sumaira Ashfaque**  
AI & Software Developer
