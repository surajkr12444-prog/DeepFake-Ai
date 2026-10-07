import time
import base64
import json
import logging
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

try:
    from services.stream_manager import stream_manager
except (ImportError, ValueError):
    from Backend.services.stream_manager import stream_manager


logger = logging.getLogger("DeepShield.LiveWS")
router = APIRouter()

@router.websocket("/ws/live/{session_id}")
async def live_surveillance_websocket(websocket: WebSocket, session_id: str):
    """
    Authoritative Live Surveillance WebSocket endpoint.
    Handles continuous bidirectional streaming:
    - Receives live video frames (~640x360 at ~1-2 FPS)
    - Receives audio chunks (MediaRecorder ~2s slices)
    - Handles heartbeat ping/pong
    - Streams multi-cue risk fusion assessments back to client
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for session: {session_id}")

    session = stream_manager.get_session(session_id)
    if not session:
        # Create session on-the-fly if client connects directly
        session = stream_manager.create_session()
        logger.info(f"Auto-created session for incoming WebSocket: {session.session_id}")

    session.websocket = websocket
    session.last_heartbeat = time.time()
    session.start_worker()


    # Initial handshake acknowledgement
    await websocket.send_json({
        "type": "connection_ack",
        "session_id": session.session_id,
        "status": "connected",
        "timestamp": time.time(),
        "message": "DeepShield AI Forensic Core stream active"
    })

    try:
        while True:
            # Receive either text (JSON) or binary data
            message = await websocket.receive()

            if "text" in message and message["text"] is not None:
                text_data = message["text"]
                try:
                    data = json.loads(text_data)
                except Exception:
                    continue

                msg_type = data.get("type")
                session.last_heartbeat = time.time()

                if msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                        "client_timestamp": data.get("timestamp")
                    })

                elif msg_type == "video_frame":
                    b64_img = data.get("image")
                    if b64_img:
                        if "," in b64_img:
                            b64_img = b64_img.split(",", 1)[1]
                        try:
                            img_bytes = base64.b64decode(b64_img)
                            nparr = np.frombuffer(img_bytes, np.uint8)
                            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            if frame_bgr is not None:
                                await session.enqueue_frame(frame_bgr, data.get("timestamp", time.time()))
                        except Exception as decode_err:
                            logger.warning(f"[{session_id}] Video decode error: {decode_err}")

                elif msg_type == "audio_chunk":
                    b64_audio = data.get("audio")
                    if b64_audio:
                        if "," in b64_audio:
                            b64_audio = b64_audio.split(",", 1)[1]
                        try:
                            audio_bytes = base64.b64decode(b64_audio)
                            await session.update_audio_chunk(audio_bytes)
                        except Exception as audio_err:
                            logger.warning(f"[{session_id}] Audio chunk decode error: {audio_err}")

                elif msg_type == "stop":
                    logger.info(f"[{session_id}] Client sent stop command via WebSocket.")
                    break

            elif "bytes" in message and message["bytes"] is not None:
                # Raw binary bytes (audio chunk or video frame)
                raw_bytes = message["bytes"]
                session.last_heartbeat = time.time()
                # If bytes start with RIFF or OggS or matroska webm, it's audio
                if raw_bytes.startswith(b"RIFF") or raw_bytes.startswith(b"OggS") or raw_bytes.startswith(b"\x1aE\xdf\xa3"):
                    await session.update_audio_chunk(raw_bytes)
                else:
                    # Try image decode
                    try:
                        nparr = np.frombuffer(raw_bytes, np.uint8)
                        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame_bgr is not None:
                            await session.enqueue_frame(frame_bgr, time.time())
                    except Exception:
                        pass

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocket client disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket session error for {session_id}: {e}", exc_info=True)

    finally:
        session.websocket = None
        logger.info(f"Cleaned up WebSocket for session: {session_id}")
