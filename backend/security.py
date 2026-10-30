"""
StreamRip Pro — Website Security & URL Validation Module
Implements:
- Server-side URL allowlisting
- SSRF protection (blocks private, loopback, link-local, and metadata IPs)
- YouTube URL format validation (Standard, Shorts, youtu.be, Mobile, Live)
- Secure filename sanitization
- Sliding-window request rate limiting
"""

import ipaddress
import re
import socket
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class SecurityValidationError(Exception):
    def __init__(self, status_code: int, error_code: str, message_en: str, message_hi: str, details: Optional[Dict] = None):
        super().__init__(message_en)
        self.status_code = status_code
        self.error_code = error_code
        self.message_en = message_en
        self.message_hi = message_hi
        self.details = details or {}


def is_private_or_reserved_ip(ip_str: str) -> bool:
    """Checks if an IP address is loopback, private, link-local, multicast, or cloud metadata."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
            or str(ip_obj) == "169.254.169.254"
        )
    except ValueError:
        return True


def verify_ssrf_safe_host(hostname: str) -> None:
    """Ensures hostname is in the strict allowlist and does not resolve to internal/private IPs."""
    host_lower = hostname.lower().strip(".")
    if host_lower not in ALLOWED_YOUTUBE_HOSTS:
        raise SecurityValidationError(
            status_code=400,
            error_code="UNSUPPORTED_DOMAIN_OR_SSRF_BLOCKED",
            message_en=f"Unsupported domain '{hostname}'. Only official YouTube domains (youtube.com, youtu.be, m.youtube.com) are allowed.",
            message_hi=f"असमर्थित डोमेन '{hostname}'। केवल आधिकारिक YouTube डोमेन (youtube.com, youtu.be, m.youtube.com) की अनुमति है।",
            details={"hostname": hostname, "allowed_hosts": sorted(list(ALLOWED_YOUTUBE_HOSTS))},
        )

    # Check if raw IP was passed
    try:
        ipaddress.ip_address(host_lower)
        raise SecurityValidationError(
            status_code=400,
            error_code="SSRF_DIRECT_IP_FORBIDDEN",
            message_en="Direct IP addresses are forbidden by SSRF security policy.",
            message_hi="SSRF सुरक्षा नीति द्वारा सीधे IP पते प्रतिबंधित हैं।",
            details={"hostname": hostname},
        )
    except ValueError:
        pass

    # Resolve DNS and verify no private/loopback IP is returned
    try:
        addr_info = socket.getaddrinfo(host_lower, 443, proto=socket.IPPROTO_TCP)
        for family, _, _, _, sockaddr in addr_info:
            resolved_ip = sockaddr[0]
            if is_private_or_reserved_ip(resolved_ip):
                raise SecurityValidationError(
                    status_code=403,
                    error_code="SSRF_PRIVATE_IP_DETECTED",
                    message_en="Target hostname resolved to a restricted internal network address.",
                    message_hi="लक्ष्य होस्टनाम एक प्रतिबंधित आंतरिक नेटवर्क पते पर हल हुआ।",
                    details={"hostname": hostname},
                )
    except socket.gaierror:
        # In restricted DNS sandboxes, allow allowlisted domain to proceed to extractor stage
        pass


def validate_and_parse_youtube_url(raw_url: str) -> Dict[str, str]:
    """
    Validates and classifies a YouTube URL into:
    - standard: youtube.com/watch?v=ID
    - shorts: youtube.com/shorts/ID
    - short_link: youtu.be/ID
    - mobile: m.youtube.com/watch?v=ID or m.youtube.com/shorts/ID
    - live: youtube.com/live/ID
    """
    if not raw_url or not isinstance(raw_url, str):
        raise SecurityValidationError(
            status_code=400,
            error_code="EMPTY_URL",
            message_en="Please provide a valid YouTube URL.",
            message_hi="कृपया एक मान्य YouTube URL प्रदान करें।",
        )

    cleaned_url = raw_url.strip()
    if len(cleaned_url) > 2048:
        raise SecurityValidationError(
            status_code=400,
            error_code="URL_TOO_LONG",
            message_en="URL exceeds maximum permitted length of 2048 characters.",
            message_hi="URL 2048 वर्णों की अधिकतम अनुमत लंबाई से अधिक है।",
        )

    try:
        parsed = urllib.parse.urlparse(cleaned_url)
    except Exception:
        raise SecurityValidationError(
            status_code=400,
            error_code="MALFORMED_URL",
            message_en="The provided string could not be parsed as a valid URL.",
            message_hi="प्रदान की गई स्ट्रिंग को मान्य URL के रूप में पार्स नहीं किया जा सका।",
        )

    if parsed.scheme not in ("http", "https"):
        raise SecurityValidationError(
            status_code=400,
            error_code="INVALID_URL_SCHEME",
            message_en="Only HTTP and HTTPS protocols are permitted.",
            message_hi="केवल HTTP और HTTPS प्रोटोकॉल की अनुमति है।",
            details={"scheme": parsed.scheme},
        )

    if parsed.username or parsed.password:
        raise SecurityValidationError(
            status_code=400,
            error_code="CREDENTIALS_IN_URL_FORBIDDEN",
            message_en="URLs containing embedded credentials are forbidden.",
            message_hi="एम्बेडेड क्रेडेंशियल वाले URL प्रतिबंधित हैं।",
        )

    if parsed.port and parsed.port not in (80, 443):
        raise SecurityValidationError(
            status_code=400,
            error_code="NON_STANDARD_PORT_FORBIDDEN",
            message_en="Non-standard network ports are blocked by SSRF policy.",
            message_hi="SSRF नीति द्वारा गैर-मानक नेटवर्क पोर्ट अवरुद्ध हैं।",
            details={"port": parsed.port},
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SecurityValidationError(
            status_code=400,
            error_code="MISSING_HOSTNAME",
            message_en="URL is missing a valid hostname.",
            message_hi="URL में मान्य होस्टनाम अनुपस्थित है।",
        )

    verify_ssrf_safe_host(hostname)

    path = parsed.path or ""
    query_params = urllib.parse.parse_qs(parsed.query)

    video_id: Optional[str] = None
    url_type: str = "standard"

    if hostname in ("youtu.be", "www.youtu.be"):
        segments = [seg for seg in path.split("/") if seg]
        if segments:
            video_id = segments[0]
            url_type = "short_link"
    else:
        is_mobile = hostname == "m.youtube.com"
        if path == "/watch" or path.startswith("/watch/"):
            v_list = query_params.get("v", [])
            if v_list:
                video_id = v_list[0]
                url_type = "mobile" if is_mobile else "standard"
        elif path.startswith("/shorts/"):
            segments = [seg for seg in path.split("/") if seg]
            if len(segments) >= 2 and segments[0] == "shorts":
                video_id = segments[1]
                url_type = "shorts"
        elif path.startswith("/live/"):
            segments = [seg for seg in path.split("/") if seg]
            if len(segments) >= 2 and segments[0] == "live":
                video_id = segments[1]
                url_type = "live"

    if not video_id or not VIDEO_ID_REGEX.match(video_id):
        raise SecurityValidationError(
            status_code=400,
            error_code="INVALID_YOUTUBE_VIDEO_ID",
            message_en="Could not extract a valid 11-character YouTube Video ID from the URL. Supported formats: watch?v=, /shorts/, youtu.be/, m.youtube.com, and /live/.",
            message_hi="URL से मान्य 11-अक्षर का YouTube वीडियो ID निकाला नहीं जा सका। समर्थित प्रारूप: watch?v=, /shorts/, youtu.be/, m.youtube.com, और /live/।",
            details={"url": cleaned_url, "extracted_id": video_id},
        )

    canonical_url = (
        f"https://www.youtube.com/shorts/{video_id}"
        if url_type == "shorts"
        else f"https://www.youtube.com/watch?v={video_id}"
    )

    return {
        "video_id": video_id,
        "url_type": url_type,
        "original_url": cleaned_url,
        "canonical_url": canonical_url,
        "hostname": hostname,
    }


def sanitize_filename(title: str, video_id: str, quality_label: str, ext: str) -> str:
    """Creates a safe, cross-platform ASCII-compatible filename without path traversal risks."""
    cleaned_title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    cleaned_title = re.sub(r"[-\s]+", "_", cleaned_title)
    # Keep safe ASCII subset for reliable HTTP Content-Disposition header
    ascii_title = cleaned_title.encode("ascii", "ignore").decode("ascii").strip("_")
    if not ascii_title or len(ascii_title) < 2:
        ascii_title = f"StreamRip_{video_id}"
    ascii_title = ascii_title[:64]

    safe_quality = re.sub(r"[^a-zA-Z0-9_-]", "", quality_label)[:20]
    safe_ext = re.sub(r"[^a-z0-9]", "", ext.lower())[:6] or "mp4"

    return f"{ascii_title}_{video_id}_{safe_quality}.{safe_ext}"


class RateLimiter:
    """Sliding-window per-client rate limiter to protect backend processing resources."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.client_timestamps: Dict[str, List[float]] = {}

    def check_allowed(self, client_ip: str) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds
        history = self.client_timestamps.get(client_ip, [])
        history = [ts for ts in history if ts > window_start]

        if len(history) >= self.max_requests:
            retry_after = max(1, int(history[0] + self.window_seconds - now))
            self.client_timestamps[client_ip] = history
            return False, retry_after

        history.append(now)
        self.client_timestamps[client_ip] = history
        return True, 0
