"""
Real-Time Deepfake Detection System (Streamlit v2 Enhanced Wrapper)
Multi-Cue Forensic Analysis: 2D FFT Spectral + Skin Texture + Boundary Seam + Liveness
Features: Live Webcam Feed OR Upload/Play Video File with Real-Time Red Caution / Red Alert
"""

import sys
import os

# Add Backend to sys.path and run Backend/real_time_deepfake_streamlit_v2.py
backend_dir = os.path.join(os.path.dirname(__file__), "Backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

v2_path = os.path.join(backend_dir, "real_time_deepfake_streamlit_v2.py")
if os.path.exists(v2_path):
    with open(v2_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, v2_path, "exec"), globals())
