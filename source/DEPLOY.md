# 🚀 Deployment Guide — Cuber's AI Coach

## Architecture Overview

```
┌─────────────────────────────────────────┐
│  Browser (student)                      │
│      ↓  upload video (HTTP)             │
│  Streamlit  (port 8501)                 │
│      ↓  POST /analyze                   │
│  FastAPI    (port 8000)                 │
│      ↓  OpenCV Optical Flow             │
│  JSON result → UI renders charts        │
└─────────────────────────────────────────┘
```

---

## Option A: Local Development (Fastest)

### Prerequisites
- Python 3.11+
- `pip`

### Steps

```bash
# 1. Clone / unzip the project
cd cubers-ai-coach

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the FastAPI backend (terminal 1)
python main.py
# → API running at http://localhost:8000
# → Docs at  http://localhost:8000/docs

# 5. Start the Streamlit frontend (terminal 2)
streamlit run app.py \
  --server.port 8501 \
  --server.maxUploadSize 200 \
  --theme.base dark \
  --theme.primaryColor "#818cf8" \
  --theme.backgroundColor "#0d0d1a" \
  --theme.secondaryBackgroundColor "#111827" \
  --theme.textColor "#e5e7eb"
# → UI at http://localhost:8501
```

---

## Option B: Docker (Single Container)

```bash
# Build
docker build -t cubers-ai-coach .

# Run (both API + UI in one container via supervisord)
docker run -p 8000:8000 -p 8501:8501 \
  -e MAX_UPLOAD_MB=200 \
  cubers-ai-coach

# Open http://localhost:8501
```

### Large video uploads with Docker
The container writes temp files to `/tmp/cubers_uploads` inside the container.
For very large files (>500 MB), mount a volume:

```bash
docker run -p 8000:8000 -p 8501:8501 \
  -v /path/on/host/uploads:/tmp/cubers_uploads \
  cubers-ai-coach
```

---

## Option C: Render.com (Recommended for Production)

Render offers free/cheap hosting with Docker support and persistent logging.

### Step-by-step

1. **Push code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit — Cuber's AI Coach"
   git remote add origin https://github.com/YOUR_USERNAME/cubers-ai-coach
   git push -u origin main
   ```

2. **Deploy the API service**
   - Go to https://render.com → *New* → *Web Service*
   - Connect your GitHub repo
   - Settings:
     | Field | Value |
     |-------|-------|
     | **Name** | `cubers-ai-coach-api` |
     | **Runtime** | Docker |
     | **Docker Command** | `python main.py` |
     | **Plan** | Starter (or Standard for production) |
   - Add Environment Variables:
     ```
     PORT            = 8000
     UPLOAD_DIR      = /tmp/cubers_uploads
     MAX_UPLOAD_MB   = 200
     INTENSITY_THRESHOLD = 2.0
     MIN_PAUSE_DURATION  = 0.5
     ```
   - Click **Create Web Service**
   - Note the URL: `https://cubers-ai-coach-api.onrender.com`

3. **Deploy the Streamlit frontend**
   - *New* → *Web Service* → same repo
   - Settings:
     | Field | Value |
     |-------|-------|
     | **Name** | `cubers-ai-coach-ui` |
     | **Runtime** | Docker |
     | **Docker Command** | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.maxUploadSize 200 --browser.gatherUsageStats false` |
   - Add Environment Variables:
     ```
     API_URL        = https://cubers-ai-coach-api.onrender.com
     MAX_UPLOAD_MB  = 200
     ```
   - Click **Create Web Service**

4. **Test**
   - Visit `https://cubers-ai-coach-ui.onrender.com`
   - Upload a short test video — you should see the full dashboard!

### ⚠️ Render Free Tier Note
Free tier services sleep after 15 min of inactivity. Use the **Starter ($7/mo)** plan for always-on availability. For large videos (>100 MB) or long solves, upgrade the API service to **Standard** for better CPU.

---

## Option D: Railway.app

Railway is the fastest zero-config deployment option.

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project in repo root
railway init

# Deploy
railway up
```

Then in the Railway dashboard:
1. Add two services from the same repo (API + UI)
2. Set `Dockerfile` as the build method for both
3. Override the start command per service (same as Render above)
4. Set the `API_URL` env var on the UI service to the Railway domain of the API service

---

## Handling Large Video Uploads

| Concern | Solution |
|---------|----------|
| Video > 200 MB | Increase `MAX_UPLOAD_MB` env var; also update `--server.maxUploadSize` in Streamlit start command |
| Memory OOM during analysis | The analyzer downsamples frames to 320px wide. For very high-res videos (4K), lower `downsample_width` in `analyzer.py` |
| Timeout on slow servers | The Streamlit client has a 5-min timeout. For longer solves, increase `timeout=300` in `app.py` → `call_analyze_api()` |
| Disk space on free tier | `/tmp` is ephemeral. Files are deleted after each request via `BackgroundTasks`. |

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | FastAPI port |
| `UPLOAD_DIR` | `/tmp/cubers_uploads` | Temp storage for uploaded videos |
| `MAX_UPLOAD_MB` | `200` | Max video file size |
| `INTENSITY_THRESHOLD` | `2.0` | Optical flow magnitude below which a frame is "paused" |
| `MIN_PAUSE_DURATION` | `0.5` | Min consecutive pause time (seconds) to be reported |
| `API_URL` | `http://localhost:8000` | Streamlit → FastAPI base URL |

---

## Tuning the Pause Detection

Edit these in `.env` or as environment variables:

- **Lower `INTENSITY_THRESHOLD`** (e.g., `1.0`): Only catches complete stops — good for fast solvers
- **Raise `INTENSITY_THRESHOLD`** (e.g., `3.5`): Catches slow/hesitant moves too — good for beginners
- **Lower `MIN_PAUSE_DURATION`** (e.g., `0.2`): Catches even brief hesitations
- **Raise `MIN_PAUSE_DURATION`** (e.g., `1.0`): Only reports significant pauses

---

*SanRu Labs — Cuber's AI Coach v1.0*
