#!/usr/bin/env bash
# Azure App Service startup command: `bash startup.sh`
# Installs the native voice dependencies the App Service Python image lacks, then starts the bot.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1 || ! ldconfig -p 2>/dev/null | grep -q libopus.so.0; then
    echo "Installing ffmpeg and libopus0..."
    apt-get update -qq && apt-get install -y -qq --no-install-recommends ffmpeg libopus0
fi

if [ -d antenv ]; then
    # Oryx-built virtualenv
    # shellcheck disable=SC1091
    source antenv/bin/activate
fi

exec python main.py
