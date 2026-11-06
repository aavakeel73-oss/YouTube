"""StreamRip Independent: Flask + yt-dlp demo for authorized public media."""
import ipaddress
import os
import re
import shutil
import socket
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, render_template, request, send_file
import yt_dlp

app = Flask(__name__)
app.json.ensure_ascii = False
ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "storage"
STORAGE.mkdir(exist_ok=True)
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "350"))
MAX_DURATION = int(os.environ.get("MAX_DURATION_SECONDS", "1800"))
TTL = int(os.environ.get("JOB_TTL_SECONDS", "1800"))
MAX_JOBS = int(os.environ.get("MAX_ACTIVE_JOBS", "2"))
LOCK = threading.RLock()
JOBS = {}


def valid_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("मान्य YouTube लिंक डालें।")
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}
    if parsed.scheme != "https" or host not in allowed or parsed.username or parsed.password or parsed.port:
        raise ValueError("केवल HTTPS YouTube लिंक स्वीकार किए जाते हैं।")
    # Disallow ambiguous alternate host resolution and private IP destinations.
    try:
        for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            addr = ipaddress.ip_address(item[4][0])
            if not addr.is_global:
                raise ValueError("नेटवर्क गंतव्य सुरक्षित नहीं है।")
    except socket.gaierror as exc:
        raise ValueError("YouTube होस्ट का DNS उपलब्ध नहीं है।") from exc
    if not (parsed.path and parsed.path != "/"):
        raise ValueError("वीडियो का पूरा लिंक डालें।")
    return value.strip()


def ydl_opts(extra=None):
    options = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "ignoreerrors": False,
        "socket_timeout": 18, "retries": 2, "extractor_retries": 2,
        "cachedir": False,
    }
    options.update(extra or {})
    return options


def cleanup():
    now = time.time()
    with LOCK:
        expired = [k for k, j in JOBS.items() if now - j["created"] > TTL and j["status"] != "processing"]
        for key in expired:
            JOBS.pop(key, None)
            shutil.rmtree(STORAGE / key, ignore_errors=True)


def public_job(j):
    return {k: j.get(k) for k in ("id", "status", "stage", "percent", "downloaded_bytes", "total_bytes", "speed", "eta", "error", "filename", "size")}


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True, ffmpeg=bool(shutil.which("ffmpeg")), ffprobe=bool(shutil.which("ffprobe")), engine="yt-dlp")


@app.post("/api/analyze")
def analyze():
    cleanup()
    try:
        url = valid_url((request.get_json(silent=True) or {}).get("url"))
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info or info.get("_type") == "playlist":
            raise ValueError("वीडियो की जानकारी नहीं मिली।")
        duration = info.get("duration") or 0
        if duration and duration > MAX_DURATION:
            return jsonify(error=f"इस सर्वर पर अधिकतम {MAX_DURATION // 60} मिनट के वीडियो समर्थित हैं।"), 413
        heights = sorted({int(f["height"]) for f in info.get("formats", []) if f.get("height") and f.get("vcodec") != "none"})
        choices = [{"id": str(h), "label": f"{h}p"} for h in heights if h <= 2160]
        choices.reverse()
        return jsonify(title=info.get("title") or "Video", thumbnail=info.get("thumbnail"), duration=duration,
                       uploader=info.get("uploader"), qualities=choices, audio=True,
                       note="फाइल का अंतिम आकार डाउनलोड/मर्ज के बाद सत्यापित होगा।")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception("analyze failed")
        return jsonify(error="वीडियो विश्लेषण विफल। वीडियो प्रतिबंधित हो सकता है या होस्टिंग IP ब्लॉक हो सकती है।"), 502


def worker(job_id, url, quality, audio_only):
    folder = STORAGE / job_id
    folder.mkdir(exist_ok=True)

    def update(**changes):
        with LOCK:
            JOBS[job_id].update(changes)

    def hook(data):
        if data.get("status") == "downloading":
            got = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            # 0-85% denotes server retrieval; 85-98% denotes post-processing.
            pct = round(85 * got / total, 1) if total else None
            update(stage="downloading", percent=pct, downloaded_bytes=got,
                   total_bytes=total or None, speed=data.get("speed"), eta=data.get("eta"))
        elif data.get("status") == "finished":
            update(stage="merging" if not audio_only else "converting", percent=85)

    def post_hook(data):
        if data.get("status") == "started":
            update(stage="merging" if not audio_only else "converting", percent=90)
        elif data.get("status") == "finished":
            update(stage="verifying", percent=98)

    try:
        if audio_only:
            fmt = "bestaudio/best"
            postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        else:
            h = int(quality)
            fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
            postprocessors = []
        options = ydl_opts({
            "skip_download": False,
            "format": fmt,
            "outtmpl": str(folder / "media.%(ext)s"),
            "merge_output_format": "mp4",
            "postprocessors": postprocessors,
            "progress_hooks": [hook],
            "postprocessor_hooks": [post_hook],
            "max_filesize": MAX_FILE_MB * 1024 * 1024,
            "restrictfilenames": True,
            "noprogress": True,
        })
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".mp4", ".mp3", ".mkv", ".webm", ".m4a")]
        if not candidates:
            raise RuntimeError("आउटपुट मीडिया फाइल नहीं मिली।")
        result = max(candidates, key=lambda p: p.stat().st_mtime)
        size = result.stat().st_size
        if size == 0 or size > MAX_FILE_MB * 1024 * 1024:
            raise RuntimeError("फाइल खाली है या सर्वर की आकार सीमा से बड़ी है।")
        update(status="complete", stage="complete", percent=100, filename=result.name, size=size, error=None)
    except Exception as exc:
        app.logger.warning("job %s failed: %s", job_id, str(exc)[:250])
        update(status="error", stage="error", error="डाउनलोड विफल। स्रोत प्रतिबंध, सर्वर IP, फॉर्मेट या संसाधन सीमा कारण हो सकते हैं।", percent=None)


@app.post("/api/jobs")
def start_job():
    cleanup()
    data = request.get_json(silent=True) or {}
    try:
        url = valid_url(data.get("url"))
        audio_only = data.get("mode") == "mp3"
        quality = str(data.get("quality", "720"))
        if not audio_only and (not quality.isdigit() or int(quality) not in (144, 240, 360, 480, 720, 1080, 1440, 2160)):
            raise ValueError("मान्य क्वालिटी चुनें।")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    with LOCK:
        active = sum(j["status"] == "processing" for j in JOBS.values())
        if active >= MAX_JOBS:
            return jsonify(error="सर्वर व्यस्त है। थोड़ी देर बाद दोबारा प्रयास करें।"), 429
        job_id = uuid.uuid4().hex
        JOBS[job_id] = {"id": job_id, "created": time.time(), "status": "processing", "stage": "queued", "percent": 0,
                        "downloaded_bytes": 0, "total_bytes": None, "speed": None, "eta": None, "error": None, "filename": None, "size": None}
    threading.Thread(target=worker, args=(job_id, url, quality, audio_only), daemon=True).start()
    return jsonify(id=job_id, status="processing"), 202


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    cleanup()
    with LOCK:
        j = JOBS.get(job_id)
        if not j:
            return jsonify(error="Job नहीं मिला या समाप्त हो गया।"), 404
        return jsonify(public_job(j))


@app.get("/api/files/<job_id>")
def file_download(job_id):
    cleanup()
    with LOCK:
        j = JOBS.get(job_id)
        if not j or j["status"] != "complete":
            abort(404)
        filename = j["filename"]
    path = STORAGE / job_id / filename
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=("streamrip." + path.suffix.lstrip(".")), conditional=True)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="अनुरोध या फाइल बहुत बड़ी है।"), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
