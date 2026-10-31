import express, { Request, Response, NextFunction } from 'express';
import { spawn, ChildProcess } from 'child_process';
import crypto from 'crypto';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const PYTHON_PORT = Number(process.env.PYTHON_BACKEND_PORT) || 5001;
const PYTHON_HOST = '127.0.0.1';
const PYTHON_TARGET_PORT = PYTHON_PORT;
const PYTHON_BACKEND_URL = `http://${PYTHON_HOST}:${PYTHON_TARGET_PORT}`;

let pythonProcess: ChildProcess | null = null;

function startPythonBackend(): void {
  const scriptPath = path.join(__dirname, 'backend', 'app.py');
  pythonProcess = spawn('python3', [scriptPath], {
    env: {
      ...process.env,
      PYTHON_BACKEND_PORT: String(PYTHON_PORT),
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pythonProcess.stdout?.on('data', (chunk) => {
    process.stdout.write(`[Python] ${chunk}`);
  });

  pythonProcess.stderr?.on('data', (chunk) => {
    process.stderr.write(`[Python Err] ${chunk}`);
  });

  pythonProcess.on('exit', (code) => {
    console.warn(`[Gateway] Python backend exited with code ${code}. Restarting in 1.5s...`);
    setTimeout(startPythonBackend, 1500);
  });
}

async function waitForPythonReady(maxWaitMs = 8000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const ok = await new Promise<boolean>((resolve) => {
      const req = http.get(`http://${PYTHON_HOST}:${PYTHON_TARGET_PORT}/api/health`, (res) => {
        res.resume();
        resolve((res.statusCode || 500) < 500);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(1000, () => {
        req.destroy();
        resolve(false);
      });
    });
    if (ok) return;
    await new Promise((r) => setTimeout(r, 200));
  }
}

const DELIVERABLE_FILES = [
  { path: 'backend/app.py', category: 'Python Backend', description: 'Python 3 REST API server, streaming file delivery, and QA test runner' },
  { path: 'backend/media_engine.py', category: 'Python Backend', description: 'yt-dlp metadata discovery, FFmpeg stream merging, audio extraction & FFprobe verification' },
  { path: 'backend/security.py', category: 'Security', description: 'URL allowlisting, SSRF protection, filename sanitization & sliding-window rate limiter' },
  { path: 'backend/diagnostics.py', category: 'Diagnostics', description: 'Structured HTTP 400/403/404/408/429/500/502/503 & 6-way YouTube HTTP 403 classifier' },
  { path: 'frontend/index.html', category: 'Standalone Frontend', description: 'Standalone HTML5 client interface' },
  { path: 'frontend/styles.css', category: 'Standalone Frontend', description: 'Standalone CSS3 dark glassmorphic stylesheet' },
  { path: 'frontend/app.js', category: 'Standalone Frontend', description: 'Standalone Vanilla JavaScript API client' },
  { path: 'tests/test_backend.py', category: 'Automated QA', description: 'Python unittest suite testing 12 mandatory QA & playability scenarios' },
  { path: 'requirements.txt', category: 'Cloud Deployment', description: 'Python package dependencies' },
  { path: 'Dockerfile', category: 'Cloud Deployment', description: 'Multi-stage production Dockerfile (Node 22 + Python 3.12 + FFmpeg + yt-dlp)' },
  { path: '.dockerignore', category: 'Cloud Deployment', description: 'Docker context exclusions' },
  { path: '.env.example', category: 'Cloud Deployment', description: 'Environment variable configuration template' },
  { path: 'README.md', category: 'Documentation', description: 'Complete architecture & Cloud Run / Railway / Render / VPS deployment guide' },
];

function parseCookies(cookieHeader: string | undefined): Record<string, string> {
  const list: Record<string, string> = {};
  if (!cookieHeader) return list;
  cookieHeader.split(';').forEach((cookie) => {
    const parts = cookie.split('=');
    const key = parts.shift()?.trim();
    if (key) {
      list[key] = decodeURIComponent(parts.join('=').trim());
    }
  });
  return list;
}

async function startServer() {
  startPythonBackend();
  await waitForPythonReady();

  const app = express();

  // Trust Cloud Run / reverse proxy headers (X-Forwarded-Proto, X-Forwarded-For)
  app.set('trust proxy', 1);

  // First-Party CHIPS / Partitioned Session & Security Middleware for Android Chrome & Embedded Preview
  app.use((req: Request, res: Response, next: NextFunction) => {
    const isSecure = req.secure || req.headers['x-forwarded-proto'] === 'https';
    const cookies = parseCookies(req.headers.cookie);
    let sessionId = cookies['streamrip_sid'] || (req.headers['x-streamrip-session'] as string);

    if (!sessionId || !/^[a-f0-9]{32}$/.test(sessionId)) {
      sessionId = crypto.randomBytes(16).toString('hex');
      const cookieAttrs = [
        `streamrip_sid=${sessionId}`,
        'Path=/',
        'HttpOnly',
        'Max-Age=86400',
      ];
      if (isSecure) {
        // Use SameSite=None; Secure; Partitioned (CHIPS) for embedded cross-site contexts on Android Chrome
        cookieAttrs.push('Secure', 'SameSite=None', 'Partitioned');
      } else {
        cookieAttrs.push('SameSite=Lax');
      }
      res.setHeader('Set-Cookie', cookieAttrs.join('; '));
    }

    res.setHeader('X-StreamRip-Session', sessionId);
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Vary', 'Origin, Cookie');
    next();
  });

  // Session & Cookie Health Check Endpoint
  app.get('/api/session-status', (req: Request, res: Response) => {
    const isSecure = req.secure || req.headers['x-forwarded-proto'] === 'https';
    res.json({
      authenticated: true,
      pythonBackend: PYTHON_BACKEND_URL,
      transport: isSecure ? 'HTTPS (Secure + SameSite=None + Partitioned CHIPS)' : 'HTTP (Local SameSite=Lax)',
      deliveryMode: 'Chunked ReadableStream + Contiguous Blob (Android Chrome Safe)',
      sessionIdPresent: Boolean(res.getHeader('X-StreamRip-Session')),
    });
  });

  // Endpoint to inspect all 14 project deliverables and source code directly in the UI
  app.get('/api/project-deliverables', (_req: Request, res: Response) => {
    const filesWithContent = DELIVERABLE_FILES.map((item) => {
      const fullPath = path.join(__dirname, item.path);
      let content = '';
      let sizeBytes = 0;
      try {
        content = fs.readFileSync(fullPath, 'utf-8');
        sizeBytes = Buffer.byteLength(content, 'utf-8');
      } catch {
        content = '# File not found';
      }
      return {
        ...item,
        sizeBytes,
        lines: content.split('\n').length,
        content,
      };
    });
    res.json({
      project: 'StreamRip Pro',
      version: '2.7.0',
      files: filesWithContent,
    });
  });

  // Set of hop-by-hop HTTP headers that must not be blindly re-forwarded
  const HOP_BY_HOP_HEADERS = new Set([
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
  ]);

  // CORS & Preflight handling for all /api endpoints (essential for Android Chrome & iframe range requests)
  app.use('/api', (req: Request, res: Response, next: NextFunction) => {
    const origin = req.headers.origin || '*';
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, HEAD');
    res.setHeader('Access-Control-Allow-Headers', 'Range, Content-Type, Authorization, X-StreamRip-Session, X-Requested-With, Cache-Control, Pragma, Accept');
    res.setHeader('Access-Control-Expose-Headers', 'Content-Length, Content-Range, Content-Disposition, Accept-Ranges, X-StreamRip-Job-Id, X-StreamRip-Verified-Bytes');
    res.setHeader('Access-Control-Allow-Credentials', 'true');

    if (req.method === 'OPTIONS') {
      res.status(204).end();
      return;
    }
    next();
  });

  // Proxy all other /api/* routes directly to the Python 3 backend (preserving binary streams & headers)
  app.use('/api', (req: Request, res: Response) => {
    req.setTimeout(0);
    res.setTimeout(0);
    req.socket?.setNoDelay(true);

    const options: http.RequestOptions = {
      hostname: PYTHON_HOST,
      port: PYTHON_TARGET_PORT,
      path: `/api${req.url}`,
      method: req.method,
      timeout: 0,
      headers: {
        ...req.headers,
        host: `${PYTHON_HOST}:${PYTHON_TARGET_PORT}`,
        connection: 'close',
      },
    };

    const proxyReq = http.request(options, (proxyRes) => {
      res.status(proxyRes.statusCode || 500);
      Object.entries(proxyRes.headers).forEach(([key, val]) => {
        const lowKey = key.toLowerCase();
        if (
          val !== undefined &&
          !HOP_BY_HOP_HEADERS.has(lowKey) &&
          !lowKey.startsWith('access-control-')
        ) {
          res.setHeader(key, val);
        }
      });
      res.setHeader('Cache-Control', 'private, no-store, no-transform');
      res.setHeader('X-Content-Type-Options', 'nosniff');

      proxyRes.on('error', () => {
        if (!res.writableEnded) {
          res.destroy();
        }
      });

      if (req.method === 'HEAD') {
        proxyRes.resume();
        res.end();
        return;
      }

      proxyRes.pipe(res);
    });

    proxyReq.on('socket', (sock) => {
      sock.setNoDelay(true);
    });
    proxyReq.setTimeout(0);

    res.on('close', () => {
      if (!res.writableEnded) {
        proxyReq.destroy();
      }
    });

    proxyReq.on('error', (err) => {
      if (!res.headersSent) {
        res.status(503).json({
          http_status: 503,
          error_code: 'PYTHON_ENGINE_UNREACHABLE',
          title_en: 'HTTP 503 — Python Media Engine Starting',
          title_hi: 'HTTP 503 — Python मीडिया इंजन प्रारंभ हो रहा है',
          message_en: `Backend gateway could not reach Python media engine: ${err.message}`,
          message_hi: 'बैकएंड गेटवे Python मीडिया इंजन तक नहीं पहुंच सका।',
        });
      } else if (!res.writableEnded) {
        res.destroy();
      }
    });

    req.on('error', () => {
      proxyReq.destroy();
    });

    req.pipe(proxyReq);
  });

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[StreamRip Pro Gateway] Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
