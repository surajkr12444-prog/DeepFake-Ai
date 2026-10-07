"""
DeepShield — One-Click Launcher
Starts the AI Forensic Backend Server and opens the Web Operations Center in your browser.
"""

import sys
import os
import time
import webbrowser
import threading

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def open_browser():
    time.sleep(1.2)
    url = "http://localhost:8050"
    print(f"\n🌐 Opening DeepShield Operations Center: {url}\n")
    webbrowser.open(url)

if __name__ == "__main__":
    os.chdir(backend_dir)
    threading.Thread(target=open_browser, daemon=True).start()

    print("=" * 65)
    print("🛡️  DeepShield Real-Time Deepfake Detection System")
    print("🚀  AI Forensic Core Server: Online")
    print("📡  Web UI: http://localhost:8050")
    print("📁  Video File Testing: Available via '📁 Test Video File' button")
    print("=" * 65)

    import uvicorn
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8050, reload=False)
