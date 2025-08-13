#!/usr/bin/env bash
set -e

# Install system dependencies
if command -v sudo >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip ffmpeg espeak
else
  apt-get update
  apt-get install -y python3 python3-venv python3-pip ffmpeg espeak
fi

# Setup Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Installation complete. Activate the environment with 'source .venv/bin/activate'."
