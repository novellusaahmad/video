#!/usr/bin/env bash
set -e

# Install system dependencies
packages="python3 python3-venv python3-pip ffmpeg espeak"
if command -v sudo >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y $packages
else
  apt-get update
  apt-get install -y $packages
fi

# Setup Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Pin moviepy to <2.0 so ImageClip still exposes set_duration
pip install "moviepy<2"

# Provide piper binary if users want the Piper TTS engine
pip install piper-tts

echo "Installation complete. Activate the environment with 'source .venv/bin/activate'."
