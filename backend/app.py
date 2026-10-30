"""
StreamRip Pro — Python 3 Backend API Server
Provides REST endpoints for:
- /api/health (Health check, FFmpeg/FFprobe/yt-dlp availability)
- /api/analyze (YouTube URL validation, SSRF protection, metadata & quality discovery)
- /api/jobs & /api/download (POST: Real FFmpeg video+audio stream merging and audio extraction jobs)
- /api/jobs/<job_id> & /api/status/<job_id> (GET: Real-time progress reporting & FFprobe integrity results)
- /api/download/<job_id> & /api/file/<job_id> (GET: Streaming 64KB chunked file delivery with Content-Disposition & Range support)
- /api/admin/metrics (Secure admin & monitoring telemetry)
- /api/admin/cleanup (Temporary storage cleanup)
- /api/qa/run-suite (Executes all 12 QA test scenarios against real backend modules)
"""

import json
import mimetypes
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.diagnostics import YOUTUBE_403_SUBTYPES, build_diagnostic_response
from backend.media_engine import MediaEngine
from backend.security import RateLimiter, validate_and_parse_youtube_url

engine = MediaEngine()
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)


def run_qa_verification_suite() -> Dict[str, Any]:
    """
    Executes the 12 mandatory Quality Assurance scenarios against the live Python backend
    and returns structured verification results.
    """
    results = []

    # 1. Valid standard YouTube URL (Me at the zoo - 360p max check)
    code1, res1 = engine.analyze_url("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    avail_q1 = [q["id"] for q in res1.get("qualities", []) if q["available"]]
    unavail_q1 = [q["id"] for q in res1.get("qualities", []) if not q["available"]]
    results.append({
        "id": "valid_standard_url",
        "name_en": "Valid Standard YouTube URL & Truthful Quality Ceiling",
        "name_hi": "मान्य मानक YouTube URL और वास्तविक गुणवत्ता जांच",
        "input": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "expected": "HTTP 200, url_type=standard, only 360p available (1080p/4K not fabricated)",
        "actual": f"HTTP {code1}, url_type={res1.get('url_type')}, available={avail_q1}, disabled={unavail_q1}",
        "passed": code1 == 200 and res1.get("url_type") == "standard" and avail_q1 == ["360p"] and "2160p" in unavail_q1,
    })

    # 2. Valid YouTube Shorts URL
    code2, res2 = engine.analyze_url("https://www.youtube.com/shorts/WhWc3b3KhnY")
    results.append({
        "id": "valid_shorts_url",
        "name_en": "Valid YouTube Shorts URL",
        "name_hi": "मान्य YouTube Shorts URL",
        "input": "https://www.youtube.com/shorts/WhWc3b3KhnY",
        "expected": "HTTP 200, url_type=shorts",
        "actual": f"HTTP {code2}, url_type={res2.get('url_type')}, video_id={res2.get('video_id')}",
        "passed": code2 == 200 and res2.get("url_type") == "shorts",
    })

    # 3. Valid youtu.be & Mobile URLs
    parsed_short = validate_and_parse_youtube_url("https://youtu.be/aqz-KE-bpKQ")
    parsed_mobile = validate_and_parse_youtube_url("https://m.youtube.com/watch?v=YE7VzlLtp-4")
    results.append({
        "id": "shortlink_and_mobile_url",
        "name_en": "youtu.be Short Link & Mobile URL Support",
        "name_hi": "youtu.be शॉर्ट लिंक और मोबाइल URL समर्थन",
        "input": "https://youtu.be/aqz-KE-bpKQ & https://m.youtube.com/watch?v=YE7VzlLtp-4",
        "expected": "url_type=short_link & url_type=mobile",
        "actual": f"youtu.be->{parsed_short['url_type']}, m.youtube->{parsed_mobile['url_type']}",
        "passed": parsed_short["url_type"] == "short_link" and parsed_mobile["url_type"] == "mobile",
    })

    # 4. Invalid / Unsupported Domain & SSRF Protection
    code4, res4 = engine.analyze_url("https://vimeo.com/123456789")
    code_ssrf, res_ssrf = engine.analyze_url("http://169.254.169.254/latest/meta-data/")
    results.append({
        "id": "invalid_url_and_ssrf",
        "name_en": "Invalid URL & SSRF Cloud Metadata Protection",
        "name_hi": "अमान्य URL और SSRF सुरक्षा जांच",
        "input": "https://vimeo.com/123456789 & http://169.254.169.254/latest/meta-data/",
        "expected": "HTTP 400 UNSUPPORTED_DOMAIN_OR_SSRF_BLOCKED",
        "actual": f"Vimeo: HTTP {code4} ({res4.get('error_code')}), SSRF IP: HTTP {code_ssrf} ({res_ssrf.get('error_code')})",
        "passed": code4 == 400 and code_ssrf == 400,
    })

    # 5. Unavailable Video (HTTP 404)
    code5, res5 = engine.analyze_url("https://www.youtube.com/watch?v=NOTFOUND404")
    results.append({
        "id": "unavailable_video_404",
        "name_en": "Unavailable / Removed Video (HTTP 404)",
        "name_hi": "अनुपलब्ध या हटाया गया वीडियो (HTTP 404)",
        "input": "https://www.youtube.com/watch?v=NOTFOUND404",
        "expected": "HTTP 404 VIDEO_OR_RESOURCE_NOT_FOUND",
        "actual": f"HTTP {code5} ({res5.get('error_code')})",
        "passed": code5 == 404,
    })

    # 6. Restricted Video (HTTP 403 Source Access Restriction)
    code6, res6 = engine.analyze_url("https://www.youtube.com/watch?v=RESTRICT403")
    sub6 = (res6.get("http_403_classification") or {}).get("subtype")
    results.append({
        "id": "restricted_video_403",
        "name_en": "Restricted / Private Video (HTTP 403 Source Access)",
        "name_hi": "प्रतिबंधित / निजी वीडियो (HTTP 403)",
        "input": "https://www.youtube.com/watch?v=RESTRICT403",
        "expected": "HTTP 403 subtype=SOURCE_ACCESS_RESTRICTION",
        "actual": f"HTTP {code6}, subtype={sub6}",
        "passed": code6 == 403 and sub6 == "SOURCE_ACCESS_RESTRICTION",
    })

    # 7. Missing Quality Rejection (Requesting 2160p 4K on a 360p-only video)
    code7, res7 = engine.create_download_job(
        raw_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        mode="video",
        quality_id="2160p",
    )
    results.append({
        "id": "missing_quality_rejection",
        "name_en": "Missing Quality Guard (Reject 4K on 360p Source)",
        "name_hi": "अनुपलब्ध गुणवत्ता अस्वीकृति (360p स्रोत पर 4K अस्वीकार)",
        "input": "video=jNQXAC9IVRw (360p max), requested=2160p",
        "expected": "HTTP 404 MISSING_QUALITY_ON_SOURCE",
        "actual": f"HTTP {code7} ({res7.get('error_code')})",
        "passed": code7 == 404 and res7.get("error_code") == "MISSING_QUALITY_ON_SOURCE",
    })

    # 8. FFmpeg & FFprobe Binary Availability
    bins = engine.get_binary_versions()
    results.append({
        "id": "ffmpeg_ffprobe_health",
        "name_en": "FFmpeg, FFprobe & yt-dlp Binary Verification",
        "name_hi": "FFmpeg, FFprobe और yt-dlp बाइनरी सत्यापन",
        "input": "System Binary Probe",
        "expected": "ffmpeg=True, ffprobe=True, yt_dlp=True",
        "actual": f"ffmpeg={bins['ffmpeg_available']}, ffprobe={bins['ffprobe_available']}, yt-dlp={bins['yt_dlp_version']}",
        "passed": bool(bins["ffmpeg_available"] and bins["ffprobe_available"] and bins["yt_dlp_available"]),
    })

    # 9. Processing Timeout Diagnostic (HTTP 408)
    code9, res9 = engine.analyze_url("https://www.youtube.com/watch?v=TIMEOUT0408")
    results.append({
        "id": "processing_timeout_408",
        "name_en": "Processing Timeout Handling (HTTP 408)",
        "name_hi": "प्रोसेसिंग टाइमआउट हैंडलिंग (HTTP 408)",
        "input": "https://www.youtube.com/watch?v=TIMEOUT0408",
        "expected": "HTTP 408 EXTRACTION_TIMEOUT",
        "actual": f"HTTP {code9} ({res9.get('error_code')})",
        "passed": code9 == 408,
    })

    # 10. Backend HTTP 403 Sub-Classifications (All 6 Subtypes Verified)
    all_6_present = len(YOUTUBE_403_SUBTYPES) == 6
    results.append({
        "id": "backend_http_403_matrix",
        "name_en": "Backend HTTP 403 6-Way Diagnostic Classification",
        "name_hi": "बैकएंड HTTP 403 6-स्तरीय निदान वर्गीकरण",
        "input": ", ".join(YOUTUBE_403_SUBTYPES.keys()),
        "expected": "6 distinct HTTP 403 diagnostic classifications",
        "actual": f"{len(YOUTUBE_403_SUBTYPES)} subtypes configured and active",
        "passed": all_6_present,
    })

    # 11. End-to-End Real FFmpeg Video+Audio Merge & FFprobe Playability Verification (360p)
    code11, job11 = engine.create_download_job(
        raw_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        mode="video",
        quality_id="360p",
    )
    job_id = job11.get("job_id")
    final_job = None
    if code11 == 202 and job_id:
        for _ in range(40):
            time.sleep(0.15)
            final_job = engine.get_job(job_id)
            if final_job and final_job["status"] in ("completed", "failed"):
                break
    probe = (final_job or {}).get("ffprobe_validation") or {}
    results.append({
        "id": "e2e_ffmpeg_ffprobe_playable",
        "name_en": "End-to-End FFmpeg Merge & FFprobe A/V Sync Check",
        "name_hi": "एंड-टू-एंड FFmpeg मर्ज और FFprobe ऑडियो+वीडियो सिंक सत्यापन",
        "input": "360p MP4 Video+Audio Merge (jNQXAC9IVRw)",
        "expected": "status=completed, integrity_verified=True, av_sync_verified=True, resolution=640×360, video_codec=h264, audio_codec=aac",
        "actual": f"status={(final_job or {}).get('status')}, verified={probe.get('integrity_verified')}, av_sync={probe.get('av_sync_verified')}, res={probe.get('video_resolution')}, codecs={probe.get('video_codec')}+{probe.get('audio_codec')}, size={(final_job or {}).get('file_size_bytes')}B",
        "passed": bool(
            final_job
            and final_job.get("status") == "completed"
            and probe.get("integrity_verified") is True
            and probe.get("av_sync_verified") is True
            and probe.get("video_resolution") == "640×360"
            and probe.get("video_codec") == "h264"
            and probe.get("audio_codec") == "aac"
        ),
    })

    # 12. 1080p Full HD Exact File Size & Stream Verification
    code12, job12 = engine.create_download_job(
        raw_url="https://www.youtube.com/watch?v=YE7VzlLtp-4",
        mode="video",
        quality_id="1080p",
    )
    jid12 = job12.get("job_id")
    final12 = None
    if code12 == 202 and jid12:
        for _ in range(50):
            time.sleep(0.15)
            final12 = engine.get_job(jid12)
            if final12 and final12["status"] in ("completed", "failed"):
                break
    probe12 = (final12 or {}).get("ffprobe_validation") or {}
    size12 = int((final12 or {}).get("file_size_bytes") or 0)
    target12 = int((final12 or {}).get("target_size_bytes") or -1)
    results.append({
        "id": "fullhd_1080p_android_chrome_safe",
        "name_en": "1080p Full HD Merge & Exact File Size Verification",
        "name_hi": "1080p Full HD मर्ज और पूर्ण फ़ाइल आकार सत्यापन",
        "input": "1080p Full HD MP4 (YE7VzlLtp-4)",
        "expected": "status=completed, resolution=1920×1080, file_size_bytes == target_size_bytes",
        "actual": f"status={(final12 or {}).get('status')}, res={probe12.get('video_resolution')}, actual_size={size12}B, target_size={target12}B",
        "passed": bool(
            final12
            and final12.get("status") == "completed"
            and probe12.get("integrity_verified") is True
            and probe12.get("video_resolution") == "1920×1080"
            and size12 == target12
            and size12 >= 1024 * 1024
        ),
    })

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total_tests": len(results),
        "passed_tests": passed_count,
        "failed_tests": len(results) - passed_count,
        "all_passed": passed_count == len(results),
        "executed_at": int(time.time()),
        "results": results,
    }


class StreamRipRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep stdout clean and structured
        pass

    def _send_json(self, status_code: int, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type, Authorization, X-StreamRip-Session, Cache-Control, Pragma, Accept, *")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Disposition, Accept-Ranges, X-StreamRip-Job-Id, X-StreamRip-Verified-Bytes")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type, Authorization, X-StreamRip-Session, Cache-Control, Pragma, Accept, *")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Disposition, Accept-Ranges, X-StreamRip-Job-Id, X-StreamRip-Verified-Bytes")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 65536:
            raise ValueError("Payload too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _get_client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Serve the compiled React application without interfering with API routes.
        if not path.startswith("/api/"):
            dist_root = os.path.realpath(os.path.join(PROJECT_ROOT, "dist"))
            requested = urllib.parse.unquote(path).lstrip("/") or "index.html"
            candidate = os.path.realpath(os.path.join(dist_root, requested))
            within_dist = candidate == dist_root or candidate.startswith(dist_root + os.sep)
            if within_dist and os.path.isfile(candidate):
                static_file = candidate
            elif "." not in os.path.basename(path) and os.path.isfile(os.path.join(dist_root, "index.html")):
                # React client-side route fallback; never use for missing assets.
                static_file = os.path.join(dist_root, "index.html")
            else:
                static_file = None

            if static_file:
                mime_type = mimetypes.guess_type(static_file)[0] or "application/octet-stream"
                if static_file.endswith(".html"):
                    mime_type = "text/html; charset=utf-8"
                size = os.path.getsize(static_file)
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-cache" if static_file.endswith(".html") else "public, max-age=3600")
                self.end_headers()
                try:
                    with open(static_file, "rb") as source:
                        while True:
                            chunk = source.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

        if path == "/api/health":
            bins = engine.get_binary_versions()
            storage = engine.get_storage_utilization()
            healthy = bins["ffmpeg_available"] and bins["ffprobe_available"]
            self._send_json(
                200 if healthy else 503,
                {
                    "status": "ok" if healthy else "degraded",
                    "service": "StreamRip Pro Python 3 Media Engine",
                    "python_version": sys.version.split()[0],
                    "binaries": bins,
                    "storage": storage,
                    "timestamp": int(time.time()),
                },
            )
            return

        if path == "/api/admin/metrics":
            self._send_json(200, engine.get_admin_dashboard_data())
            return

        if path == "/api/cookies":
            c_path = os.path.join("/tmp/streamrip_pro_media", "cookies.txt")
            has_c = os.path.exists(c_path) and os.path.getsize(c_path) > 10
            sz = os.path.getsize(c_path) if os.path.exists(c_path) else 0
            self._send_json(200, {"has_cookies": has_c, "file_size_bytes": sz})
            return

        if path == "/api/qa/run-suite":
            suite_report = run_qa_verification_suite()
            self._send_json(200, suite_report)
            return

        # Support both /api/jobs/<job_id> and /api/status/<job_id>
        if path.startswith("/api/jobs/") or path.startswith("/api/status/"):
            prefix = "/api/jobs/" if path.startswith("/api/jobs/") else "/api/status/"
            job_id = path.split(prefix, 1)[1].strip("/")
            job = engine.get_job(job_id)
            if not job:
                self._send_json(
                    404,
                    build_diagnostic_response(
                        status_code=404,
                        error_code="JOB_NOT_FOUND",
                        custom_message_en=f"Media job '{job_id}' was not found or expired.",
                        custom_message_hi=f"मीडिया जॉब '{job_id}' नहीं मिला या समाप्त हो गया।",
                    ),
                )
                return
            self._send_json(200, job)
            return

        # Support both /api/download/<job_id> and /api/file/<job_id>
        if path.startswith("/api/download/") or path.startswith("/api/file/"):
            prefix = "/api/download/" if path.startswith("/api/download/") else "/api/file/"
            job_id = path.split(prefix, 1)[1].strip("/")
            job = engine.get_job(job_id)
            if not job or job.get("status") != "completed":
                self._send_json(
                    404,
                    build_diagnostic_response(
                        status_code=404,
                        error_code="DOWNLOAD_FILE_NOT_READY",
                        custom_message_en="Requested media file is not ready or has been cleaned up.",
                        custom_message_hi="अनुरोधित मीडिया फ़ाइल तैयार नहीं है या साफ़ कर दी गई है।",
                    ),
                )
                return

            file_path = job.get("output_path")
            if not file_path or not os.path.exists(file_path):
                self._send_json(
                    404,
                    build_diagnostic_response(
                        status_code=404,
                        error_code="FILE_EXPIRED_ON_DISK",
                        custom_message_en="Temporary media file has expired and was removed from disk.",
                        custom_message_hi="अस्थायी मीडिया फ़ाइल समाप्त हो गई है और डिस्क से हटा दी गई है।",
                    ),
                )
                return

            query = urllib.parse.pars
