# StreamRip Independent — HTML/CSS/JS + Flask + yt-dlp + FFmpeg

A newly written, independent interface inspired by the **general** analyze → convert → status → file workflow observed in publicly delivered YT1D frontend assets. No YT1D source files, images, logos, or proprietary code are included.

## Features
- HTTPS YouTube URL analysis with available source heights
- MP4 video/audio selection and MP3 extraction
- Flask JSON API; background jobs and polling; FFmpeg merge via yt-dlp
- Server-side bytes/speed/ETA when yt-dlp reports them; distinct postprocessing stage
- Final file download with HTTP range support via Flask `send_file(conditional=True)`
- Mobile-first interface; automatic browser download attempt with manual fallback

## Local setup
Python 3.11+ and FFmpeg/FFprobe must be installed and available on PATH.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

On Windows use `.venv\\Scripts\\activate` instead of `source`.

## Render deployment (Android mobile / GitHub)
1. Unzip the project. Upload the **contents** of `StreamRip_Independent/` into a new GitHub repository root (not just the outer ZIP).
2. Render → New → Blueprint → connect your GitHub repository → approve `render.yaml`.
3. Render builds Dockerfile with FFmpeg and runs `waitress-serve` on the Render-provided `PORT`.
4. Visit `/api/health` to confirm `ffmpeg: true`, then test a video you are permitted to download.

Alternative: New Web Service → Docker runtime → repo root → use Dockerfile. `render.yaml` is optional for this route.

## API
- `GET /api/health`
- `POST /api/analyze` JSON `{"url":"https://www.youtube.com/watch?v=..."}`
- `POST /api/jobs` JSON `{"url":"...","quality":"720","mode":"mp4"}` (or `"mode":"mp3"`)
- `GET /api/jobs/<id>` (status)
- `GET /api/files/<id>` (download after complete)

## Limitations / important deployment notes
- **No guarantee** YouTube downloads work from Render/cloud datacenter IPs. YouTube may require sign-in, throttle, return 403, or disallow a video. Do not attempt to circumvent access controls.
- Free Render has limited CPU, RAM, ephemeral disk, sleeps on inactivity, and may restart; jobs and files disappear on restart. This prototype uses in-memory jobs and temporary local storage. Multiple replicas do not share state. For production use Redis/Celery/RQ + object storage, durable database, rate limits, auth, storage quotas and cleanup scheduler.
- Server retrieval progress is **not** browser-to-phone download progress. Unknown total bytes show `—` instead of a fabricated percentage. Postprocessing progress is a stage estimate, not FFmpeg frame-level progress.
- Final MP4 can have a different size than estimated streams. Final size is shown only after processing.
- `max_filesize` is a best-effort yt-dlp limit; the final file is also checked. Default 350 MB and 30 minutes; configure via env vars.
- The project does not implement cookies or user authentication; do not upload private cookies to a public server.
- Only use with media you own or have permission to download and follow applicable platform terms and law.
