import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "6.5.0"
    timestamp: float = Field(default_factory=time.time)
    detectors: Dict[str, Any]

class SessionCreateRequest(BaseModel):
    client_name: Optional[str] = "DeepShield-Web"
    sensitivity_threshold: Optional[float] = 60.0

class SessionResponse(BaseModel):
    session_id: str
    created_at: float
    status: str
    active_connections: int

class AudioAnalysis(BaseModel):
    score: float  # 0.0 to 100.0 (synthetic voice risk score)
    label: str
    is_mock: bool = False
    details: Optional[Dict[str, Any]] = None

class VideoAnalysis(BaseModel):
    score: float  # 0.0 to 100.0 (visual deepfake risk score)
    label: str
    is_mock: bool = False
    face_detected: bool = True
    fft_score: float = 0.0
    texture_score: float = 0.0
    seam_score: float = 0.0
    liveness_score: float = 0.0
    bbox: Optional[List[int]] = None
    landmarks: Optional[List[List[int]]] = None

class LipSyncAnalysis(BaseModel):
    score: float  # 0.0 to 100.0 (audio-visual desync risk score)
    is_mock: bool = True
    details: Optional[Dict[str, Any]] = None

class ScamContextAnalysis(BaseModel):
    score: float  # 0.0 to 100.0 (social engineering risk score)
    is_mock: bool = True
    keywords_detected: Optional[List[str]] = None

class FusedRisk(BaseModel):
    score: float  # 0.0 to 100.0 overall threat score
    level: str    # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    label: str
    reasons: List[str]

class AnalysisResult(BaseModel):
    type: str = "analysis"
    session_id: str
    timestamp: float
    audio: AudioAnalysis
    video: VideoAnalysis
    lip_sync: LipSyncAnalysis
    scam_context: ScamContextAnalysis
    fused: FusedRisk
    latency_ms: float
