# ─────────────────────────────────────────────────────────────────────────────
#  Cuber's AI Coach — Production Dockerfile
#  Runs both FastAPI (port 8000) and Streamlit (port 8501) in one container
#  using supervisord.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System dependencies required by OpenCV ────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python deps (layer-cached until requirements change) ──────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY analyzer.py main.py app.py ./

# ── Supervisord config — manages both processes ───────────────────────────────
RUN mkdir -p /var/log/supervisor /tmp/cubers_uploads

COPY supervisord.conf /etc/supervisor/conf.d/cubers.conf

# ── Expose both ports ─────────────────────────────────────────────────────────
EXPOSE 8000 8501

# ── Environment defaults ──────────────────────────────────────────────────────
ENV UPLOAD_DIR=/tmp/cubers_uploads \
    MAX_UPLOAD_MB=200 \
    INTENSITY_THRESHOLD=2.0 \
    MIN_PAUSE_DURATION=0.5 \
    API_URL=http://localhost:8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Launch ────────────────────────────────────────────────────────────────────
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/cubers.conf"]
