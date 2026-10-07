import os
from typing import List

# Server Network Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8050"))

# Allowed CORS Origins (supports comma-separated list in env)
_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:8050,http://127.0.0.1:8050,http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://127.0.0.1:3000")
CORS_ORIGINS: List[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

# File Paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR) if os.path.basename(BACKEND_DIR).lower() == 'backend' else BACKEND_DIR
FRONTEND_DIR = os.path.join(ROOT_DIR, "Frontend")
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
REFS_DIR = os.path.join(BACKEND_DIR, "refs")
LOG_FILE = os.path.join(BACKEND_DIR, "detection_log.csv")
REPORT_FILE = os.path.join(BACKEND_DIR, "Deepfake_Report.txt")
VOICE_DIR = os.path.join(ROOT_DIR, "voice")
VOICE_MODEL_PATH = os.path.join(VOICE_DIR, "models", "best_model10.pth")


# Streaming & Live Surveillance Settings
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "2"))
DEFAULT_SENSITIVITY_THRESHOLD = float(os.getenv("DEFAULT_SENSITIVITY_THRESHOLD", "60.0"))
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "30"))
STALE_FRAME_DROP_ENABLED = True
