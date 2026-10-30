# StreamRip Pro — Professional Full-Stack YouTube Media Processor (2026)

StreamRip Pro is a full-stack YouTube media analysis, video+audio stream merging, and audio extraction workstation built for authorized, user-owned, Creative Commons, and public-domain media.

## 1. Architecture & Stack

- **Frontend**: Responsive Mobile-First React 19 + TypeScript + Tailwind CSS (plus standalone HTML5/CSS3/JS reference in `/frontend`), featuring full **English & Hindi (हिन्दी)** bilingual localization.
- **Gateway**: Express + Vite middleware (`server.ts`) on port `3000` with streaming binary proxy to the Python 3 media engine.
- **Backend Media Engine**: Python 3 (`backend/app.py`, `backend/media_engine.py`, `backend/security.py`, `backend/diagnostics.py`) powered by:
  - `yt-dlp` (`./bin/yt-dlp` or system `yt-dlp`)
  - `FFmpeg` (`/usr/bin/ffmpeg`) for video+audio stream merging (`-c:v copy -c:a aac -movflags +faststart`) and audio encoding (`libmp3lame`, `aac`)
  - `FFprobe` (`/usr/bin/ffprobe`) for post-processing container & stream integrity verification

## 2. Project Folder Structure

```text
/
├── backend/
│   ├── __init__.py          # Backend package marker
│   ├── app.py               # Python 3 multi-threaded REST API server & QA suite runner
│   ├── diagnostics.py       # HTTP 400/403/404/408/429/500/502/503 & 6-way YT 403 classifier
│   ├── media_engine.py      # yt-dlp discovery, FFmpeg merge/extract, FFprobe validation
│   └── security.py          # URL allowlisting, SSRF guard, filename sanitizer, rate limiter
├── bin/
│   └── yt-dlp               # Standalone Linux yt-dlp binary
├── frontend/
│   ├── index.html           # Standalone HTML5 client
│   ├── styles.css           # Standalone CSS3 dark glassmorphic stylesheet
│   └── app.js               # Standalone JavaScript API client
├── src/
│   ├── App.tsx              # Full-featured bilingual React 19 workstation UI
│   ├── i18n.ts              # English & Hindi translations
│   ├── index.css            # Tailwind CSS & custom glassmorphism utilities
│   └── main.tsx             # React entry point
├── tests/
│   └── test_backend.py      # Automated unittest suite covering 12 QA scenarios
├── server.ts                # Node/Express full-stack gateway & Python process manager
├── requirements.txt         # Python dependencies
├── Dockerfile               # Multi-stage production container (Node 22 + Python 3.12 + FFmpeg)
├── .dockerignore            # Docker build exclusions
└── .env.example             # Environment variable template
```

## 3. Cloud Deployment Instructions

### A. Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/streamrip-pro
gcloud run deploy streamrip-pro \
  --image gcr.io/YOUR_PROJECT_ID/streamrip-pro \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300s \
  --port 3000
```

### B. Railway
1. Connect repository to Railway.
2. Railway automatically detects the `Dockerfile`.
3. Set environment variables: `PORT=3000`, `PYTHON_BACKEND_PORT=5001`.

### C. Render
1. Create a new **Web Service** on Render and select **Docker** runtime.
2. Configure Health Check Path to `/api/health`.
3. Note: Free Render instances spin down after inactivity and have ephemeral `/tmp` storage.

### D. Docker-Based VPS
```bash
docker build -t streamrip-pro:latest .
docker run -d --name streamrip-pro -p 3000:3000 --restart unless-stopped streamrip-pro:latest
```

## 4. Platform Limitations & Ethical Compliance
- StreamRip Pro strictly complies with platform rules: it **does not** implement DRM bypassing, CAPTCHA evasion, BotGuard bypassing, proxy rotation, or unauthorized cookie harvesting.
- Shared cloud datacenter IPs (Cloud Run, AWS, Render, Railway) are frequently challenged by YouTube (`HTTP 403 — Hosting Environment Restriction`). StreamRip Pro detects and classifies these restrictions transparently without faking availability.
