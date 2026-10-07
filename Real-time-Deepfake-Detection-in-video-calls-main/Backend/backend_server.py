"""
DeepShield — Real-Time Deepfake Detection System
FastAPI Backend Application Entry Point
Modular Architecture: Routers, Services, Forensics, and Live Stream Manager
"""

import os
import sys
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure Backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import (
    HOST, PORT, CORS_ORIGINS, FRONTEND_DIR, REFS_DIR, LOG_FILE
)
from routers.sessions import router as sessions_router
from routers.live_ws import router as live_ws_router

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("DeepShield.App")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    os.makedirs(REFS_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
            f.write("Time,Confidence (%),Label,Mean Liveness Sim\n")
    logger.info("==================================================")
    logger.info("🛡️ DeepShield AI Forensic Backend Server Initialized")
    logger.info(f"📡 Host: {HOST} | Port: {PORT}")
    logger.info(f"🌐 Allowed CORS Origins: {CORS_ORIGINS}")
    logger.info("==================================================")
    yield
    # Teardown logic
    logger.info("DeepShield Backend Server shutting down.")

# Initialize FastAPI Application
app = FastAPI(
    title="DeepShield AI Forensic Core",
    description="Real-Time Deepfake Detection & Social Engineering Risk Engine",
    version="6.5.0",
    lifespan=lifespan
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_origin_regex=r"^https?://.*|^file://.*|^null$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(sessions_router, prefix="/api", tags=["Sessions & Analytics"])
app.include_router(live_ws_router, tags=["Live Streaming WebSocket"])

# Serve Frontend Static Assets
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "DeepShield AI Core Online. Frontend index.html not found."}

    # Serve direct files from Frontend (e.g. style.css, script.js, config.js, etc.)
    @app.get("/{filename:path}")
    def serve_frontend_files(filename: str):
        file_path = os.path.join(FRONTEND_DIR, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Resource not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_server:app", host=HOST, port=PORT, reload=False)
