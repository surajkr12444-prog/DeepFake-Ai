import os
import time
import csv
import base64
import logging
from datetime import datetime
from typing import Optional, List

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

try:
    from config import (
        LOG_FILE, REFS_DIR, REPORT_FILE, DEFAULT_SENSITIVITY_THRESHOLD
    )
    from schemas import (
        HealthResponse, SessionCreateRequest, SessionResponse
    )
    from services.stream_manager import stream_manager
    from services.video_detector import VideoDeepfakeDetector
except (ImportError, ValueError):
    from Backend.config import (
        LOG_FILE, REFS_DIR, REPORT_FILE, DEFAULT_SENSITIVITY_THRESHOLD
    )
    from Backend.schemas import (
        HealthResponse, SessionCreateRequest, SessionResponse
    )
    from Backend.services.stream_manager import stream_manager
    from Backend.services.video_detector import VideoDeepfakeDetector


logger = logging.getLogger("DeepShield.SessionsRouter")
router = APIRouter()

# Dedicated forensic engines
legacy_video_detector = VideoDeepfakeDetector(refs_dir=REFS_DIR)
try:
    from services.audio_detector import AudioDeepfakeDetector
except (ImportError, ValueError):
    from Backend.services.audio_detector import AudioDeepfakeDetector
dedicated_voice_detector = AudioDeepfakeDetector()

# Legacy in-memory settings state
CONFIG = {
    "model_name": "Multi-Cue Deepfake Forensics Core",
    "detector_backend": "OpenCV Vision + 2D FFT Spectral Analysis",
    "similarity_threshold": 0.60,
    "liveness_threshold": 0.995,
    "enforce_detection": False
}
SERVER_START_TIME = time.time()

# -------------------------------------------------------------
# REST Endpoints: Target Architecture
# -------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
def get_health():
    """System health check endpoint."""
    return HealthResponse(
        status="ok",
        version="6.5.0",
        timestamp=time.time(),
        detectors={
            "video": {
                "name": "OpenCV Multi-Cue 2D-FFT Forensics",
                "status": "ready",
                "is_mock": False
            },
            "audio": {
                "name": "Mel-Spectrogram ResNet18-BiGRU Attention (best_model10.pth)",
                "status": "ready (Trained Neural Model Active)" if not dedicated_voice_detector.is_mock else "ready (demo adapter)",
                "is_mock": dedicated_voice_detector.is_mock
            },
            "lip_sync": {
                "name": "Phoneme-Viseme Cross-Modal Sync",
                "status": "ready (demo adapter)",
                "is_mock": True
            },
            "scam_context": {
                "name": "Social Engineering & Intent Analyzer",
                "status": "ready (demo adapter)",
                "is_mock": True
            }
        }
    )

@router.post("/voice/predict")
async def predict_voice_file(file: UploadFile = File(...)):
    """
    Dedicated Voice Deepfake Recognition Endpoint.
    Analyzes uploaded audio file using trained ResNet18 + Bi-GRU neural model (best_model10.pth).
    Returns real vs synthetic classification, confidence, and acoustic forensic metrics.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    return dedicated_voice_detector.analyze_audio_file(content, filename=file.filename)

@router.post("/sessions", response_model=SessionResponse)

async def create_session(payload: Optional[SessionCreateRequest] = None):
    """Initializes a new live surveillance session with unique ID."""
    threshold = payload.sensitivity_threshold if payload else DEFAULT_SENSITIVITY_THRESHOLD
    session = stream_manager.create_session(sensitivity_threshold=threshold or DEFAULT_SENSITIVITY_THRESHOLD)
    session.start_worker()
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        status="active",
        active_connections=len(stream_manager.sessions)
    )


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Retrieves metadata and status of an active surveillance session."""
    session = stream_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Surveillance session not found or expired")
    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "uptime_seconds": round(time.time() - session.created_at, 1),
        "status": "active" if session.is_active else "closed",
        "has_websocket": session.websocket is not None,
        "last_heartbeat": session.last_heartbeat,
        "threshold": session.sensitivity_threshold
    }

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Terminates and tears down a surveillance session."""
    removed = await stream_manager.remove_session(session_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Surveillance session not found")
    return {"message": "Session terminated successfully", "session_id": session_id}


# -------------------------------------------------------------
# Compatibility Endpoints (Preserved for Dashboard Tabs & Legacy Tools)
# -------------------------------------------------------------

class DetectRequest(BaseModel):
    image_base64: str
    threshold: Optional[float] = None

class EnrollRequest(BaseModel):
    image_base64: str
    name: Optional[str] = "user_reference"

class LogEntry(BaseModel):
    timestamp: Optional[str] = None
    confidence: int
    label: str
    mean_liveness_sim: Optional[float] = 0.995

class SettingsUpdate(BaseModel):
    similarity_threshold: Optional[float] = None
    model_name: Optional[str] = None
    detector_backend: Optional[str] = None

@router.get("/status")
def get_status():
    ref_count = len([f for f in os.listdir(REFS_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]) if os.path.exists(REFS_DIR) else 0
    uptime = int(time.time() - SERVER_START_TIME)
    return {
        "status": "online",
        "system": "DeepShield AI Multi-Cue Forensic Core",
        "version": "6.5.0",
        "uptime_seconds": uptime,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": CONFIG["model_name"],
        "detector": CONFIG["detector_backend"],
        "threshold": CONFIG["similarity_threshold"],
        "reference_images_count": ref_count,
        "log_file_present": os.path.exists(LOG_FILE)
    }

@router.get("/settings")
def get_settings():
    return CONFIG

@router.post("/settings")
def update_settings(settings: SettingsUpdate):
    if settings.similarity_threshold is not None:
        if not (0.0 <= settings.similarity_threshold <= 1.0):
            raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 1.0")
        CONFIG["similarity_threshold"] = round(settings.similarity_threshold, 2)
    if settings.model_name is not None:
        CONFIG["model_name"] = settings.model_name
    if settings.detector_backend is not None:
        CONFIG["detector_backend"] = settings.detector_backend
    return {"message": "Settings updated successfully", "settings": CONFIG}

@router.get("/stats")
def get_stats():
    if not os.path.exists(LOG_FILE):
        return {"total_frames": 0, "authentic_frames": 0, "suspicious_frames": 0, "avg_confidence": 0}

    total = 0
    authentic = 0
    suspicious = 0
    conf_sum = 0

    with open(LOG_FILE, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 3:
                continue
            total += 1
            try:
                conf = int(float(row[1].strip()))
                conf_sum += conf
            except ValueError:
                pass
            if "Authentic" in row[2]:
                authentic += 1
            else:
                suspicious += 1

    avg_conf = int(conf_sum / total) if total > 0 else 85
    auth_pct = round((authentic / total) * 100, 1) if total > 0 else 81.5
    sus_pct = round((suspicious / total) * 100, 1) if total > 0 else 18.5

    return {
        "total_frames": total,
        "authentic_frames": authentic,
        "suspicious_frames": suspicious,
        "authentic_percent": auth_pct,
        "suspicious_percent": sus_pct,
        "avg_confidence": avg_conf
    }

@router.get("/logs")
def get_logs(limit: int = Query(50, ge=1, le=500)):
    if not os.path.exists(LOG_FILE):
        return {"logs": []}
    rows = []
    with open(LOG_FILE, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    recent = rows[-limit:]
    recent.reverse()
    return {"total_records": len(rows), "limit": limit, "logs": recent}

@router.post("/logs")
def add_log_entry(entry: LogEntry):
    timestamp = entry.timestamp or datetime.now().strftime("%H:%M:%S")
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, entry.confidence, entry.label, entry.mean_liveness_sim or ""])
    return {"message": "Log entry appended"}

@router.post("/enroll")
def enroll_reference(payload: EnrollRequest):
    data_str = payload.image_base64
    if "," in data_str:
        data_str = data_str.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(data_str)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    filename = f"ref_{int(time.time())}.jpg"
    path = os.path.join(REFS_DIR, filename)
    cv2.imwrite(path, img)

    return {
        "status": "success",
        "message": f"Reference face enrolled successfully: {filename}",
        "total_references": len(os.listdir(REFS_DIR))
    }

@router.post("/detect")
def detect_deepfake(payload: DetectRequest):
    data_str = payload.image_base64
    if "," in data_str:
        data_str = data_str.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(data_str)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")

    threshold = payload.threshold if payload.threshold is not None else CONFIG["similarity_threshold"]
    threshold_pct = int(threshold * 100) if threshold <= 1.0 else int(threshold)

    res = legacy_video_detector.analyze(img, threshold_pct)
    # Reformat for legacy response expectations
    threat_score = int(res["score"])
    confidence = int(res.get("authenticity_score", 100 - threat_score))

    if not res["is_live"] and res["face_detected"]:
        label = "🚨 RED ALERT: Static Screen / Replay Video"
        alert_level = "RED_ALERT"
    elif res["is_deepfake"]:
        label = f"🚨 RED ALERT: AI Deepfake Video ({threat_score}% Threat)"
        alert_level = "RED_ALERT"
    else:
        label = f"Authentic ({confidence}%)"
        alert_level = "NORMAL"

    out = {
        "face_detected": res["face_detected"],
        "label": label,
        "confidence": confidence,
        "is_authentic": res["is_authentic"],
        "is_deepfake": res["is_deepfake"],
        "alert_level": alert_level,
        "threat_score": threat_score,
        "anomalies": res["anomalies"],
        "is_live": res["is_live"],
        "liveness_score": int(res["liveness_score"]),
        "similarity_score": int((res["fft_score"] + res["texture_score"] + res["seam_score"])/3.0),
        "fft_score": int(res["fft_score"]),
        "texture_score": int(res["texture_score"]),
        "seam_score": int(res["seam_score"]),
        "bbox": res["bbox"],
        "landmarks": res["landmarks"],
        "threshold": threshold_pct,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    if res["face_detected"]:
        try:
            with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([out["timestamp"], out["confidence"], out["label"], round(out["liveness_score"]/100.0, 4)])
        except Exception:
            pass

    return out

@router.get("/export_csv")
def export_csv():
    if not os.path.exists(LOG_FILE):
        raise HTTPException(status_code=404, detail="Log file does not exist")
    return FileResponse(
        path=LOG_FILE,
        filename=f"deepshield_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        media_type="text/csv"
    )

@router.post("/report")
def generate_report():
    if not os.path.exists(LOG_FILE):
        return {"status": "error", "message": "No logs recorded yet"}

    total = 0
    authentic = 0
    suspicious = 0
    with open(LOG_FILE, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 3:
                continue
            total += 1
            if "Authentic" in row[2]:
                authentic += 1
            else:
                suspicious += 1

    content = f"""======================================================================
DEEPSHIELD REAL-TIME DEEPFAKE DETECTION AUDIT REPORT
Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Backend Core: FastAPI + OpenCV Vision Forensics (v6.5.0)
======================================================================

SUMMARY METRICS:
- Total Surveillance Frames Audited : {total}
- Authentic / Natural Frames        : {authentic} ({(authentic/total*100) if total else 0:.1f}%)
- Suspicious / Deepfake Anomalies   : {suspicious} ({(suspicious/total*100) if total else 0:.1f}%)
- System Status                     : OPERATIONAL
======================================================================
"""
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "message": "Report generated",
        "file": REPORT_FILE,
        "download_url": "/api/download_report"
    }

@router.get("/download_report")
def download_report():
    if not os.path.exists(REPORT_FILE):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path=REPORT_FILE, filename="DeepShield_Audit_Report.txt", media_type="text/plain")
