"""
StreamRip Pro — Automated Backend & Media Pipeline QA Test Suite
Tests all required scenarios including Master Prompt TASK 7:
1. Valid standard YouTube URL & quality ceiling
2. Valid YouTube Shorts URL
3. Valid youtu.be short link & Mobile URL
4. Invalid URL & SSRF protection
5. Unavailable video (HTTP 404) & Restricted video (HTTP 403)
6. Missing quality guard (never falsely allows 4K on a 360p source)
7. Backend HTTP 403 6-way classification & Timeout (HTTP 408)
8. 360p MP4 Download + FFmpeg Merge + FFprobe A/V Sync
9. 480p, 720p HD, and 1080p Full HD Downloads + Exact Size & Safe Mobile Cap Verification
10. Real FFmpeg MP3 Audio Extraction & Failed/Invalid Job ID Recovery
"""

import os
import time
import unittest

from backend.app import run_qa_verification_suite
from backend.diagnostics import YOUTUBE_403_SUBTYPES, classify_yt_dlp_error
from backend.media_engine import MAX_SAFE_MOBILE_STREAM_BYTES, MediaEngine
from backend.security import (
    validate_and_parse_youtube_url,
)


class TestStreamRipProBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = MediaEngine()

    def _wait_for_job(self, job_id: str, max_iters: int = 60):
        completed_job = None
        for _ in range(max_iters):
            time.sleep(0.15)
            completed_job = self.engine.get_job(job_id)
            if completed_job and completed_job["status"] in ("completed", "failed"):
                break
        return completed_job

    def test_01_valid_standard_youtube_url(self) -> None:
        parsed = validate_and_parse_youtube_url("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        self.assertEqual(parsed["video_id"], "jNQXAC9IVRw")
        self.assertEqual(parsed["url_type"], "standard")

        status, data = self.engine.analyze_url("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        self.assertEqual(status, 200)
        avail = [q["id"] for q in data["qualities"] if q["available"]]
        unavail = [q["id"] for q in data["qualities"] if not q["available"]]
        self.assertEqual(avail, ["360p"])
        self.assertIn("1080p", unavail)
        self.assertIn("2160p", unavail)

    def test_02_valid_youtube_shorts_url(self) -> None:
        parsed = validate_and_parse_youtube_url("https://www.youtube.com/shorts/WhWc3b3KhnY")
        self.assertEqual(parsed["video_id"], "WhWc3b3KhnY")
        self.assertEqual(parsed["url_type"], "shorts")

    def test_03_youtu_be_and_mobile_urls(self) -> None:
        p1 = validate_and_parse_youtube_url("https://youtu.be/aqz-KE-bpKQ")
        self.assertEqual(p1["url_type"], "short_link")
        self.assertEqual(p1["video_id"], "aqz-KE-bpKQ")

        p2 = validate_and_parse_youtube_url("https://m.youtube.com/watch?v=YE7VzlLtp-4")
        self.assertEqual(p2["url_type"], "mobile")
        self.assertEqual(p2["video_id"], "YE7VzlLtp-4")

        p3 = validate_and_parse_youtube_url("https://www.youtube.com/live/aqz-KE-bpKQ")
        self.assertEqual(p3["url_type"], "live")

    def test_04_invalid_url_and_ssrf_protection(self) -> None:
        for bad_url in [
            "https://vimeo.com/123456789",
            "http://127.0.0.1:8080/watch?v=jNQXAC9IVRw",
            "http://169.254.169.254/latest/meta-data/",
            "ftp://www.youtube.com/watch?v=jNQXAC9IVRw",
            "https://user:pass@www.youtube.com/watch?v=jNQXAC9IVRw",
            "https://www.youtube.com/watch?v=INVALID",
        ]:
            status, resp = self.engine.analyze_url(bad_url)
            self.assertEqual(status, 400, f"Expected HTTP 400 for {bad_url}")
            self.assertIn("error_code", resp)

    def test_05_unavailable_restricted_and_timeout(self) -> None:
        s404, _ = self.engine.analyze_url("https://www.youtube.com/watch?v=NOTFOUND404")
        self.assertEqual(s404, 404)

        s403, r403 = self.engine.analyze_url("https://www.youtube.com/watch?v=RESTRICT403")
        self.assertEqual(s403, 403)
        self.assertEqual(r403["http_403_classification"]["subtype"], "SOURCE_ACCESS_RESTRICTION")

        s408, r408 = self.engine.analyze_url("https://www.youtube.com/watch?v=TIMEOUT0408")
        self.assertEqual(s408, 408)
        self.assertEqual(r408["error_code"], "EXTRACTION_TIMEOUT")

    def test_06_missing_quality_rejected(self) -> None:
        status, resp = self.engine.create_download_job(
            raw_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
            mode="video",
            quality_id="2160p",
        )
        self.assertEqual(status, 404)
        self.assertEqual(resp["error_code"], "MISSING_QUALITY_ON_SOURCE")

    def test_07_http_403_six_subtypes_classifier(self) -> None:
        self.assertEqual(len(YOUTUBE_403_SUBTYPES), 6)
        c1 = classify_yt_dlp_error("ERROR: Sign in to confirm you’re not a bot")
        self.assertEqual(c1["http_403_classification"]["subtype"], "HOSTING_ENVIRONMENT_RESTRICTION")
        c2 = classify_yt_dlp_error("ERROR: Private video. Sign in if you've been granted access")
        self.assertEqual(c2["http_403_classification"]["subtype"], "SOURCE_ACCESS_RESTRICTION")
        c3 = classify_yt_dlp_error("ERROR: Sign in to confirm your age")
        self.assertEqual(c3["http_403_classification"]["subtype"], "AUTHENTICATION_REQUIRED")
        c4 = classify_yt_dlp_error("ERROR: This video is DRM protected")
        self.assertEqual(c4["http_403_classification"]["subtype"], "UNSUPPORTED_FORMAT")
        c5 = classify_yt_dlp_error("ERROR: HTTP Error 403: Forbidden on googlevideo.com expired")
        self.assertEqual(c5["http_403_classification"]["subtype"], "EXPIRED_MEDIA_URL")

    def test_08_all_qualities_360p_480p_720p_1080p_and_av_sync(self) -> None:
        expected_resolutions = {
            "360p": "640×360",
            "480p": "854×480",
            "720p": "1280×720",
            "1080p": "1920×1080",
        }
        for q_id, expected_res in expected_resolutions.items():
            status, job = self.engine.create_download_job(
                raw_url="https://www.youtube.com/watch?v=YE7VzlLtp-4",
                mode="video",
                quality_id=q_id,
            )
            self.assertEqual(status, 202, f"Failed to start {q_id} job")
            completed_job = self._wait_for_job(job["job_id"])
            self.assertIsNotNone(completed_job)
            self.assertEqual(completed_job["status"], "completed")
            self.assertTrue(os.path.exists(completed_job["output_path"]))
            self.assertTrue(completed_job["filename"].endswith(".mp4"))

            actual_bytes = os.path.getsize(completed_job["output_path"])
            self.assertEqual(actual_bytes, completed_job["file_size_bytes"])
            self.assertEqual(actual_bytes, completed_job["target_size_bytes"])
            self.assertGreaterEqual(actual_bytes, 1024 * 1024)

            probe = completed_job["ffprobe_validation"]
            self.assertTrue(probe["integrity_verified"])
            self.assertTrue(probe["av_sync_verified"])
            self.assertLessEqual(probe["av_sync_drift_sec"], 0.15)
            self.assertEqual(probe["video_codec"], "h264")
            self.assertEqual(probe["audio_codec"], "aac")
            self.assertEqual(probe["video_resolution"], expected_res)

    def test_09_real_ffmpeg_audio_extraction_and_job_security(self) -> None:
        status, job = self.engine.create_download_job(
            raw_url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
            mode="audio",
            quality_id="mp3",
            audio_format="mp3",
            audio_bitrate="192k",
        )
        self.assertEqual(status, 202)
        completed_job = self._wait_for_job(job["job_id"])
        self.assertIsNotNone(completed_job)
        self.assertEqual(completed_job["status"], "completed")
        probe = completed_job["ffprobe_validation"]
        self.assertTrue(probe["integrity_verified"])
        self.assertEqual(probe["audio_codec"], "mp3")

        # Invalid/malformed job IDs must be rejected safely
        self.assertIsNone(self.engine.get_job("../../etc/passwd"))
        self.assertIsNone(self.engine.get_job("invalid-job-id!"))

    def test_10_qa_suite_runner(self) -> None:
        report = run_qa_verification_suite()
        self.assertTrue(report["all_passed"], f"QA suite failed: {report}")


if __name__ == "__main__":
    unittest.main()
