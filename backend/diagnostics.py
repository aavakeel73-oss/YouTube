"""
StreamRip Pro — Structured HTTP Error Handling & YouTube HTTP 403 Diagnostics
Implements structured diagnostics for:
- HTTP 400 — Invalid Request
- HTTP 403 — Access Forbidden (with 6 distinct YouTube sub-classifications)
- HTTP 404 — Resource Not Found
- HTTP 408 — Request Timeout
- HTTP 429 — Rate Limited
- HTTP 500 — Server Error
- HTTP 502 — Upstream Failure
- HTTP 503 — Service Unavailable
"""

from typing import Any, Dict, Optional

HTTP_STATUS_CATALOG: Dict[int, Dict[str, str]] = {
    400: {
        "title_en": "HTTP 400 — Invalid Request",
        "title_hi": "HTTP 400 — अमान्य अनुरोध",
        "summary_en": "The submitted URL or parameter failed validation or violated allowlist rules.",
        "summary_hi": "सबमिट किया गया URL या पैरामीटर सत्यापन में विफल रहा या अनुमति-सूची नियमों का उल्लंघन किया।",
    },
    403: {
        "title_en": "HTTP 403 — Access Forbidden",
        "title_hi": "HTTP 403 — पहुंच प्रतिबंधित",
        "summary_en": "Upstream media access was denied due to source permissions, hosting network restrictions, or authentication requirements.",
        "summary_hi": "स्रोत अनुमतियों, होस्टिंग नेटवर्क प्रतिबंधों, या प्रमाणीकरण आवश्यकताओं के कारण अपस्ट्रीम मीडिया पहुंच अस्वीकार कर दी गई।",
    },
    404: {
        "title_en": "HTTP 404 — Resource Not Found",
        "title_hi": "HTTP 404 — संसाधन नहीं मिला",
        "summary_en": "The requested YouTube video, Short, or requested quality stream does not exist or has been removed.",
        "summary_hi": "अनुरोधित YouTube वीडियो, शॉर्ट, या गुणवत्ता स्ट्रीम मौजूद नहीं है या हटा दी गई है।",
    },
    408: {
        "title_en": "HTTP 408 — Request Timeout",
        "title_hi": "HTTP 408 — अनुरोध समय समाप्त",
        "summary_en": "Metadata extraction or FFmpeg media processing exceeded the maximum allowed execution window.",
        "summary_hi": "मेटाडेटा निष्कर्षण या FFmpeg मीडिया प्रोसेसिंग अधिकतम अनुमत निष्पादन समय से अधिक हो गई।",
    },
    429: {
        "title_en": "HTTP 429 — Rate Limited",
        "title_hi": "HTTP 429 — अनुरोध सीमा पार",
        "summary_en": "Too many requests were sent in a short window, or YouTube rate-limited the server IP.",
        "summary_hi": "कम समय में बहुत अधिक अनुरोध भेजे गए, या YouTube ने सर्वर IP को रेट-लिमिट कर दिया।",
    },
    500: {
        "title_en": "HTTP 500 — Server Error",
        "title_hi": "HTTP 500 — आंतरिक सर्वर त्रुटि",
        "summary_en": "An unexpected internal exception occurred inside the Python media pipeline.",
        "summary_hi": "Python मीडिया पाइपलाइन के भीतर एक अप्रत्याशित आंतरिक त्रुटि हुई।",
    },
    502: {
        "title_en": "HTTP 502 — Upstream Failure",
        "title_hi": "HTTP 502 — अपस्ट्रीम विफलता",
        "summary_en": "YouTube upstream servers returned an unreadable or truncated media response.",
        "summary_hi": "YouTube अपस्ट्रीम सर्वर ने अपठनीय या अधूरा मीडिया प्रतिसाद लौटाया।",
    },
    503: {
        "title_en": "HTTP 503 — Service Unavailable",
        "title_hi": "HTTP 503 — सेवा अनुपलब्ध",
        "summary_en": "Required media dependencies (FFmpeg, FFprobe, or yt-dlp) or temporary storage are unavailable.",
        "summary_hi": "आवश्यक मीडिया निर्भरताएँ (FFmpeg, FFprobe, या yt-dlp) या अस्थायी स्टोरेज अनुपलब्ध हैं।",
    },
}


YOUTUBE_403_SUBTYPES: Dict[str, Dict[str, Any]] = {
    "SOURCE_ACCESS_RESTRICTION": {
        "code": "YT_403_SOURCE_ACCESS_RESTRICTION",
        "label_en": "Source Access Restriction",
        "label_hi": "स्रोत पहुंच प्रतिबंध",
        "cause_en": "The video is private, members-only, rental-gated, or geographically restricted by the uploader or rightsholder.",
        "cause_hi": "वीडियो निजी है, केवल सदस्यों के लिए है, किराए पर है, या अपलोडर/अधिकार धारक द्वारा भौगोलिक रूप से प्रतिबंधित है।",
        "action_en": "Verify that the content is public and authorized for download in the server's region. Private or members-only streams cannot be downloaded without owner authorization.",
        "action_hi": "सत्यापित करें कि सामग्री सार्वजनिक है और सर्वर के क्षेत्र में डाउनलोड के लिए अधिकृत है।",
        "auto_fixable": False,
    },
    "EXPIRED_MEDIA_URL": {
        "code": "YT_403_EXPIRED_MEDIA_URL",
        "label_en": "Expired Media Stream URL",
        "label_hi": "समाप्त मीडिया स्ट्रीम URL",
        "cause_en": "Signed googlevideo.com stream URLs contain time-limited and IP-bound cryptographic tokens that expired before stream merging completed.",
        "cause_hi": "हस्ताक्षरित googlevideo.com स्ट्रीम URL में समय-सीमित टोकन होते हैं जो स्ट्रीम मर्जिंग पूरी होने से पहले समाप्त हो गए।",
        "action_en": "Re-analyze the video URL to obtain fresh manifest signatures and initiate the download immediately.",
        "action_hi": "नए मैनिफेस्ट हस्ताक्षर प्राप्त करने के लिए वीडियो URL का पुनः विश्लेषण करें और तुरंत डाउनलोड शुरू करें।",
        "auto_fixable": True,
    },
    "UNSUPPORTED_FORMAT": {
        "code": "YT_403_UNSUPPORTED_FORMAT",
        "label_en": "Unsupported or DRM-Protected Format",
        "label_hi": "असमर्थित या DRM-संरक्षित प्रारूप",
        "cause_en": "The stream utilizes Widevine/PlayReady DRM encryption or an unauthenticated SABR/DASH manifest format.",
        "cause_hi": "स्ट्रीम Widevine/PlayReady DRM एन्क्रिप्शन या अप्रमाणित SABR/DASH मैनिफेस्ट प्रारूप का उपयोग करती है।",
        "action_en": "StreamRip Pro strictly respects platform rules and does not bypass DRM encryption. Only unencrypted, authorized streams are supported.",
        "action_hi": "StreamRip Pro प्लेटफ़ॉर्म नियमों का सख्ती से पालन करता है और DRM एन्क्रिप्शन को बायपास नहीं करता है।",
        "auto_fixable": False,
    },
    "AUTHENTICATION_REQUIRED": {
        "code": "YT_403_AUTHENTICATION_REQUIRED",
        "label_en": "Authentication / Account Sign-In Required",
        "label_hi": "प्रमाणीकरण / खाता साइन-इन आवश्यक",
        "cause_en": "YouTube requested account verification (age confirmation or anti-abuse challenge) before serving media manifests.",
        "cause_hi": "YouTube ने मीडिया मैनिफेस्ट देने से पहले खाता सत्यापन (आयु पुष्टि या बॉट सुरक्षा) का अनुरोध किया।",
        "action_en": "This content requires an authenticated session or is restricted from anonymous automated extraction.",
        "action_hi": "इस सामग्री के लिए प्रमाणित सत्र की आवश्यकता है या यह अनाम स्वचालित निष्कर्षण से प्रतिबंधित है।",
        "auto_fixable": False,
    },
    "HOSTING_ENVIRONMENT_RESTRICTION": {
        "code": "YT_403_HOSTING_ENVIRONMENT_RESTRICTION",
        "label_en": "Hosting Environment / Cloud Datacenter IP Restriction",
        "label_hi": "होस्टिंग वातावरण / क्लाउड डेटासेंटर IP प्रतिबंध",
        "cause_en": "YouTube blocks or challenges anonymous media stream requests originating from shared cloud datacenter IP ranges (GCP Cloud Run, AWS, Railway, Render).",
        "cause_hi": "YouTube साझा क्लाउड डेटासेंटर IP रेंज (GCP Cloud Run, AWS, Railway, Render) से आने वाले अनाम मीडिया स्ट्रीम अनुरोधों को अवरुद्ध करता है।",
        "action_en": "Deploy the container on a dedicated self-hosted environment for live YouTube extraction, or use the Authorized Reference Stream FFmpeg Pipeline in Cloud Sandbox mode.",
        "action_hi": "लाइव YouTube निष्कर्षण के लिए समर्पित सेल्फ-होस्टेड वातावरण में कंटेनर तैनात करें, या क्लाउड सैंडबॉक्स मोड में अधिकृत रेफरेंस स्ट्रीम FFmpeg पाइपलाइन का उपयोग करें।",
        "auto_fixable": False,
    },
    "BACKEND_IMPLEMENTATION_ERROR": {
        "code": "YT_403_BACKEND_IMPLEMENTATION_ERROR",
        "label_en": "Backend Extractor or Header Mismatch",
        "label_hi": "बैकएंड एक्सट्रैक्टर या हेडर त्रुटि",
        "cause_en": "The local yt-dlp binary version is outdated relative to recent YouTube player changes, or stream transport headers were rejected.",
        "cause_hi": "हाल के YouTube प्लेयर परिवर्तनों की तुलना में स्थानीय yt-dlp बाइनरी संस्करण पुराना है।",
        "action_en": "Update the yt-dlp binary inside the deployment container (`yt-dlp -U`) and verify FFmpeg transport flags.",
        "action_hi": "डिप्लॉयमेंट कंटेनर के भीतर yt-dlp बाइनरी को अपडेट करें (`yt-dlp -U`)।",
        "auto_fixable": False,
    },
}


def classify_yt_dlp_error(raw_stderr: str) -> Dict[str, Any]:
    """
    Inspects raw stderr from yt-dlp or FFmpeg and classifies it accurately into HTTP status codes
    and the 6 YouTube HTTP 403 sub-classifications where applicable.
    """
    err_lower = (raw_stderr or "").lower()

    if "sign in to confirm you’re not a bot" in err_lower or "sign in to confirm you're not a bot" in err_lower or "not a bot" in err_lower:
        sub = YOUTUBE_403_SUBTYPES["HOSTING_ENVIRONMENT_RESTRICTION"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="HOSTING_ENVIRONMENT_RESTRICTION",
            raw_error=raw_stderr.strip(),
        )

    if "private video" in err_lower or "members-only" in err_lower or "not available in your country" in err_lower or "uploader has not made this video available" in err_lower:
        sub = YOUTUBE_403_SUBTYPES["SOURCE_ACCESS_RESTRICTION"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="SOURCE_ACCESS_RESTRICTION",
            raw_error=raw_stderr.strip(),
        )

    if "sign in to confirm your age" in err_lower or "age-restricted" in err_lower or "login required" in err_lower:
        sub = YOUTUBE_403_SUBTYPES["AUTHENTICATION_REQUIRED"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="AUTHENTICATION_REQUIRED",
            raw_error=raw_stderr.strip(),
        )

    if "drm" in err_lower or "widevine" in err_lower or "unplayable" in err_lower:
        sub = YOUTUBE_403_SUBTYPES["UNSUPPORTED_FORMAT"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="UNSUPPORTED_FORMAT",
            raw_error=raw_stderr.strip(),
        )

    if "http error 403" in err_lower and ("expired" in err_lower or "googlevideo" in err_lower):
        sub = YOUTUBE_403_SUBTYPES["EXPIRED_MEDIA_URL"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="EXPIRED_MEDIA_URL",
            raw_error=raw_stderr.strip(),
        )

    if "http error 403" in err_lower or "forbidden" in err_lower:
        sub = YOUTUBE_403_SUBTYPES["BACKEND_IMPLEMENTATION_ERROR"]
        return build_diagnostic_response(
            status_code=403,
            error_code=sub["code"],
            subtype_key="BACKEND_IMPLEMENTATION_ERROR",
            raw_error=raw_stderr.strip(),
        )

    if "video unavailable" in err_lower or "http error 404" in err_lower or "not found" in err_lower or "incomplete youtube id" in err_lower:
        return build_diagnostic_response(
            status_code=404,
            error_code="VIDEO_OR_RESOURCE_NOT_FOUND",
            raw_error=raw_stderr.strip(),
        )

    if "http error 429" in err_lower or "too many requests" in err_lower:
        return build_diagnostic_response(
            status_code=429,
            error_code="UPSTREAM_RATE_LIMITED",
            raw_error=raw_stderr.strip(),
        )

    if "timed out" in err_lower or "timeout" in err_lower:
        return build_diagnostic_response(
            status_code=408,
            error_code="EXTRACTION_TIMEOUT",
            raw_error=raw_stderr.strip(),
        )

    return build_diagnostic_response(
        status_code=502,
        error_code="UPSTREAM_EXTRACTION_FAILURE",
        raw_error=raw_stderr.strip(),
    )


def build_diagnostic_response(
    status_code: int,
    error_code: str,
    subtype_key: Optional[str] = None,
    custom_message_en: Optional[str] = None,
    custom_message_hi: Optional[str] = None,
    raw_error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = HTTP_STATUS_CATALOG.get(status_code, HTTP_STATUS_CATALOG[500])
    subtype = YOUTUBE_403_SUBTYPES.get(subtype_key) if subtype_key else None

    payload: Dict[str, Any] = {
        "http_status": status_code,
        "error_code": error_code,
        "title_en": base["title_en"],
        "title_hi": base["title_hi"],
        "message_en": custom_message_en or (subtype["cause_en"] if subtype else base["summary_en"]),
        "message_hi": custom_message_hi or (subtype["cause_hi"] if subtype else base["summary_hi"]),
        "action_en": subtype["action_en"] if subtype else "Check URL validity, network connectivity, or try an authorized reference stream.",
        "action_hi": subtype["action_hi"] if subtype else "URL की वैधता, नेटवर्क कनेक्टिविटी की जांच करें, या अधिकृत रेफरेंस स्ट्रीम का प्रयास करें।",
        "http_403_classification": {
            "subtype": subtype_key,
            "label_en": subtype["label_en"],
            "label_hi": subtype["label_hi"],
            "cause_en": subtype["cause_en"],
            "cause_hi": subtype["cause_hi"],
            "action_en": subtype["action_en"],
            "action_hi": subtype["action_hi"],
            "auto_fixable": subtype["auto_fixable"],
        }
        if subtype
        else None,
        "all_403_categories_reference": list(YOUTUBE_403_SUBTYPES.keys()) if status_code == 403 else None,
        "raw_diagnostic": (raw_error or "")[:600],
    }
    if extra:
        payload.update(extra)
    return payload
