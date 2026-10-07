import asyncio
import time
import uuid
import base64
import logging
from typing import Dict, Optional, Any

import cv2
import numpy as np
from fastapi import WebSocket

try:
    from services.video_detector import VideoDeepfakeDetector
    from services.audio_detector import AudioDeepfakeDetector
    from services.lipsync_detector import LipSyncDetector
    from services.scam_detector import ScamContextDetector
    from services.risk_fusion import RiskFusionEngine
    from config import MAX_QUEUE_SIZE, DEFAULT_SENSITIVITY_THRESHOLD, REFS_DIR
except (ImportError, ValueError):
    from Backend.services.video_detector import VideoDeepfakeDetector
    from Backend.services.audio_detector import AudioDeepfakeDetector
    from Backend.services.lipsync_detector import LipSyncDetector
    from Backend.services.scam_detector import ScamContextDetector
    from Backend.services.risk_fusion import RiskFusionEngine
    from Backend.config import MAX_QUEUE_SIZE, DEFAULT_SENSITIVITY_THRESHOLD, REFS_DIR


logger = logging.getLogger("DeepShield.StreamManager")

class SurveillanceSession:
    def __init__(self, session_id: str, sensitivity_threshold: float = DEFAULT_SENSITIVITY_THRESHOLD):
        self.session_id = session_id
        self.created_at = time.time()
        self.sensitivity_threshold = sensitivity_threshold
        self.last_heartbeat = time.time()
        self.websocket: Optional[WebSocket] = None
        self.is_active = True

        # Session-isolated forensic detector instances
        self.video_detector = VideoDeepfakeDetector(refs_dir=REFS_DIR)
        self.audio_detector = AudioDeepfakeDetector()
        self.lipsync_detector = LipSyncDetector()
        self.scam_detector = ScamContextDetector()
        self.risk_fusion = RiskFusionEngine()

        # Cache latest sub-detector states
        self.latest_audio_res: Dict[str, Any] = {
            "score": 0.0,
            "label": "Audio Idle",
            "is_mock": self.audio_detector.is_mock
        }
        self.latest_lipsync_res: Dict[str, Any] = {
            "score": 0.0,
            "is_mock": True
        }
        self.latest_scam_res: Dict[str, Any] = {
            "score": 0.0,
            "is_mock": True,
            "keywords_detected": []
        }

        # Bounded frame queue (drops stale frames to prevent backlog)
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self.worker_task: Optional[asyncio.Task] = None
        self.last_frame_time: float = 0.0

    def start_worker(self):
        if self.worker_task is None or self.worker_task.done():
            try:
                loop = asyncio.get_running_loop()
                self.worker_task = loop.create_task(self._process_stream_loop())
            except RuntimeError:
                pass


    async def enqueue_frame(self, frame_bgr: np.ndarray, client_timestamp: float):
        """
        Enqueues video frame into bounded queue. If queue is full,
        drops older stale frames immediately in favor of newest live frame.
        """
        self.last_frame_time = time.time()
        while self.frame_queue.full():
            try:
                # Drop stale frame
                self.frame_queue.get_nowait()
                self.frame_queue.task_done()
                logger.debug(f"[{self.session_id}] Stale frame dropped to maintain real-time latency.")
            except asyncio.QueueEmpty:
                break

        try:
            self.frame_queue.put_nowait((frame_bgr, client_timestamp, time.time()))
        except asyncio.QueueFull:
            pass

    async def update_audio_chunk(self, audio_bytes: bytes):
        """
        Analyzes incoming audio chunk (from MediaRecorder ~2s slices) in threadpool.
        """
        try:
            res = await asyncio.to_thread(self.audio_detector.analyze, audio_bytes)
            self.latest_audio_res = res
        except Exception as e:
            logger.error(f"[{self.session_id}] Audio analysis error: {e}")
            self.latest_audio_res = {
                "score": 0.0,
                "label": "Audio Analysis Error",
                "is_mock": self.audio_detector.is_mock,
                "error": str(e)
            }

        # If no active video frames have been received recently (mic-only surveillance mode),
        # push audio analysis directly to ensure live telemetry reaches the client
        time_since_video = time.time() - getattr(self, "last_frame_time", 0.0)
        if self.websocket is not None and time_since_video > 3.0:
            try:
                dummy_video = {
                    "face_detected": False,
                    "score": 0.0,
                    "label": "Microphone Surveillance Mode",
                    "is_authentic": True,
                    "is_deepfake": False,
                    "is_live": True,
                    "is_mock": False,
                    "anomalies": []
                }
                fused = self.risk_fusion.fuse(
                    video_res=dummy_video,
                    audio_res=self.latest_audio_res,
                    lipsync_res=self.latest_lipsync_res,
                    scam_res=self.latest_scam_res,
                    sensitivity_threshold=self.sensitivity_threshold
                )
                payload = {
                    "type": "analysis",
                    "session_id": self.session_id,
                    "timestamp": time.time(),
                    "audio": {
                        "score": float(self.latest_audio_res.get("score", 0.0)),
                        "label": self.latest_audio_res.get("label", "Audio Active"),
                        "is_mock": bool(self.latest_audio_res.get("is_mock", True))
                    },
                    "video": dummy_video,
                    "lip_sync": self.latest_lipsync_res,
                    "scam_context": self.latest_scam_res,
                    "fused": fused,
                    "latency_ms": 8.0
                }
                await self.websocket.send_json(payload)
            except Exception as send_err:
                logger.warning(f"[{self.session_id}] Audio-direct WebSocket push error: {send_err}")

    async def _process_stream_loop(self):
        """
        Continuous background worker processing video frames off the bounded queue.
        Runs CPU inference in a separate threadpool to never block FastAPI's async event loop.
        """
        logger.info(f"[{self.session_id}] Live analysis worker started.")
        while self.is_active:
            try:
                frame_bgr, client_ts, enqueued_ts = await self.frame_queue.get()
                t0 = time.perf_counter()

                # Run blocking video forensic inference in threadpool
                try:
                    video_res = await asyncio.to_thread(
                        self.video_detector.analyze,
                        frame_bgr,
                        self.sensitivity_threshold
                    )
                except Exception as e:
                    logger.error(f"[{self.session_id}] Video inference error: {e}", exc_info=True)
                    video_res = {
                        "face_detected": False,
                        "label": "Video Detector Error",
                        "score": 0.0,
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
                        "anomalies": ["Video processing exception isolated"]
                    }

                # Evaluate Lip Sync
                try:
                    lipsync_res = await asyncio.to_thread(
                        self.lipsync_detector.analyze,
                        video_res.get("landmarks"),
                        float(self.latest_audio_res.get("details", {}).get("signal_energy", 0.0))
                    )
                    self.latest_lipsync_res = lipsync_res
                except Exception as e:
                    lipsync_res = {"score": 0.0, "is_mock": True, "error": str(e)}

                # Run Risk Fusion
                try:
                    fused = self.risk_fusion.fuse(
                        video_res=video_res,
                        audio_res=self.latest_audio_res,
                        lipsync_res=self.latest_lipsync_res,
                        scam_res=self.latest_scam_res,
                        sensitivity_threshold=self.sensitivity_threshold
                    )
                except Exception as e:
                    logger.error(f"[{self.session_id}] Risk fusion error: {e}")
                    fused = {
                        "score": float(video_res.get("score", 0.0)),
                        "level": "LOW",
                        "label": "Fusion Error Fallback",
                        "reasons": [f"Fusion error: {str(e)}"]
                    }

                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

                # Build standardized target payload
                payload = {
                    "type": "analysis",
                    "session_id": self.session_id,
                    "timestamp": time.time(),
                    "audio": {
                        "score": float(self.latest_audio_res.get("score", 0.0)),
                        "label": self.latest_audio_res.get("label", "Audio Idle"),
                        "is_mock": bool(self.latest_audio_res.get("is_mock", True))
                    },
                    "video": {
                        "score": float(video_res.get("score", 0.0)),
                        "label": video_res.get("label", "Unknown"),
                        "is_mock": False,
                        "face_detected": video_res.get("face_detected", False),
                        "fft_score": video_res.get("fft_score", 0.0),
                        "texture_score": video_res.get("texture_score", 0.0),
                        "seam_score": video_res.get("seam_score", 0.0),
                        "liveness_score": video_res.get("liveness_score", 0.0),
                        "bbox": video_res.get("bbox"),
                        "landmarks": video_res.get("landmarks")
                    },
                    "lip_sync": {
                        "score": float(self.latest_lipsync_res.get("score", 0.0)),
                        "is_mock": True
                    },
                    "scam_context": {
                        "score": float(self.latest_scam_res.get("score", 0.0)),
                        "is_mock": True
                    },
                    "fused": fused,
                    "latency_ms": latency_ms
                }

                # Push result to connected WebSocket
                if self.websocket is not None:
                    try:
                        await self.websocket.send_json(payload)
                    except Exception as ws_err:
                        logger.warning(f"[{self.session_id}] WebSocket send failed: {ws_err}")

                self.frame_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as loop_err:
                logger.error(f"[{self.session_id}] Worker loop error: {loop_err}", exc_info=True)
                await asyncio.sleep(0.05)

    async def close(self):
        self.is_active = False
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        if self.websocket:
            try:
                await self.websocket.close(code=1000, reason="Session terminated")
            except Exception:
                pass
            self.websocket = None
        logger.info(f"[{self.session_id}] Surveillance session closed cleanly.")


class StreamManager:
    """
    Registry and lifecycle controller for live surveillance sessions.
    """
    def __init__(self):
        self.sessions: Dict[str, SurveillanceSession] = {}

    def create_session(self, sensitivity_threshold: float = DEFAULT_SENSITIVITY_THRESHOLD) -> SurveillanceSession:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = SurveillanceSession(session_id=session_id, sensitivity_threshold=sensitivity_threshold)
        session.start_worker()
        self.sessions[session_id] = session
        logger.info(f"Created surveillance session: {session_id} (active: {len(self.sessions)})")
        return session

    def get_session(self, session_id: str) -> Optional[SurveillanceSession]:
        return self.sessions.get(session_id)

    async def remove_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
            logger.info(f"Removed surveillance session: {session_id} (remaining: {len(self.sessions)})")
            return True
        return False

# Global Singleton Stream Manager
stream_manager = StreamManager()
