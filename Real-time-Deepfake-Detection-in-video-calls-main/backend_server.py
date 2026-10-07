"""
DeepShield — Real-Time Deepfake Detection System Root Entry Point
Executes the Backend/backend_server.py with full environment and path resolution.
"""

import sys
import os

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    import uvicorn
    # Change working directory to Backend so relative file paths (refs, logs) resolve correctly
    os.chdir(backend_dir)
    # Configure UTF-8 stdout if available
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    print("=" * 60)
    print("[DeepShield] AI Forensic Server Starting...")
    print("Server URL: http://localhost:8050")
    print("Frontend:   http://localhost:8050")
    print("=" * 60)
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8050, reload=False)
