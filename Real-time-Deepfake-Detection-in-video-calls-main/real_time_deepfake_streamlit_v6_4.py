"""
Real-Time Deepfake Detection v6.4 (Root Wrapper)
Executes Backend/real_time_deepfake_streamlit_v6_4.py seamlessly.
"""

import sys
import os

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

v6_path = os.path.join(backend_dir, "real_time_deepfake_streamlit_v6_4.py")
if os.path.exists(v6_path):
    os.chdir(backend_dir)
    with open(v6_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, v6_path, "exec"), globals())
