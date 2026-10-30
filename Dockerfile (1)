# Build the React frontend
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY . .
RUN npm install --legacy-peer-deps && npm run build

# Python backend with FFmpeg
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY bin ./bin
COPY frontend ./frontend
COPY --from=frontend /build/dist ./dist

# Add React static-file serving to the existing Python API without
# replacing or removing any existing API routes.
RUN python - <<'PY'
from pathlib import Path
p = Path('/app/backend/app.py')
s = p.read_text(encoding='utf-8')
anchor = '        path = parsed.path\n'
start = s.index('    def do_GET(self)')
point = s.index(anchor, start) + len(anchor)
if '# StreamRip React static frontend' not in s[start:]:
    static_handler = '''
        # StreamRip React static frontend
        if not path.startswith("/api/"):
            dist_root = os.path.realpath(os.path.join(PROJECT_ROOT, "dist"))
            relative = urllib.parse.unquote(path).lstrip("/") or "index.html"
            candidate = os.path.realpath(os.path.join(dist_root, relative))
            safe = os.path.commonpath([dist_root, candidate]) == dist_root
            if safe and os.path.isfile(candidate):
                target = candidate
            elif safe and "." not in os.path.basename(relative):
                target = os.path.join(dist_root, "index.html")
            else:
                target = None
            if target and os.path.isfile(target):
                content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
                if target.endswith(".html"):
                    content_type = "text/html; charset=utf-8"
                size = os.path.getsize(target)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    with open(target, "rb") as file:
                        while True:
                            chunk = file.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

'''
    s = s[:point] + static_handler + s[point:]
    p.write_text(s, encoding='utf-8')
compile(s, str(p), 'exec')
print('React frontend route added; Python syntax verified')
PY

ENV PORT=10000
EXPOSE 10000
CMD ["python", "-m", "backend.app"]
