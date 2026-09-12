# Lane Guardian - Predecessor timer bot
# Build:  docker build -t lane-guardian .
# Run:    docker compose up -d   (see docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONFIG_PATH=/data/server_configs.json \
    HEALTH_PORT=8080

# ffmpeg decodes the TTS mp3 and encodes Opus; libopus0 is loaded by discord.py.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py ./

# Run as an unprivileged user; /data holds server_configs.json and survives upgrades.
RUN useradd --system --uid 1000 --create-home bot \
    && mkdir -p /data \
    && chown -R bot:bot /data /app
USER bot

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('HEALTH_PORT','8080'), timeout=4).status == 200 else 1)"

CMD ["python", "main.py"]
