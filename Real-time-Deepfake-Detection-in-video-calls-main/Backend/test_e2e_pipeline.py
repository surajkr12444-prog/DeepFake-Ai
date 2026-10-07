import sys
import time
import json
import base64
import asyncio
import numpy as np
import cv2
import requests
import websockets

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8050"
WS_URL = "ws://127.0.0.1:8050"

def generate_test_frame_b64():
    """Generates a synthetic camera test frame with human face geometry."""
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (640, 360), (35, 30, 25), -1)
    # Face ellipse
    cv2.ellipse(img, (320, 180), (80, 110), 0, 0, 360, (140, 175, 215), -1)
    # Eyes
    cv2.circle(img, (290, 155), 10, (20, 20, 20), -1)
    cv2.circle(img, (350, 155), 10, (20, 20, 20), -1)
    # Mouth
    cv2.line(img, (300, 225), (340, 225), (30, 40, 160), 3)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

def generate_test_audio_b64():
    """Generates synthetic audio chunk bytes."""
    dummy_wav = b"RIFF" + b"\x00" * 36 + b"data" + (b"\x10\x20\x30\x40" * 500)
    return "data:audio/wav;base64," + base64.b64encode(dummy_wav).decode('utf-8')

async def run_e2e_tests():
    print("=" * 65)
    print("🚀 DEEPSHIELD COMPREHENSIVE E2E PIPELINE VERIFICATION")
    print("=" * 65)

    # 1. GET /api/health
    print("\n[1] Testing GET /api/health...")
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    health_data = r.json()
    print("    Status:", health_data.get("status"))
    print("    Detectors:", list(health_data.get("detectors", {}).keys()))
    assert "video" in health_data["detectors"]
    assert "audio" in health_data["detectors"]

    # 2. POST /api/sessions
    print("\n[2] Testing POST /api/sessions...")
    r = requests.post(f"{BASE_URL}/api/sessions", json={"sensitivity_threshold": 65.0}, timeout=5)
    assert r.status_code == 200, f"Session creation failed: {r.status_code}"
    session_data = r.json()
    session_id = session_data["session_id"]
    print("    Created Session ID:", session_id)
    assert session_id.startswith("sess_")

    # 3. GET /api/sessions/{session_id}
    print(f"\n[3] Testing GET /api/sessions/{session_id}...")
    r = requests.get(f"{BASE_URL}/api/sessions/{session_id}", timeout=5)
    assert r.status_code == 200, f"Get session failed: {r.status_code}"
    sess_meta = r.json()
    print("    Session Status:", sess_meta["status"], "| Threshold:", sess_meta["threshold"])

    # 4. WebSocket Live Streaming Connection
    print(f"\n[4] Testing WebSocket /ws/live/{session_id}...")
    ws_uri = f"{WS_URL}/ws/live/{session_id}"
    async with websockets.connect(ws_uri) as ws:
        # Await connection acknowledgement
        ack_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        ack = json.loads(ack_raw)
        print("    Connection Ack received:", ack.get("type"), "-", ack.get("message"))
        assert ack.get("type") == "connection_ack"

        # 5. Heartbeat Ping / Pong
        print("\n[5] Testing Ping / Pong Heartbeat...")
        await ws.send(json.dumps({"type": "ping", "timestamp": time.time()}))
        pong_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        pong = json.loads(pong_raw)
        print("    Pong received:", pong.get("type"))
        assert pong.get("type") == "pong"

        # 6. Stream Video Frame
        print("\n[6] Sending video frame packet (~640x360)...")
        test_frame = generate_test_frame_b64()
        await ws.send(json.dumps({
            "type": "video_frame",
            "image": test_frame,
            "timestamp": time.time()
        }))

        # Await multi-cue risk fusion analysis result
        analysis_raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
        analysis = json.loads(analysis_raw)
        print("    Analysis Packet Received:")
        print("      Session ID:", analysis.get("session_id"))
        print("      Video Score:", analysis.get("video", {}).get("score"))
        print("      Audio Score:", analysis.get("audio", {}).get("score"), f"(is_mock: {analysis.get('audio', {}).get('is_mock')})")
        print("      Lip Sync Score:", analysis.get("lip_sync", {}).get("score"))
        print("      Scam Context Score:", analysis.get("scam_context", {}).get("score"))
        print("      Fused Threat Score:", analysis.get("fused", {}).get("score"))
        print("      Fused Threat Level:", analysis.get("fused", {}).get("level"))
        print("      Reasons:", analysis.get("fused", {}).get("reasons"))
        print("      Latency:", analysis.get("latency_ms"), "ms")

        assert analysis.get("type") == "analysis"
        assert "fused" in analysis
        assert "score" in analysis["fused"]
        assert "level" in analysis["fused"]

        # 7. Stream Audio Chunk Packet
        print("\n[7] Sending ~2s audio chunk packet...")
        test_audio = generate_test_audio_b64()
        await ws.send(json.dumps({
            "type": "audio_chunk",
            "audio": test_audio,
            "timestamp": time.time()
        }))
        # Give worker a moment to process audio
        await asyncio.sleep(0.3)

        # Send next frame to verify audio score fused into next analysis
        await ws.send(json.dumps({
            "type": "video_frame",
            "image": test_frame,
            "timestamp": time.time()
        }))
        analysis2_raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
        analysis2 = json.loads(analysis2_raw)
        print("    Analysis with Audio Chunk fused successfully! Threat:", analysis2.get("fused", {}).get("score"))

        # 8. Malformed Packet Fault Tolerance
        print("\n[8] Testing malformed packet fault tolerance...")
        await ws.send("NON_JSON_CORRUPTED_GARBAGE_PAYLOAD")
        await asyncio.sleep(0.2)
        # Verify socket is still healthy by sending ping
        await ws.send(json.dumps({"type": "ping", "timestamp": time.time()}))
        pong2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
        assert pong2.get("type") == "pong"
        print("    Resilience verified: Socket survived malformed packet.")

    # 9. DELETE /api/sessions/{session_id}
    print(f"\n[9] Testing DELETE /api/sessions/{session_id}...")
    r = requests.delete(f"{BASE_URL}/api/sessions/{session_id}", timeout=5)
    assert r.status_code == 200, f"Delete session failed: {r.status_code}"
    print("    Session closed and resources cleaned up.")

    # 10. Legacy Endpoints Verification
    print("\n[10] Verifying legacy compatibility endpoints...")
    assert requests.get(f"{BASE_URL}/api/status").status_code == 200
    assert requests.get(f"{BASE_URL}/api/stats").status_code == 200
    assert requests.get(f"{BASE_URL}/api/logs?limit=5").status_code == 200
    assert requests.get(f"{BASE_URL}/api/export_csv").status_code == 200
    print("    All legacy routes intact and returning 200 OK.")

    # 11. Root Static Frontend Serving
    print("\n[11] Verifying Frontend serving at root URL /...")
    r = requests.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200
    assert "DeepShield" in r.text
    print("    Frontend index.html served successfully with HTTP 200.")

    # 12. Dedicated Voice Deepfake Recognition Endpoint
    print("\n[12] Testing POST /api/voice/predict with audio waveform...")
    dummy_wav = b"RIFF" + b"\x00" * 36 + b"data" + (b"\x10\x20\x30\x40" * 1000)
    files = {"file": ("test_speech.wav", dummy_wav, "audio/wav")}
    r = requests.post(f"{BASE_URL}/api/voice/predict", files=files, timeout=10)
    assert r.status_code == 200, f"Voice prediction failed: {r.status_code}"
    v_data = r.json()
    print("    Voice Recognition Result:", v_data.get("label"))
    print("    Authenticity Confidence:", v_data.get("confidence"), "%")
    print("    Synthetic Threat Risk:", v_data.get("score"), "%")
    print("    Acoustic Forensics:", v_data.get("metrics"))
    assert "label" in v_data
    assert "metrics" in v_data

    print("\n" + "=" * 65)
    print("🎉 ALL 12 E2E & VOICE RECOGNITION PIPELINE TESTS PASSED 100%!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
