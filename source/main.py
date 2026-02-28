"""
main.py - FastAPI backend for Cuber's AI Coach
"""

import os
import uuid
import shutil
import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from analyzer import analyze_video

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/cubers_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

INTENSITY_THRESHOLD = float(os.environ.get("INTENSITY_THRESHOLD", "2.0"))
MIN_PAUSE_DURATION = float(os.environ.get("MIN_PAUSE_DURATION", "0.5"))

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "video/mpeg",
    "application/octet-stream",  # Some clients send this for video
}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cuber's AI Coach API",
    description="Analyzes Rubik's Cube solve videos for Recognition Pauses using Optical Flow.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cleanup_file(path: Path) -> None:
    """Delete temp file after response is sent."""
    try:
        path.unlink(missing_ok=True)
        logger.info(f"Cleaned up temp file: {path}")
    except Exception as e:
        logger.warning(f"Could not delete temp file {path}: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Cuber's AI Coach API"}


@app.post("/analyze")
async def analyze_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a video upload, run optical-flow analysis, return metrics as JSON.
    """
    # ── Validate content type ──────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES and not content_type.startswith("video/"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: '{content_type}'. Please upload a video file (MP4, MOV, AVI, WebM).",
        )

    # ── Save to temp file (stream in chunks to avoid memory blow-up) ───────
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        total_bytes = 0
        with tmp_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    f.close()
                    tmp_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_MB} MB.",
                    )
                f.write(chunk)

        logger.info(
            f"Saved upload: {tmp_path.name}  ({total_bytes / 1024 / 1024:.1f} MB)"
        )
    except HTTPException:
        raise
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    # ── Run CV analysis ────────────────────────────────────────────────────
    try:
        result = analyze_video(
            str(tmp_path),
            intensity_threshold=INTENSITY_THRESHOLD,
            min_pause_duration=MIN_PAUSE_DURATION,
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        background_tasks.add_task(_cleanup_file, tmp_path)
        raise HTTPException(
            status_code=422,
            detail=f"Video analysis failed: {str(e)}. Make sure the file is a valid, non-corrupted video.",
        )

    # ── Schedule cleanup ───────────────────────────────────────────────────
    background_tasks.add_task(_cleanup_file, tmp_path)

    return JSONResponse(content=result.to_dict())


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
        workers=1,  # OpenCV is not fork-safe; use 1 worker
    )
