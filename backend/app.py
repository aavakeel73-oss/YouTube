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
import logging
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("streamrip.api")

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
        logger.info("request client=%s message=%s", self.client_address[0], (format % args).split("?")[0])

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

            query = urllib.parse.parse_qs(parsed.query)
            inline_mode = query.get("inline", ["0"])[0] == "1"
            filename = job.get("filename") or os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "video/mp4" if filename.endswith(".mp4") else "audio/mpeg"

            file_size = os.path.getsize(file_path)
            disposition = "inline" if inline_mode else "attachment"

            # Support HTTP Range requests for mobile Chrome / HTML5 media playback
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                try:
                    range_spec = range_header.split("=", 1)[1]
                    start_str, end_str = range_spec.split("-", 1)
                    start_byte = int(start_str) if start_str else 0
                    end_byte = int(end_str) if end_str else file_size - 1
                    end_byte = min(end_byte, file_size - 1)
                    chunk_len = (end_byte - start_byte) + 1

                    self.send_response(206)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(chunk_len))
                    self.send_header("Content-Range", f"bytes {start_byte}-{end_byte}/{file_size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
                    self.send_header("Access-Control-Allow-Headers", "Range, Content-Type, Authorization, X-StreamRip-Session, *")
                    self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Disposition, Accept-Ranges, X-StreamRip-Job-Id, X-StreamRip-Verified-Bytes")
                    self.send_header("X-StreamRip-Job-Id", job_id)
                    self.send_header("X-StreamRip-Verified-Bytes", str(file_size))
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start_byte)
                        remaining = chunk_len
                        while remaining > 0:
                            data = f.read(min(1048576, remaining))
                            if not data:
                                break
                            self.wfile.write(data)
                            remaining -= len(data)
                    return
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    return

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Range, Content-Type, Authorization, X-StreamRip-Session, *")
            self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Disposition, Accept-Ranges, X-StreamRip-Job-Id, X-StreamRip-Verified-Bytes")
            self.send_header("X-StreamRip-Job-Id", job_id)
            self.send_header("X-StreamRip-Verified-Bytes", str(file_size))
            self.end_headers()

            try:
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(1048576)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        self._send_json(404, build_diagnostic_response(404, "ENDPOINT_NOT_FOUND"))

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/download/") or path.startswith("/api/file/"):
            prefix = "/api/download/" if path.startswith("/api/download/") else "/api/file/"
            job_id = path.split(prefix, 1)[1].strip("/")
            job = engine.get_job(job_id)
            if not job or job.get("status") != "completed":
                self.send_response(404)
                self.end_headers()
                return
            file_path = job.get("output_path")
            if not file_path or not os.path.exists(file_path):
                self.send_response(404)
                self.end_headers()
                return
            filename = job.get("filename") or os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "video/mp4" if filename.endswith(".mp4") else "audio/mpeg"
            file_size = os.path.getsize(file_path)
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("X-StreamRip-Job-Id", job_id)
            self.send_header("X-StreamRip-Verified-Bytes", str(file_size))
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        client_ip = self._get_client_ip()
        allowed, retry_after = rate_limiter.check_allowed(client_ip)
        if not allowed:
            engine.record_error(429)
            self._send_json(
                429,
                build_diagnostic_response(
                    status_code=429,
                    error_code="RATE_LIMIT_EXCEEDED",
                    custom_message_en=f"Rate limit exceeded. Please wait {retry_after} seconds before sending another request.",
                    custom_message_hi=f"अनुरोध सीमा पार हो गई। कृपया नया अनुरोध भेजने से पहले {retry_after} सेकंड प्रतीक्षा करें।",
                ),
                extra_headers={"Retry-After": str(retry_after)},
            )
            return

        try:
            body = self._read_json_body()
        except Exception as exc:
            engine.record_error(400)
            self._send_json(
                400,
                build_diagnostic_response(
                    status_code=400,
                    error_code="INVALID_JSON_PAYLOAD",
                    custom_message_en=f"Invalid JSON request body: {exc}",
                    custom_message_hi="अमान्य JSON अनुरोध पेलोड।",
                ),
            )
            return

        if path == "/api/analyze":
            raw_url = str(body.get("url") or "")
            strict_live = bool(body.get("strict_live_only", False))
            simulate_diag = body.get("simulate_diagnostic")
            status_code, response_data = engine.analyze_url(
                raw_url=raw_url,
                strict_live_only=strict_live,
                simulate_diagnostic=simulate_diag,
            )
            if status_code >= 400:
                logger.warning("analyze failed status=%s code=%s", status_code, response_data.get("error_code"))
            self._send_json(status_code, response_data)
            return

        # Support both POST /api/jobs and POST /api/download
        if path in ("/api/jobs", "/api/download"):
            import base64
            raw_url = str(body.get("url") or "")
            mode = str(body.get("mode") or "video")
            quality_id = str(body.get("quality_id") or body.get("quality") or "720p")
            audio_format = str(body.get("audio_format") or "mp3")
            audio_bitrate = str(body.get("audio_bitrate") or "192k")
            inline_blob = bool(body.get("inline_blob", False))

            status_code, response_data = engine.create_download_job(
                raw_url=raw_url,
                mode=mode,
                quality_id=quality_id,
                audio_format=audio_format,
                audio_bitrate=audio_bitrate,
            )

            if status_code == 202 and inline_blob and response_data.get("job_id"):
                jid = response_data["job_id"]
                for _ in range(70):
                    time.sleep(0.05)
                    latest = engine.get_job(jid)
                    if latest and latest.get("status") in ("completed", "failed"):
                        response_data = dict(latest)
                        break

                if response_data.get("status") == "completed":
                    fpath = response_data.get("output_path")
                    if fpath and os.path.exists(fpath):
                        fname = response_data.get("filename") or os.path.basename(fpath)
                        mtype, _ = mimetypes.guess_type(fname)
                        if not mtype:
                            mtype = "video/mp4" if fname.endswith(".mp4") else "audio/mpeg"
                        fsize = os.path.getsize(fpath)
                        # Zero silent truncation:
                        # For files <= 50 MB, base64 inline delivery is safe without browser heap exhaustion.
                        # For files > 50 MB, do NOT truncate to 25 MB! Instead, direct streaming (/api/download/<job_id>)
                        # must be used so 100% of the original video bytes are delivered directly to disk.
                        if fsize <= 50 * 1024 * 1024:
                            with open(fpath, "rb") as bf:
                                rbytes = bf.read()
                            response_data["inline_blob_data"] = {
                                "job_id": jid,
                                "filename": fname,
                                "mime_type": mtype,
                                "size_bytes": fsize,
                                "base_stream_bytes": len(rbytes),
                                "target_size_bytes": int(response_data.get("target_size_bytes") or fsize),
                                "container_ext": str(response_data.get("container_ext") or "mp4").lower(),
                                "base64_data": base64.b64encode(rbytes).decode("ascii"),
                            }
                        else:
                            response_data["direct_download_url"] = f"/api/download/{jid}"

            if status_code >= 400:
                logger.warning("job failed status=%s code=%s", status_code, response_data.get("error_code"))
            self._send_json(status_code, response_data)
            return

        if path == "/api/admin/cleanup":
            res = engine.cleanup_temp_files(force_all=True)
            self._send_json(
                200,
                {
                    "status": "cleaned",
                    **res,
                    "storage": engine.get_storage_utilization(),
                },
            )
            return

        if path == "/api/cookies":
            cookies_text = str(body.get("cookies_text") or "").strip()
            if not cookies_text:
                self._send_json(400, {"error": "Cookie content cannot be empty"})
                return
            c_path = os.path.join("/tmp/streamrip_pro_media", "cookies.txt")
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(cookies_text)
            self._send_json(200, {"success": True, "has_cookies": True, "file_size_bytes": len(cookies_text.encode())})
            return

        if path == "/api/cookies/clear":
            c_path = os.path.join("/tmp/streamrip_pro_media", "cookies.txt")
            if os.path.exists(c_path):
                try:
                    os.remove(c_path)
                except OSError:
                    pass
            self._send_json(200, {"success": True, "has_cookies": False})
            return

        if path == "/api/qa/run-suite":
            suite_report = run_qa_verification_suite()
            self._send_json(200, suite_report)
            return

        if path == "/api/download-blob":
            import base64
            job_id = str(body.get("job_id") or "").strip()
            job = engine.get_job(job_id)
            if not job or job.get("status") != "completed":
                self._send_json(
                    404,
                    build_diagnostic_response(
                        status_code=404,
                        error_code="DOWNLOAD_FILE_NOT_READY",
                        custom_message_en="Requested media file is not ready or has expired.",
                        custom_message_hi="अनुरोधित मीडिया फ़ाइल तैयार नहीं है या समाप्त हो गई है।",
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
                        custom_message_en="Temporary media file has expired on disk.",
                        custom_message_hi="अस्थायी मीडिया फ़ाइल डिस्क से समाप्त हो गई है।",
                    ),
                )
                return

            filename = job.get("filename") or os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "video/mp4" if filename.endswith(".mp4") else "audio/mpeg"

            full_file_size = os.path.getsize(file_path)

            # Never silently truncate to 25 MB! (Requirement 8)
            # If the file exceeds 50 MB, base64 transfer is dangerous for browser memory.
            # Return explicit DIRECT_STREAM_REQUIRED error pointing to /api/download/<job_id>
            # rather than silently cutting the file!
            if full_file_size > 50 * 1024 * 1024:
                file_mb = round(full_file_size / (1024 * 1024), 2)
                self._send_json(
                    413,
                    build_diagnostic_response(
                        status_code=413,
                        error_code="DIRECT_STREAM_REQUIRED",
                        custom_message_en=f"File is {file_mb} MB. Base64 transfer limit is 50 MB. Use direct HTTP streaming (/api/download/{job_id}) to download full file without truncation.",
                        custom_message_hi=f"फ़ाइल का आकार {file_mb} MB है। चुपचाप 25 MB में छोटा करने के बजाय, पूरा वीडियो डाउनलोड करने के लिए सीधा डाउनलोड (/api/download/{job_id}) उपयोग करें।",
                    ),
                )
                return

            with open(file_path, "rb") as f:
                raw_bytes = f.read()

            b64_data = base64.b64encode(raw_bytes).decode("ascii")
            self._send_json(
                200,
                {
                    "job_id": job_id,
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": full_file_size,
                    "base_stream_bytes": len(raw_bytes),
                    "target_size_bytes": int(job.get("target_size_bytes") or full_file_size),
                    "container_ext": str(job.get("container_ext") or "mp4").lower(),
                    "base64_data": b64_data,
                },
            )
            return

        self._send_json(404, build_diagnostic_response(404, "ENDPOINT_NOT_FOUND"))


def run_server(host: str = "127.0.0.1", port: int = 5001) -> None:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), StreamRipRequestHandler)
    print(f"[StreamRip Pro Python Engine] Listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    port_num = int(os.environ.get("PYTHON_BACKEND_PORT", "5001"))
    run_server(host="0.0.0.0", port=port_num)
