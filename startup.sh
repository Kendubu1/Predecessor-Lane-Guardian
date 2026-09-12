#!/usr/bin/env bash
# Azure App Service startup command: `bash startup.sh`
# Equivalent to the previous inline command:
#   apt-get update && apt-get install -y ffmpeg && python -m pip install --upgrade pip \
#     && pip install -r requirements.txt && python main.py
# but skips the apt step when ffmpeg/libopus are already present (faster restarts).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1 || ! ldconfig -p 2>/dev/null | grep -q libopus.so.0; then
    echo "Installing ffmpeg and libopus0..."
    apt-get update -qq && apt-get install -y -qq --no-install-recommends ffmpeg libopus0
fi

if [ -d antenv ] && [ -z "${VIRTUAL_ENV:-}" ]; then
    # Oryx-built virtualenv
    # shellcheck disable=SC1091
    source antenv/bin/activate
fi

python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

exec python main.py
