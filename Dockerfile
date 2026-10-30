
# Build React frontend
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY . .
RUN npm install && npm run build

# Python backend and FFmpeg
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

ENV PORT=10000
EXPOSE 10000

CMD ["python", "-m", "backend.app"]
