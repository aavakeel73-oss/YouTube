/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  AudioLines,
  CheckCircle2,
  Clipboard,
  ClipboardCheck,
  Cloud,
  Code2,
  Cpu,
  Download,
  ExternalLink,
  FileAudio,
  FileVideo,
  FolderGit2,
  Globe,
  HardDrive,
  Key,
  Loader2,
  RefreshCw,
  Search,
  Server,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Trash2,
  Video,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { Language, TRANSLATIONS } from './i18n';

interface QualityOption {
  id: string;
  label: string;
  resolution: string;
  width: number;
  height: number;
  container: string;
  video_codec: string;
  audio_codec: string;
  requires_ffmpeg_merge: boolean;
  available: boolean;
  estimated_size_bytes: number | null;
  estimated_size_mb: number | null;
  is_estimated?: boolean;
  is_exact?: boolean;
  size_display_hi?: string | null;
  size_display_en?: string | null;
  unavailable_reason_en: string | null;
  unavailable_reason_hi: string | null;
}

interface AudioBitrateOption {
  bitrate: string;
  estimated_size_bytes: number;
  estimated_size_mb: number;
  is_estimated?: boolean;
  is_exact?: boolean;
  size_display_hi?: string;
  size_display_en?: string;
}

interface AudioFormatOption {
  id: string;
  label: string;
  ext: string;
  codec: string;
  default_bitrate: string;
  bitrates: AudioBitrateOption[];
  available: boolean;
}

interface YtDlpDiagnosticNotice {
  http_status: number;
  subtype: string;
  label_en: string;
  label_hi: string;
  explanation_en: string;
  explanation_hi: string;
  raw_stderr: string;
}

interface AnalysisResult {
  video_id: string;
  url_type: string;
  canonical_url: string;
  title: string;
  channel: string;
  duration_seconds: number;
  duration_formatted: string;
  thumbnail: string;
  license_note?: string;
  extraction_mode: string;
  yt_dlp_diagnostic: YtDlpDiagnosticNotice | null;
  qualities: QualityOption[];
  audio_formats: AudioFormatOption[];
  analysis_time_ms: number;
}

interface DiagnosticErrorPayload {
  http_status: number;
  error_code: string;
  title_en: string;
  title_hi: string;
  message_en: string;
  message_hi: string;
  action_en: string;
  action_hi: string;
  http_403_classification?: {
    subtype: string;
    label_en: string;
    label_hi: string;
    cause_en: string;
    cause_hi: string;
    action_en: string;
    action_hi: string;
    auto_fixable: boolean;
  } | null;
  raw_diagnostic?: string;
}

interface FFprobeValidationReport {
  integrity_verified: boolean;
  av_sync_verified?: boolean;
  av_sync_drift_sec?: number;
  format_name: string;
  duration_sec: number;
  size_bytes: number;
  size_mb?: number;
  bit_rate_bps: number;
  stream_count: number;
  video_codec: string | null;
  video_resolution: string | null;
  audio_codec: string | null;
  audio_sample_rate: string | null;
  audio_channels?: number | null;
  is_complete?: boolean;
}

interface MediaJob {
  job_id: string;
  video_id: string;
  title: string;
  channel: string;
  mode: 'video' | 'audio';
  quality_id: string;
  resolution: string;
  duration_seconds?: number;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  stage: string;
  stage_label_en: string;
  stage_label_hi: string;
  progress: number;
  processing_time_ms: number | null;
  file_size_bytes: number | null;
  actual_size_bytes?: number | null;
  actual_size_mb?: number | null;
  estimated_size_bytes?: number | null;
  estimated_size_mb?: number | null;
  target_size_bytes?: number | null;
  direct_download_url?: string | null;
  ffprobe_validation: FFprobeValidationReport | null;
  error: DiagnosticErrorPayload | null;
  inline_blob_data?: {
    job_id: string;
    filename: string;
    mime_type: string;
    size_bytes: number;
    base_stream_bytes: number;
    target_size_bytes: number;
    container_ext: string;
    base64_data: string;
  };
}

interface QaTestResultItem {
  id: string;
  name_en: string;
  name_hi: string;
  input: string;
  expected: string;
  actual: string;
  passed: boolean;
}

interface QaSuiteReport {
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  all_passed: boolean;
  executed_at: number;
  results: QaTestResultItem[];
}

interface AdminMetricsData {
  status: string;
  uptime_seconds: number;
  total_requests: number;
  analyze_requests: number;
  successful_downloads: number;
  failed_requests: number;
  average_processing_time_ms: number;
  binaries: {
    ffmpeg_available: boolean;
    ffprobe_available: boolean;
    yt_dlp_available: boolean;
    ffmpeg_version: string | null;
    ffprobe_version: string | null;
    yt_dlp_version: string | null;
  };
  storage: {
    directory: string;
    used_bytes: number;
    used_mb: number;
    max_mb: number;
    utilization_percent: number;
    active_files: number;
  };
  error_categories: Record<string, number>;
  http_403_subcategories: Record<string, number>;
  recent_jobs: Array<{
    job_id: string;
    video_id: string;
    title: string;
    mode: string;
    quality: string;
    resolution: string;
    status: string;
    processing_time_ms: number | null;
    file_size_bytes: number | null;
    integrity_verified: boolean;
  }>;
}

interface DeliverableFile {
  path: string;
  category: string;
  description: string;
  sizeBytes: number;
  lines: number;
  content: string;
}

const DIAGNOSTIC_TRIGGERS = [
  { id: 'SOURCE_ACCESS_RESTRICTION', label: 'HTTP 403 · Source Access Restriction (Private/Geo)' },
  { id: 'EXPIRED_MEDIA_URL', label: 'HTTP 403 · Expired Signed Media URL' },
  { id: 'UNSUPPORTED_FORMAT', label: 'HTTP 403 · Unsupported / DRM Format' },
  { id: 'AUTHENTICATION_REQUIRED', label: 'HTTP 403 · Authentication / Age Gate Required' },
  { id: 'HOSTING_ENVIRONMENT_RESTRICTION', label: 'HTTP 403 · Cloud Hosting Datacenter IP Block' },
  { id: 'BACKEND_IMPLEMENTATION_ERROR', label: 'HTTP 403 · Backend Extractor / Header Mismatch' },
  { id: 'HTTP_400', label: 'HTTP 400 · Invalid Request / SSRF Block' },
  { id: 'HTTP_404', label: 'HTTP 404 · Video or Stream Not Found' },
  { id: 'HTTP_408', label: 'HTTP 408 · Extraction / FFmpeg Timeout' },
  { id: 'HTTP_429', label: 'HTTP 429 · Rate Limited' },
  { id: 'HTTP_500', label: 'HTTP 500 · Internal Pipeline Error' },
  { id: 'HTTP_502', label: 'HTTP 502 · Upstream Manifest Failure' },
  { id: 'HTTP_503', label: 'HTTP 503 · Service / Binary Unavailable' },
];

type ActiveTab = 'workspace' | 'diagnostics' | 'qa' | 'admin' | 'deploy';

function isHtmlInterceptionBuffer(buffer: ArrayBuffer): boolean {
  const headerBytes = new Uint8Array(buffer.slice(0, 64));
  const textSample = new TextDecoder('utf-8', { fatal: false })
    .decode(headerBytes)
    .trim()
    .toLowerCase();
  return (
    textSample.startsWith('<!doctype') ||
    textSample.startsWith('<html') ||
    textSample.includes('cookie check') ||
    textSample.includes('action required')
  );
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = window.atob(base64);
  const len = binaryString.length;
  const buffer = new ArrayBuffer(len);
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return buffer;
}

function scheduleRevokeObjectUrl(url: string | null) {
  if (!url || !url.startsWith('blob:')) return;
  window.setTimeout(() => {
    try {
      URL.revokeObjectURL(url);
    } catch {
      // Ignore revoke error
    }
  }, 300000);
}

function looksLikeCompleteYouTubeUrl(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed) return false;
  return /^(https?:\/\/)?((www|m|music)\.)?(youtube\.com\/(watch\?.*v=|shorts\/|live\/|embed\/)|youtu\.be\/)[A-Za-z0-9_-]{11}([?&/#].*)?$/i.test(
    trimmed
  );
}

export default function App() {
  const [lang, setLang] = useState<Language>('hi');
  const t = TRANSLATIONS[lang];

  const [activeTab, setActiveTab] = useState<ActiveTab>('workspace');
  const [urlInput, setUrlInput] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [errorDiag, setErrorDiag] = useState<DiagnosticErrorPayload | null>(null);
  const lastAutoAnalyzedUrlRef = useRef<string>('');

  // Media Download Selection State
  const [mediaMode, setMediaMode] = useState<'video' | 'audio'>('video');
  const [selectedQuality, setSelectedQuality] = useState<string>('480p');
  const [selectedAudioFormat, setSelectedAudioFormat] = useState<string>('mp3');
  const [selectedAudioBitrate, setSelectedAudioBitrate] = useState<string>('192k');

  // Active FFmpeg Processing Job & Verified Contiguous Stream State (Android Chrome Safe)
  const [activeJob, setActiveJob] = useState<MediaJob | null>(null);
  const [downloadingQualityId, setDownloadingQualityId] = useState<string | null>(null);
  const [isStartingJob, setIsStartingJob] = useState<boolean>(false);
  const [verifiedBlobUrl, setVerifiedBlobUrl] = useState<string | null>(null);
  const [verifiedMediaFile, setVerifiedMediaFile] = useState<File | null>(null);
  const [isFetchingBlob, setIsFetchingBlob] = useState<boolean>(false);
  const [downloadProgress, setDownloadProgress] = useState<number>(0);
  const [downloadSpeedMbps, setDownloadSpeedMbps] = useState<number>(90.0);
  const pollTimerRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Diagnostics Lab State
  const [labDiagResult, setLabDiagResult] = useState<DiagnosticErrorPayload | null>(null);
  const [isTestingDiag, setIsTestingDiag] = useState<boolean>(false);

  // QA Verification Suite State
  const [qaReport, setQaReport] = useState<QaSuiteReport | null>(null);
  const [isRunningQa, setIsRunningQa] = useState<boolean>(false);

  // Admin Monitor State
  const [adminData, setAdminData] = useState<AdminMetricsData | null>(null);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState<boolean>(false);

  // Deliverables & Deployment Inspector State
  const [deliverables, setDeliverables] = useState<DeliverableFile[]>([]);
  const [selectedFilePath, setSelectedFilePath] = useState<string>('backend/media_engine.py');
  const [selectedCloudGuide, setSelectedCloudGuide] = useState<'cloudrun' | 'railway' | 'render' | 'vps'>('cloudrun');

  // Cookie Manager Modal State
  const [showCookieModal, setShowCookieModal] = useState<boolean>(false);
  const [cookieInput, setCookieInput] = useState<string>('');
  const [hasCookies, setHasCookies] = useState<boolean>(false);
  const [isSavingCookies, setIsSavingCookies] = useState<boolean>(false);

  useEffect(() => {
    fetch('/api/cookies', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d && d.has_cookies) setHasCookies(true);
      })
      .catch(() => {});
  }, []);

  async function handleSaveCookies() {
    if (!cookieInput.trim()) return;
    setIsSavingCookies(true);
    try {
      const res = await fetch('/api/cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ cookies_text: cookieInput }),
      });
      if (res.ok) {
        setHasCookies(true);
        setShowCookieModal(false);
        setCookieInput('');
        if (urlInput.trim()) handleAnalyzeUrl(urlInput.trim());
      }
    } finally {
      setIsSavingCookies(false);
    }
  }

  async function handleClearCookies() {
    await fetch('/api/cookies/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    setHasCookies(false);
  }

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
      if (verifiedBlobUrl && verifiedBlobUrl.startsWith('blob:')) {
        URL.revokeObjectURL(verifiedBlobUrl);
      }
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'admin') {
      fetchAdminMetrics();
    } else if (activeTab === 'deploy' && deliverables.length === 0) {
      fetchDeliverables();
    } else if (activeTab === 'qa' && !qaReport && !isRunningQa) {
      handleRunQaSuite();
    }
  }, [activeTab]);

  async function handlePasteClipboard() {
    try {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        const cleaned = text.trim();
        setUrlInput(cleaned);
        await handleAnalyzeUrl(cleaned);
      }
    } catch {
      // Clipboard permission unavailable
    }
  }

  async function handleAnalyzeUrl(targetUrl: string): Promise<AnalysisResult | null> {
    const cleaned = targetUrl.trim();
    if (!cleaned) {
      setErrorDiag({
        http_status: 400,
        error_code: 'EMPTY_URL',
        title_en: 'HTTP 400 — Please Paste a YouTube Link',
        title_hi: 'कृपया पहले ऊपर बॉक्स में YouTube लिंक पेस्ट करें',
        message_en: 'Paste a valid YouTube Video, Shorts, or youtu.be URL above to download.',
        message_hi: 'डाउनलोड करने के लिए ऊपर बॉक्स में YouTube वीडियो या शॉर्ट्स का लिंक पेस्ट करें।',
        action_en: 'Paste a YouTube URL.',
        action_hi: 'YouTube लिंक पेस्ट करें।',
      });
      return null;
    }

    lastAutoAnalyzedUrlRef.current = cleaned;
    setIsAnalyzing(true);
    setErrorDiag(null);
    setActiveJob(null);
    setDownloadProgress(0);
    if (verifiedBlobUrl) {
      scheduleRevokeObjectUrl(verifiedBlobUrl);
      setVerifiedBlobUrl(null);
      setVerifiedMediaFile(null);
    }

    try {
      let lastRes: Response | null = null;
      let lastData: unknown = null;
      let lastErr: unknown = null;

      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const res = await fetch('/api/analyze', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: cleaned,
              strict_live_only: false,
            }),
          });
          lastRes = res;
          lastData = await res.json();
          if (res.status !== 502 && res.status !== 503) {
            break;
          }
        } catch (err) {
          lastErr = err;
        }
        await new Promise((r) => window.setTimeout(r, 600));
      }

      if (!lastRes) {
        throw lastErr || new Error('Backend server unreachable');
      }

      if (!lastRes.ok) {
        setAnalysis(null);
        setErrorDiag(lastData as DiagnosticErrorPayload);
        return null;
      }

      const result = lastData as AnalysisResult;
      setAnalysis(result);

      const availQualities = result.qualities.filter((q) => q.available);
      if (availQualities.length > 0) {
        const currentStillValid = availQualities.some((q) => q.id === selectedQuality);
        if (!currentStillValid) {
          const preferred =
            availQualities.find((q) => q.id === '480p') ||
            availQualities.find((q) => q.id === '720p') ||
            availQualities[0];
          setSelectedQuality(preferred.id);
        }
      }
      return result;
    } catch (err) {
      setAnalysis(null);
      setErrorDiag({
        http_status: 503,
        error_code: 'NETWORK_OR_GATEWAY_ERROR',
        title_en: 'HTTP 503 — Backend Connection Error',
        title_hi: 'HTTP 503 — बैकएंड कनेक्शन त्रुटि',
        message_en: String(err),
        message_hi: 'बैकएंड सर्वर से संपर्क करने में विफल।',
        action_en: 'Verify that the Python media engine is running.',
        action_hi: 'सत्यापित करें कि Python मीडिया इंजन चल रहा है।',
      });
      return null;
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function verifyBlobAndObjectUrl(blob: Blob, objectUrl: string): Promise<boolean> {
    try {
      if (blob.size <= 0) return false;
      const headBuf = await blob.slice(0, Math.min(64, blob.size)).arrayBuffer();
      if (headBuf.byteLength === 0 || isHtmlInterceptionBuffer(headBuf)) return false;
      return true;
    } catch {
      return false;
    }
  }

  async function finalizeContiguousBlobAndTrigger(
    job: MediaJob,
    blob: Blob,
    mimeType: string
  ): Promise<string | null> {
    const objectUrl = URL.createObjectURL(blob);
    const verified = await verifyBlobAndObjectUrl(blob, objectUrl);
    if (!verified) {
      URL.revokeObjectURL(objectUrl);
      setErrorDiag({
        http_status: 500,
        error_code: 'BLOB_VERIFICATION_FAILED',
        title_en: 'HTTP 500 — Media Stream Verification Failed',
        title_hi: 'HTTP 500 — मीडिया फ़ाइल सत्यापन विफल',
        message_en: 'The downloaded media stream could not be verified in browser memory.',
        message_hi: 'ब्राउज़र मेमोरी में डाउनलोड की गई मीडिया फ़ाइल सत्यापित नहीं हो सकी।',
        action_en: 'Tap Download to retry.',
        action_hi: 'कृपया दोबारा डाउनलोड बटन दबाएं।',
      });
      return null;
    }

    setVerifiedBlobUrl(objectUrl);
    setActiveJob((prev) =>
      prev && prev.job_id === job.job_id ? {
        ...prev,
        file_size_bytes: prev.file_size_bytes || blob.size,
      } : prev
    );
    if (blob.size <= 25 * 1024 * 1024) {
      setVerifiedMediaFile(new File([blob], job.filename, { type: mimeType }));
    } else {
      setVerifiedMediaFile(null);
    }
    setDownloadProgress(100);
    triggerBrowserDownload(objectUrl, job.filename);
    return objectUrl;
  }

  /**
   * Streams and triggers authenticated native download for the completed media file.
   * - Streams full binary media chunks inside the authenticated browser/iframe session.
   * - Never delegates raw server URLs to Android OS DownloadManager over the network (which triggers 'Cookie check' HTML interception).
   * - Constructs a local in-memory Blob and blob: URL, written directly to device storage by Chrome.
   * - Prepares File object for Android native Web Share API (Save to Gallery / WhatsApp / Files).
   */
  function handleCancelDownloadJob() {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort();
      } catch {
        // Ignore abort errors
      }
      abortControllerRef.current = null;
    }
    setIsStartingJob(false);
    setIsFetchingBlob(false);
    setDownloadingQualityId(null);
    setDownloadProgress(0);
    setActiveJob(null);
  }

  async function fetchVerifiedMediaBlob(job: MediaJob): Promise<string | null> {
    setIsFetchingBlob(true);
    setDownloadProgress(75);
    setDownloadSpeedMbps(90.0);
    const defaultMime = job.filename.endsWith('.mp4')
      ? 'video/mp4'
      : job.filename.endsWith('.m4a')
      ? 'audio/mp4'
      : 'audio/mpeg';

    const directDownloadUrl = `/api/download/${job.job_id}`;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const startTime = performance.now();

    try {
      let totalBytes =
        Number(job.file_size_bytes) ||
        Number(job.actual_size_bytes) ||
        Number(job.ffprobe_validation?.size_bytes) ||
        0;

      // Probe exact byte length via HEAD if not already known
      if (totalBytes <= 0) {
        const headRes = await fetch(directDownloadUrl, {
          method: 'HEAD',
          credentials: 'include',
          signal: controller.signal,
        });
        if (headRes.ok) {
          totalBytes =
            Number(headRes.headers.get('x-streamrip-verified-bytes')) ||
            Number(headRes.headers.get('content-length')) ||
            0;
        }
      }

      const chunks: BlobPart[] = [];
      let receivedBytes = 0;
      const CHUNK_SIZE = 8 * 1024 * 1024; // 8 MB per Range request (bypasses 25-32 MB cloud proxy cap)

      if (totalBytes > 0) {
        while (receivedBytes < totalBytes) {
          const endByte = Math.min(receivedBytes + CHUNK_SIZE - 1, totalBytes - 1);
          let chunkSuccess = false;
          let lastChunkErr: unknown = null;

          for (let retry = 0; retry < 5; retry++) {
            try {
              const rangeRes = await fetch(directDownloadUrl, {
                method: 'GET',
                credentials: 'include',
                signal: controller.signal,
                headers: {
                  Range: `bytes=${receivedBytes}-${endByte}`,
                },
              });

              if (!rangeRes.ok && rangeRes.status !== 206 && rangeRes.status !== 200) {
                try {
                  const errPayload = await rangeRes.json();
                  if (errPayload && errPayload.error_code) {
                    setErrorDiag(errPayload as DiagnosticErrorPayload);
                    return null;
                  }
                } catch {}
                throw new Error(`HTTP ${rangeRes.status} during chunk transfer`);
              }

              const cType = (rangeRes.headers.get('content-type') || '').toLowerCase();
              if (cType.includes('text/html') || cType.includes('application/json')) {
                throw new Error('Received HTML/JSON instead of binary media chunk');
              }

              const buf = await rangeRes.arrayBuffer();
              if (buf.byteLength === 0) {
                throw new Error('Empty media chunk received from server');
              }

              if (receivedBytes === 0 && isHtmlInterceptionBuffer(buf)) {
                throw new Error('Received HTML interception page instead of media binary');
              }

              // If server returned 200 full body instead of 206 range on small files, accept full body
              if (rangeRes.status === 200 && receivedBytes === 0 && buf.byteLength >= totalBytes) {
                chunks.push(new Uint8Array(buf));
                receivedBytes = buf.byteLength;
                chunkSuccess = true;
                break;
              }

              chunks.push(new Uint8Array(buf));
              receivedBytes += buf.byteLength;
              chunkSuccess = true;

              const elapsedSec = Math.max(0.05, (performance.now() - startTime) / 1000);
              const measuredMbps = receivedBytes / (1024 * 1024) / elapsedSec;
              setDownloadSpeedMbps(
                measuredMbps >= 0.5 ? Math.min(99.9, Number(measuredMbps.toFixed(1))) : 90.0
              );
              const pct = Math.min(99, Math.max(75, 75 + Math.floor((receivedBytes / totalBytes) * 24)));
              setDownloadProgress(pct);
              break;
            } catch (chunkErr) {
              if ((chunkErr as Error)?.name === 'AbortError') {
                throw chunkErr;
              }
              lastChunkErr = chunkErr;
              await new Promise((r) => window.setTimeout(r, 500 * (retry + 1)));
            }
          }

          if (!chunkSuccess) {
            throw lastChunkErr || new Error('Failed to transfer complete media stream after retries');
          }
        }
      } else {
        // Fallback stream reader when totalBytes is unknown beforehand
        const res = await fetch(directDownloadUrl, {
          method: 'GET',
          credentials: 'include',
          signal: controller.signal,
        });
        if (!res.ok) {
          throw new Error(`Media stream returned HTTP ${res.status}`);
        }
        const buf = await res.arrayBuffer();
        if (buf.byteLength === 0 || isHtmlInterceptionBuffer(buf)) {
          throw new Error('Invalid or empty media stream');
        }
        chunks.push(new Uint8Array(buf));
        receivedBytes = buf.byteLength;
        totalBytes = receivedBytes;
      }

      // Strict Completeness Verification: never save an incomplete/truncated file!
      if (totalBytes > 0 && receivedBytes < totalBytes) {
        const recMb = (receivedBytes / (1024 * 1024)).toFixed(2);
        const totMb = (totalBytes / (1024 * 1024)).toFixed(2);
        setErrorDiag({
          http_status: 502,
          error_code: 'INCOMPLETE_DOWNLOAD_ABORTED',
          title_en: 'Incomplete Video Transfer Detected',
          title_hi: 'अधूरा वीडियो डाउनलोड रोका गया',
          message_en: `Only ${recMb} MB of ${totMb} MB was received. Incomplete file was rejected so corrupt media is not saved.`,
          message_hi: `कुल ${totMb} MB में से केवल ${recMb} MB प्राप्त हुआ। अधूरी फ़ाइल को सेव होने से रोक दिया गया है। कृपया पुनः प्रयास करें।`,
          action_en: 'Tap quality button to retry.',
          action_hi: 'दोबारा डाउनलोड करने के लिए क्वालिटी बटन दबाएं।',
        });
        return null;
      }

      setDownloadProgress(100);

      // Assemble complete binary Blob & create local blob: URL (100% Android Chrome safe)
      const finalBlob = new Blob(chunks, { type: defaultMime });
      const objectUrl = URL.createObjectURL(finalBlob);

      setVerifiedBlobUrl(objectUrl);
      setActiveJob((prev) =>
        prev && prev.job_id === job.job_id
          ? {
              ...prev,
              file_size_bytes: finalBlob.size,
              actual_size_bytes: finalBlob.size,
            }
          : prev
      );

      // Only allocate duplicate File object for Web Share if <= 25 MB to preserve mobile RAM
      if (finalBlob.size <= 25 * 1024 * 1024) {
        setVerifiedMediaFile(new File([finalBlob], job.filename, { type: defaultMime }));
      } else {
        setVerifiedMediaFile(null);
      }

      setErrorDiag(null);
      triggerBrowserDownload(objectUrl, job.filename);

      return objectUrl;
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        return null;
      }
      setErrorDiag({
        http_status: 502,
        error_code: 'STREAM_TRANSFER_INTERRUPTED',
        title_en: 'Download Stream Interrupted',
        title_hi: 'डाउनलोड के दौरान नेटवर्क बाधित हुआ',
        message_en: `Full video download could not be completed (${String(err)}). Please tap the quality button to retry.`,
        message_hi: `पूरा वीडियो डाउनलोड नहीं हो सका (${String(err)})। अधूरी फ़ाइल सेव नहीं की गई है। कृपया दोबारा प्रयास करें।`,
        action_en: 'Retry download.',
        action_hi: 'दोबारा प्रयास करें।',
      });
      return null;
    } finally {
      setIsFetchingBlob(false);
    }
  }

  /**
   * Starts a download job for the exact YouTube URL currently pasted in urlInput.
   */
  async function handleStartDownloadJob(
    overrideMode?: 'video' | 'audio',
    overrideQualityId?: string,
    overrideAudioFmt?: string,
    overrideAudioBr?: string
  ) {
    const pastedUrl = urlInput.trim();
    if (!pastedUrl) {
      setErrorDiag({
        http_status: 400,
        error_code: 'EMPTY_URL',
        title_en: 'HTTP 400 — Please Paste a YouTube Link',
        title_hi: 'कृपया पहले ऊपर बॉक्स में YouTube लिंक पेस्ट करें',
        message_en: 'Paste a YouTube Video, Shorts, or youtu.be URL in the box above and tap Download.',
        message_hi: 'कृपया ऊपर दिए गए बॉक्स में अपना YouTube लिंक पेस्ट करें और फिर डाउनलोड बटन दबाएं।',
        action_en: 'Paste a YouTube URL.',
        action_hi: 'YouTube लिंक पेस्ट करें।',
      });
      return;
    }

    const targetMode = overrideMode || mediaMode;
    const targetQuality = overrideQualityId || selectedQuality;
    const targetAudioFmt = overrideAudioFmt || selectedAudioFormat;
    const targetAudioBr = overrideAudioBr || selectedAudioBitrate;

    if (overrideQualityId) setSelectedQuality(overrideQualityId);
    if (overrideMode) setMediaMode(overrideMode);
    if (overrideAudioFmt) setSelectedAudioFormat(overrideAudioFmt);
    if (overrideAudioBr) setSelectedAudioBitrate(overrideAudioBr);
    setDownloadingQualityId(targetMode === 'video' ? targetQuality : targetAudioFmt);
    setDownloadProgress(10);
    setDownloadSpeedMbps(90.0);

    if (verifiedBlobUrl) {
      scheduleRevokeObjectUrl(verifiedBlobUrl);
      setVerifiedBlobUrl(null);
      setVerifiedMediaFile(null);
    }

    setIsStartingJob(true);
    setErrorDiag(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          url: pastedUrl,
          mode: targetMode,
          quality_id: targetQuality,
          audio_format: targetAudioFmt,
          audio_bitrate: targetAudioBr,
          inline_blob: false,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorDiag(data as DiagnosticErrorPayload);
        setIsStartingJob(false);
        setDownloadingQualityId(null);
        return;
      }

      const job = data as MediaJob;
      setActiveJob(job);
      setIsStartingJob(false);
      setDownloadProgress(Math.max(15, Math.min(74, Math.floor((job.progress || 20) * 0.75))));

      if (job.status === 'completed') {
        await fetchVerifiedMediaBlob(job);
        setDownloadingQualityId(null);
        return;
      }
      if (job.status === 'failed') {
        setDownloadingQualityId(null);
        if (job.error) setErrorDiag(job.error);
        return;
      }

      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = window.setInterval(async () => {
        try {
          const pollRes = await fetch(`/api/jobs/${job.job_id}`, {
            credentials: 'include',
          });
          if (!pollRes.ok) return;
          const updatedJob = (await pollRes.json()) as MediaJob;
          setActiveJob(updatedJob);
          if (typeof updatedJob.progress === 'number') {
            setDownloadProgress(Math.min(74, Math.max(15, Math.floor(updatedJob.progress * 0.75))));
          }

          if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
            if (pollTimerRef.current) {
              window.clearInterval(pollTimerRef.current);
              pollTimerRef.current = null;
            }
            if (updatedJob.status === 'completed') {
              await fetchVerifiedMediaBlob(updatedJob);
              setDownloadingQualityId(null);
            } else {
              setDownloadingQualityId(null);
              if (updatedJob.error) {
                setErrorDiag(updatedJob.error);
              }
            }
          }
        } catch {
          // Ignore transient poll errors
        }
      }, 400);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        return;
      }
      setIsStartingJob(false);
      setDownloadingQualityId(null);
      setErrorDiag({
        http_status: 500,
        error_code: 'JOB_INIT_ERROR',
        title_en: 'HTTP 500 — Failed to Start Media Job',
        title_hi: 'HTTP 500 — मीडिया जॉब शुरू करने में विफल',
        message_en: String(err),
        message_hi: 'मीडिया प्रोसेसिंग जॉब शुरू नहीं हो सका।',
        action_en: 'Retry the download request.',
        action_hi: 'डाउनलोड अनुरोध पुनः प्रयास करें।',
      });
    }
  }

  function triggerBrowserDownload(blobOrDataUrl: string, filename: string) {
    const a = document.createElement('a');
    a.href = blobOrDataUrl;
    a.download = filename;
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    window.setTimeout(() => {
      if (a.parentNode) {
        document.body.removeChild(a);
      }
    }, 5000);
  }

  async function handleShareFileAndroid() {
    if (!verifiedMediaFile || !navigator.canShare) return;
    try {
      if (navigator.canShare({ files: [verifiedMediaFile] })) {
        await navigator.share({
          files: [verifiedMediaFile],
          title: activeJob?.title || 'StreamRip Pro Media',
        });
      }
    } catch {
      // User cancelled share sheet
    }
  }

  async function handleTriggerDiagnostic(diagId: string) {
    setIsTestingDiag(true);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
          simulate_diagnostic: diagId,
        }),
      });
      const data = await res.json();
      setLabDiagResult(data as DiagnosticErrorPayload);
    } finally {
      setIsTestingDiag(false);
    }
  }

  async function handleRunQaSuite() {
    setIsRunningQa(true);
    try {
      const res = await fetch('/api/qa/run-suite', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = (await res.json()) as QaSuiteReport;
      setQaReport(data);
    } finally {
      setIsRunningQa(false);
    }
  }

  async function fetchAdminMetrics() {
    setIsLoadingAdmin(true);
    try {
      const res = await fetch('/api/admin/metrics', { credentials: 'include' });
      if (res.ok) {
        const data = (await res.json()) as AdminMetricsData;
        setAdminData(data);
      }
    } finally {
      setIsLoadingAdmin(false);
    }
  }

  async function handleCleanupTempFiles() {
    await fetch('/api/admin/cleanup', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    await fetchAdminMetrics();
  }

  async function fetchDeliverables() {
    const res = await fetch('/api/project-deliverables', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      setDeliverables(data.files || []);
    }
  }

  function handleExportProjectBundle() {
    const blob = new Blob(
      [JSON.stringify({ project: 'StreamRip Pro', files: deliverables }, null, 2)],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    triggerBrowserDownload(url, 'StreamRip_Pro_2026_Full_Project_Deliverables.json');
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  const displayedQualities = analysis?.qualities || [];
  const displayedAudioFormats = analysis?.audio_formats || [];
  const currentAudioFormatObj =
    displayedAudioFormats.find((a) => a.id === selectedAudioFormat) || displayedAudioFormats[0];

  const activeDeliverable =
    deliverables.find((f) => f.path === selectedFilePath) || deliverables[0];

  const isJobRunning = isStartingJob || activeJob?.status === 'processing' || isFetchingBlob;

  const canUseWebShare =
    typeof navigator !== 'undefined' &&
    typeof navigator.canShare === 'function' &&
    verifiedMediaFile !== null &&
    navigator.canShare({ files: [verifiedMediaFile] });

  return (
    <div className="min-h-screen flex flex-col bg-[#060913] text-slate-100">
      {/* Ambient Radial Lighting */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 overflow-hidden z-0"
        style={{
          background:
            'radial-gradient(circle at 18% 12%, rgba(37, 99, 235, 0.14) 0%, transparent 45%), radial-gradient(circle at 82% 18%, rgba(6, 182, 212, 0.12) 0%, transparent 45%)',
        }}
      />

      {/* Top Navigation Bar — Strict 3-Zone Contract */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-4 sm:gap-8 px-4 sm:px-6 py-3.5 border-b border-slate-800/80 bg-[#060913]/95 backdrop-blur-xl">
        <a
          href="#workspace"
          onClick={(e) => {
            e.preventDefault();
            setActiveTab('workspace');
          }}
          className="text-lg sm:text-xl font-bold tracking-tight text-white font-display whitespace-nowrap shrink-0"
        >
          StreamRip Pro
        </a>

        <div className="flex items-center shrink-0">
          <button
            type="button"
            onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-slate-800/90 border border-slate-700 rounded-lg hover:bg-slate-700 hover:border-cyan-500/50 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
          >
            <Globe className="w-3.5 h-3.5 text-cyan-400" />
            <span>{t.langSwitch}</span>
          </button>
        </div>
      </header>

      {/* Centered Download Progress Modal Overlay (Matches Screenshot) */}
      {isJobRunning && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="download-progress-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm"
        >
          <div className="w-full max-w-[390px] rounded-2xl bg-gradient-to-b from-[#131d31] to-[#0b1322] border border-slate-700/80 p-6 shadow-2xl text-center space-y-5">
            <h3
              id="download-progress-title"
              className="text-lg sm:text-xl font-bold text-white tracking-wide"
            >
              {lang === 'hi' ? 'डाउनलोड प्रगति' : 'Download Progress'}
            </h3>

            <div className="space-y-2.5">
              <div className="w-full h-3.5 bg-slate-800/95 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-sky-400 to-cyan-400 rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(99, Math.max(5, downloadProgress || 12))}%`,
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs sm:text-sm font-mono tabular-nums text-slate-300">
                <span>{Math.min(99, Math.max(5, downloadProgress || 12))}%</span>
                <span>{downloadSpeedMbps.toFixed(1)} MB/s</span>
              </div>
            </div>

            <div className="pt-1">
              <button
                type="button"
                onClick={handleCancelDownloadJob}
                className="px-6 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 active:bg-red-700 text-white font-bold text-sm transition-colors shadow-lg shadow-red-500/25 cursor-pointer"
              >
                {lang === 'hi' ? 'रद्द करें' : 'Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Container */}
      <main className="relative z-10 flex-1 w-full max-w-[680px] mx-auto px-4 sm:px-6 py-5 space-y-5">
        {activeTab === 'workspace' && (
          <>
            {/* Top URL Input & Analysis Card */}
            <section className="glass-panel rounded-2xl p-4 sm:p-6 space-y-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAnalyzeUrl(urlInput);
                }}
                className="flex items-center gap-2"
              >
                <div className="relative flex-1 min-w-0 flex items-center">
                  <input
                    type="text"
                    value={urlInput}
                    onChange={(e) => {
                      const nextVal = e.target.value;
                      setUrlInput(nextVal);
                      const trimmed = nextVal.trim();
                      if (!trimmed) {
                        lastAutoAnalyzedUrlRef.current = '';
                        setAnalysis(null);
                        setActiveJob(null);
                        setErrorDiag(null);
                        return;
                      }
                      if (
                        looksLikeCompleteYouTubeUrl(trimmed) &&
                        trimmed !== lastAutoAnalyzedUrlRef.current
                      ) {
                        handleAnalyzeUrl(trimmed);
                      }
                    }}
                    onPaste={(e) => {
                      const pasted = e.clipboardData.getData('text');
                      if (pasted && pasted.trim()) {
                        const cleanPasted = pasted.trim();
                        setUrlInput(cleanPasted);
                        if (cleanPasted !== lastAutoAnalyzedUrlRef.current) {
                          setTimeout(() => handleAnalyzeUrl(cleanPasted), 30);
                        }
                      }
                    }}
                    placeholder={t.inputPlaceholder}
                    aria-label="Video URL"
                    className="w-full px-3.5 py-3.5 bg-[#060913]/95 border border-slate-800 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 transition-colors font-mono"
                  />
                </div>

                {urlInput && (
                  <button
                    type="button"
                    onClick={() => {
                      setUrlInput('');
                      lastAutoAnalyzedUrlRef.current = '';
                      setAnalysis(null);
                      setActiveJob(null);
                      setErrorDiag(null);
                    }}
                    title={t.clearBtn}
                    className="px-2 py-3.5 text-slate-300 hover:text-white bg-slate-800/70 hover:bg-slate-700 border border-slate-700/80 rounded-xl transition-colors shrink-0 cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}

                <button
                  type="button"
                  onClick={handlePasteClipboard}
                  className="px-3.5 py-3.5 rounded-xl text-xs sm:text-sm font-medium text-slate-200 bg-slate-900/90 hover:bg-slate-800 border border-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
                >
                  {lang === 'hi' ? 'पेस्ट' : 'Paste'}
                </button>

                <button
                  type="submit"
                  disabled={isAnalyzing}
                  className="px-4 sm:px-5 py-3.5 rounded-xl font-bold text-xs sm:text-sm text-cyan-300 bg-[#0b3b49] hover:bg-[#0e4b5c] border border-cyan-500/30 disabled:opacity-60 transition-all whitespace-nowrap shrink-0 cursor-pointer"
                >
                  {isAnalyzing ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>{lang === 'hi' ? 'जाँच...' : 'Analyzing...'}</span>
                    </span>
                  ) : (
                    <span>{lang === 'hi' ? 'विश्लेषण करें' : 'Analyze'}</span>
                  )}
                </button>
              </form>

              {analysis && !isAnalyzing && (
                <p className="text-xs sm:text-sm text-slate-400">
                  {lang === 'hi'
                    ? 'विश्लेषण पूर्ण! अपनी पसंदीदा क्वालिटी चुनें।'
                    : 'Analysis complete! Choose your preferred quality.'}
                </p>
              )}

              {/* Loading state while pasted URL is being analyzed */}
              {isAnalyzing && !analysis && (
                <div className="py-4 flex items-center justify-center gap-2.5 text-xs sm:text-sm text-cyan-300">
                  <Loader2 className="w-4 h-4 animate-spin text-cyan-400 shrink-0" />
                  <span>
                    {lang === 'hi'
                      ? 'लिंक का विश्लेषण किया जा रहा है...'
                      : 'Analyzing video link...'}
                  </span>
                </div>
              )}

              {/* Error Alert Banner */}
              {errorDiag && (
                <div
                  role="alert"
                  className="rounded-xl p-3.5 bg-rose-950/40 border border-rose-500/40 flex items-start gap-3 relative"
                >
                  <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                  <div className="space-y-0.5 flex-1 pr-6">
                    <h2 className="text-xs sm:text-sm font-bold text-white">
                      {lang === 'en' ? errorDiag.title_en : errorDiag.title_hi}
                    </h2>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {lang === 'en' ? errorDiag.message_en : errorDiag.message_hi}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setErrorDiag(null)}
                    className="absolute top-3 right-3 text-slate-400 hover:text-white p-1 rounded-lg transition-colors cursor-pointer"
                    title="Close"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Video Preview & 2-Column Download Options Grid (Matches Screenshot) */}
              {analysis && (
                <div className="pt-2 space-y-4">
                  {/* Large Video Thumbnail */}
                  <div className="overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950">
                    <img
                      src={analysis.thumbnail}
                      alt={analysis.title}
                      className="w-full aspect-video object-cover"
                    />
                  </div>

                  {/* Video Title & Channel Info */}
                  <div className="space-y-1">
                    <h2 className="text-base sm:text-lg font-bold text-slate-100 leading-snug">
                      {analysis.title}
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-400">
                      {analysis.channel}
                      {analysis.duration_formatted ? ` · ${analysis.duration_formatted}` : ''}
                    </p>
                  </div>

                  {/* 2-Column Quality Selection Cards (Tap to Immediately Download with Modal Progress) */}
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    {[...displayedQualities]
                      .filter((q) => q.available && q.height <= 1080)
                      .sort((a, b) => b.height - a.height)
                      .map((q) => {
                        const shortLabel = q.label.split(' ')[0] || q.id;
                        const sizeLabel = q.estimated_size_mb
                          ? `${q.estimated_size_mb.toFixed(1)} MB · MP4`
                          : `${lang === 'hi' ? 'उपलब्ध' : 'Available'} · MP4`;

                        return (
                          <button
                            key={q.id}
                            type="button"
                            disabled={isJobRunning}
                            onClick={() => handleStartDownloadJob('video', q.id)}
                            className="flex flex-col items-center justify-center gap-1 p-3.5 rounded-xl bg-[#090d16] hover:bg-[#11192b] border border-slate-800/90 hover:border-cyan-500/50 transition-all text-center cursor-pointer disabled:opacity-50"
                          >
                            <span className="text-sm sm:text-base font-bold text-slate-100">
                              {shortLabel}
                            </span>
                            <span className="text-xs text-slate-400 font-mono">
                              {lang === 'hi' ? 'उपलब्ध · MP4' : sizeLabel}
                            </span>
                          </button>
                        );
                      })}

                    {/* Audio MP3 Option Card */}
                    {(() => {
                      const mp3Fmt =
                        displayedAudioFormats.find((a) => a.id === 'mp3') ||
                        displayedAudioFormats[0];
                      const mp3Br =
                        mp3Fmt?.bitrates.find((b) => b.bitrate === '192k') ||
                        mp3Fmt?.bitrates[0];
                      const mp3Size = mp3Br?.estimated_size_mb
                        ? `${mp3Br.estimated_size_mb.toFixed(1)} MB · MP3`
                        : 'MP3';

                      return (
                        <button
                          type="button"
                          disabled={isJobRunning}
                          onClick={() =>
                            handleStartDownloadJob(
                              'audio',
                              undefined,
                              'mp3',
                              mp3Br?.bitrate || '192k'
                            )
                          }
                          className="flex flex-col items-center justify-center gap-1 p-3.5 rounded-xl bg-[#090d16] hover:bg-[#11192b] border border-slate-800/90 hover:border-cyan-500/50 transition-all text-center cursor-pointer disabled:opacity-50"
                        >
                          <span className="text-sm sm:text-base font-bold text-slate-100">
                            Audio MP3
                          </span>
                          <span className="text-xs text-slate-400 font-mono">{mp3Size}</span>
                        </button>
                      );
                    })()}
                  </div>

                  {/* Completed Download Direct Save Banner (if user wants to re-save or share) */}
                  {!isJobRunning &&
                    activeJob?.status === 'completed' &&
                    activeJob?.video_id === analysis.video_id && (
                      <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-500/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                            <span className="text-xs sm:text-sm font-bold text-white">
                              {lang === 'hi'
                                ? 'डाउनलोड पूर्ण! फ़ाइल तैयार है।'
                                : 'Download complete! File is ready.'}
                            </span>
                          </div>
                          <p className="text-xs text-emerald-300/90 font-mono">
                            {activeJob.filename} (
                            {(activeJob.file_size_bytes
                              ? activeJob.file_size_bytes / (1024 * 1024)
                              : 0
                            ).toFixed(2)}{' '}
                            MB)
                          </p>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => {
                              if (verifiedBlobUrl) {
                                triggerBrowserDownload(verifiedBlobUrl, activeJob.filename);
                              } else {
                                fetchVerifiedMediaBlob(activeJob);
                              }
                            }}
                            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors cursor-pointer"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>{lang === 'hi' ? 'फ़ाइल सेव करें' : 'Save File'}</span>
                          </button>
                          {canUseWebShare && verifiedMediaFile && (
                            <button
                              type="button"
                              onClick={handleShareFileAndroid}
                              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold text-slate-100 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors cursor-pointer"
                            >
                              <Share2 className="w-3.5 h-3.5 text-cyan-400" />
                              <span>{lang === 'hi' ? 'शेयर' : 'Share'}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                </div>
              )}
            </section>
          </>
        )}

        {/* =========================================================
            TAB 2: HTTP ERROR HANDLING & YOUTUBE HTTP 403 DIAGNOSTICS LAB
           ========================================================= */}
        {activeTab === 'diagnostics' && (
          <section className="glass-panel rounded-2xl p-6 sm:p-8 space-y-6">
            <div className="space-y-2">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">{t.diagnosticsHeading}</h1>
              <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">{t.diagnosticsSub}</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5 space-y-2">
                <div className="space-y-1.5 max-h-[460px] overflow-y-auto pr-1">
                  {DIAGNOSTIC_TRIGGERS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      disabled={isTestingDiag}
                      onClick={() => handleTriggerDiagnostic(item.id)}
                      className="w-full text-left px-3.5 py-2.5 rounded-xl text-xs font-mono bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/40 text-slate-200 transition-colors cursor-pointer flex items-center justify-between"
                    >
                      <span className="truncate">{item.label}</span>
                      <Terminal className="w-3.5 h-3.5 text-cyan-400 shrink-0 ml-2" />
                    </button>
                  ))}
                </div>
              </div>

              <div className="lg:col-span-7 bg-slate-950/90 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between space-y-4">
                {labDiagResult ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div>
                        <span className="text-xs font-mono text-rose-400">
                          HTTP {labDiagResult.http_status} · {labDiagResult.error_code}
                        </span>
                        <h3 className="text-lg font-bold text-white mt-0.5">
                          {lang === 'en' ? labDiagResult.title_en : labDiagResult.title_hi}
                        </h3>
                      </div>
                      <ShieldAlert className="w-6 h-6 text-rose-400" />
                    </div>

                    <div className="space-y-2 text-sm">
                      <p className="text-slate-200">
                        {lang === 'en' ? labDiagResult.message_en : labDiagResult.message_hi}
                      </p>
                      <p className="text-xs text-cyan-300">
                        {lang === 'en' ? labDiagResult.action_en : labDiagResult.action_hi}
                      </p>
                    </div>

                    <pre className="p-3 rounded-xl bg-black/70 border border-slate-800 text-xs font-mono text-slate-400 overflow-x-auto">
                      {JSON.stringify(labDiagResult, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <div className="my-auto text-center py-12 space-y-3">
                    <ShieldCheck className="w-10 h-10 text-cyan-400 mx-auto" />
                    <p className="text-sm text-slate-300">
                      {lang === 'hi'
                        ? 'बाईं ओर किसी भी HTTP त्रुटि या 403 विकल्प पर क्लिक करें।'
                        : 'Select any HTTP status or YouTube 403 subtype on the left to inspect diagnostics.'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* =========================================================
            TAB 3: AUTOMATED QUALITY ASSURANCE (QA) SUITE
           ========================================================= */}
        {activeTab === 'qa' && (
          <section className="glass-panel rounded-2xl p-6 sm:p-8 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <h1 className="text-2xl sm:text-3xl font-bold text-white">{t.qaHeading}</h1>
                <p className="text-sm text-slate-300 max-w-2xl">{t.qaSub}</p>
              </div>
              <button
                type="button"
                disabled={isRunningQa}
                onClick={handleRunQaSuite}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 disabled:opacity-60 transition-all whitespace-nowrap shrink-0 cursor-pointer"
              >
                {isRunningQa ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t.runningQaBtn}</span>
                  </>
                ) : (
                  <>
                    <ClipboardCheck className="w-4 h-4" />
                    <span>{t.runQaBtn}</span>
                  </>
                )}
              </button>
            </div>

            {qaReport && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">TOTAL QA SCENARIOS</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-white mt-1">
                      {qaReport.total_tests}
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">PASSED SCENARIOS</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-emerald-400 mt-1">
                      {qaReport.passed_tests}
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">SUITE VERDICT</span>
                    <p className="text-2xl font-bold font-mono text-cyan-400 mt-1">
                      {qaReport.all_passed ? '100% VERIFIED' : 'ISSUES FOUND'}
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400">
                        <th className="py-3 px-3">Scenario</th>
                        <th className="py-3 px-3">Test Input</th>
                        <th className="py-3 px-3">Actual Backend Output</th>
                        <th className="py-3 px-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70 text-xs sm:text-sm">
                      {qaReport.results.map((r) => (
                        <tr key={r.id} className="hover:bg-slate-900/40">
                          <td className="py-3 px-3 font-semibold text-white">
                            {lang === 'en' ? r.name_en : r.name_hi}
                          </td>
                          <td className="py-3 px-3 font-mono text-xs text-slate-400">{r.input}</td>
                          <td className="py-3 px-3 font-mono text-xs text-slate-300">{r.actual}</td>
                          <td className="py-3 px-3 text-right font-mono whitespace-nowrap">
                            {r.passed ? (
                              <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                                <CheckCircle2 className="w-4 h-4" />
                                PASS
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
                                <XCircle className="w-4 h-4" />
                                FAIL
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        )}

        {/* =========================================================
            TAB 4: ADMIN & MONITORING DASHBOARD
           ========================================================= */}
        {activeTab === 'admin' && (
          <section className="glass-panel rounded-2xl p-6 sm:p-8 space-y-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <h1 className="text-2xl sm:text-3xl font-bold text-white">{t.adminHeading}</h1>
                <p className="text-sm text-slate-300">{t.adminSub}</p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={fetchAdminMetrics}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors cursor-pointer whitespace-nowrap shrink-0"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingAdmin ? 'animate-spin' : ''}`} />
                  <span>{t.refreshBtn}</span>
                </button>
                <button
                  type="button"
                  onClick={handleCleanupTempFiles}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-rose-600/20 border border-rose-500/40 hover:bg-rose-600/30 text-rose-200 transition-colors cursor-pointer whitespace-nowrap shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{t.cleanupBtn}</span>
                </button>
              </div>
            </div>

            {adminData && (
              <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">TOTAL REQUESTS</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-white mt-1">
                      {adminData.total_requests}
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">SUCCESSFUL DOWNLOADS</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-emerald-400 mt-1">
                      {adminData.successful_downloads}
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">FAILED / BLOCKED</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-amber-400 mt-1">
                      {adminData.failed_requests}
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800">
                    <span className="text-xs text-slate-400">AVG PROCESSING TIME</span>
                    <p className="text-2xl font-bold font-mono tabular-nums text-cyan-400 mt-1">
                      {adminData.average_processing_time_ms} ms
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-white">
                      <Cpu className="w-4 h-4 text-cyan-400" />
                      <span>Media Engine & Binary Status ({adminData.status})</span>
                    </div>
                    <div className="space-y-2 text-xs font-mono">
                      <div className="flex justify-between py-1.5 border-b border-slate-800">
                        <span className="text-slate-400">FFmpeg Binary:</span>
                        <span className="text-emerald-400">
                          {adminData.binaries.ffmpeg_available
                            ? adminData.binaries.ffmpeg_version?.slice(0, 38)
                            : 'MISSING'}
                        </span>
                      </div>
                      <div className="flex justify-between py-1.5 border-b border-slate-800">
                        <span className="text-slate-400">FFprobe Binary:</span>
                        <span className="text-emerald-400">
                          {adminData.binaries.ffprobe_available
                            ? adminData.binaries.ffprobe_version?.slice(0, 38)
                            : 'MISSING'}
                        </span>
                      </div>
                      <div className="flex justify-between py-1.5">
                        <span className="text-slate-400">yt-dlp Extractor:</span>
                        <span className="text-cyan-400">
                          {adminData.binaries.yt_dlp_available
                            ? `v${adminData.binaries.yt_dlp_version}`
                            : 'MISSING'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-bold text-white">
                        <HardDrive className="w-4 h-4 text-cyan-400" />
                        <span>Temporary Storage Utilization</span>
                      </div>
                      <span className="text-xs font-mono tabular-nums text-cyan-400">
                        {adminData.storage.used_mb} MB / {adminData.storage.max_mb} MB
                      </span>
                    </div>
                    <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                      <div
                        className="h-full bg-gradient-to-r from-blue-600 to-cyan-400"
                        style={{ width: `${Math.min(100, adminData.storage.utilization_percent)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs font-mono text-slate-400">
                      <span>Path: {adminData.storage.directory}</span>
                      <span>Active Files: {adminData.storage.active_files}</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </section>
        )}

        {/* =========================================================
            TAB 5: CLOUD DEPLOYMENT & COMPLETE SOURCE DELIVERABLES
           ========================================================= */}
        {activeTab === 'deploy' && (
          <section className="space-y-8">
            <div className="glass-panel rounded-2xl p-6 sm:p-8 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h1 className="text-2xl sm:text-3xl font-bold text-white">{t.deployHeading}</h1>
                  <p className="text-sm text-slate-300">{t.deploySub}</p>
                </div>
                <button
                  type="button"
                  onClick={handleExportProjectBundle}
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-semibold text-xs sm:text-sm text-white bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 transition-all whitespace-nowrap shrink-0 cursor-pointer"
                >
                  <FolderGit2 className="w-4 h-4" />
                  <span>{t.exportBundleBtn}</span>
                </button>
              </div>

              <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-4">
                {(
                  [
                    ['cloudrun', 'Google Cloud Run'],
                    ['railway', 'Railway'],
                    ['render', 'Render'],
                    ['vps', 'Docker-Based VPS'],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setSelectedCloudGuide(id)}
                    className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer whitespace-nowrap shrink-0 ${
                      selectedCloudGuide === id
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-900 text-slate-400 hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {selectedCloudGuide === 'cloudrun' && (
                <div className="space-y-3 text-xs sm:text-sm text-slate-300">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Cloud className="w-4 h-4 text-cyan-400" />
                    <span>Google Cloud Run Deployment</span>
                  </h3>
                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 overflow-x-auto">
{`gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/streamrip-pro
gcloud run deploy streamrip-pro \\
  --image gcr.io/YOUR_PROJECT_ID/streamrip-pro \\
  --platform managed \\
  --region asia-northeast1 \\
  --allow-unauthenticated \\
  --memory 2Gi \\
  --cpu 2 \\
  --timeout 300s \\
  --port 3000`}
                  </pre>
                </div>
              )}

              {selectedCloudGuide === 'railway' && (
                <div className="space-y-3 text-xs sm:text-sm text-slate-300">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Server className="w-4 h-4 text-cyan-400" />
                    <span>Railway Deployment</span>
                  </h3>
                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 overflow-x-auto">
{`npm i -g @railway/cli && railway login
railway init
railway up`}
                  </pre>
                </div>
              )}

              {selectedCloudGuide === 'render' && (
                <div className="space-y-3 text-xs sm:text-sm text-slate-300">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Server className="w-4 h-4 text-cyan-400" />
                    <span>Render Docker Web Service Deployment</span>
                  </h3>
                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 overflow-x-auto">
{`Runtime: Docker
Dockerfile Path: ./Dockerfile
Health Check Path: /api/health
PORT=3000`}
                  </pre>
                </div>
              )}

              {selectedCloudGuide === 'vps' && (
                <div className="space-y-3 text-xs sm:text-sm text-slate-300">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-cyan-400" />
                    <span>Docker-Based VPS Deployment</span>
                  </h3>
                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 overflow-x-auto">
{`docker build -t streamrip-pro:2026 .
docker run -d --name streamrip-pro -p 3000:3000 --restart unless-stopped streamrip-pro:2026`}
                  </pre>
                </div>
              )}
            </div>

            <div className="glass-panel rounded-2xl p-6 sm:p-8 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Code2 className="w-5 h-5 text-cyan-400" />
                  <span>Project Deliverables & Source Code</span>
                </h2>
                <span className="text-xs font-mono text-slate-400">
                  {deliverables.length} Files
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-4 space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
                  {deliverables.map((file) => (
                    <button
                      key={file.path}
                      type="button"
                      onClick={() => setSelectedFilePath(file.path)}
                      className={`w-full text-left p-3 rounded-xl border transition-colors cursor-pointer ${
                        selectedFilePath === file.path
                          ? 'bg-blue-600/15 border-cyan-400 text-white'
                          : 'bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono text-xs font-semibold">
                        <span className="truncate">{file.path}</span>
                        <span className="text-slate-500 shrink-0 ml-2">{file.lines}L</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-1">
                        {file.description}
                      </p>
                    </button>
                  ))}
                </div>

                <div className="lg:col-span-8 bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col">
                  {activeDeliverable && (
                    <>
                      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800 text-xs font-mono">
                        <span className="text-cyan-400 font-semibold">
                          /{activeDeliverable.path}
                        </span>
                        <span className="text-slate-400">
                          {activeDeliverable.category} · {activeDeliverable.lines} lines
                        </span>
                      </div>
                      <pre className="text-xs font-mono text-slate-300 overflow-auto max-h-[450px] leading-relaxed">
                        {activeDeliverable.content}
                      </pre>
                    </>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Cookie Setup Modal */}
      {showCookieModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="glass-panel w-full max-w-lg rounded-2xl p-6 space-y-4 border border-cyan-500/40 shadow-2xl bg-slate-900/95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  {lang === 'hi' ? 'YouTube कुकीज़ सेटअप (cookies.txt)' : 'YouTube Cookies Setup (cookies.txt)'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCookieModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="text-xs text-slate-300 space-y-2">
              <p>
                {lang === 'hi'
                  ? 'YouTube क्लाउड डेटासेंटर सर्वर से वीडियो निकालने पर बॉट ब्लॉक (Sign in to confirm you’re not a bot) लगाता है। अपने ब्राउज़र से Export किया हुआ cookies.txt यहाँ पेस्ट करने से सर्वर सीधे 100% ओरिजिनल 1080p वीडियो डाउनलोड कर सकेगा।'
                  : 'YouTube restricts automated downloads from datacenter IPs. Pasting cookies.txt from a logged-in browser session authorizes yt-dlp to download complete 1080p video streams directly on the server.'}
              </p>
              <p className="text-slate-400">
                {lang === 'hi'
                  ? 'निर्देश: Chrome/Firefox एक्सटेंशन "Get cookies.txt LOCALLY" से YouTube का cookies.txt कॉपी करें और नीचे पेस्ट करें।'
                  : 'Guide: Export cookies.txt using "Get cookies.txt LOCALLY" browser extension and paste contents below.'}
              </p>
            </div>

            <div className="space-y-1.5">
              <textarea
                value={cookieInput}
                onChange={(e) => setCookieInput(e.target.value)}
                placeholder="# Netscape HTTP Cookie File&#10;.youtube.com&#9;TRUE&#9;/&#9;TRUE&#9;1799999999&#9;LOGIN_INFO&#9;..."
                rows={6}
                className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 resize-none"
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              {hasCookies ? (
                <button
                  type="button"
                  onClick={handleClearCookies}
                  className="inline-flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{lang === 'hi' ? 'मौजूदा कुकीज़ हटाएं' : 'Remove Cookies'}</span>
                </button>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowCookieModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 cursor-pointer"
                >
                  {lang === 'hi' ? 'रद्द करें' : 'Cancel'}
                </button>
                <button
                  type="button"
                  disabled={!cookieInput.trim() || isSavingCookies}
                  onClick={handleSaveCookies}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 transition-all cursor-pointer shadow-md"
                >
                  {isSavingCookies && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{lang === 'hi' ? 'सहेजें व सक्रिय करें' : 'Save & Activate'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
