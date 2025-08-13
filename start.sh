#!/usr/bin/env bash
set -e

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# Ensure locale and TTS voices default to English to avoid espeak errors
export LANG=${LANG:-en_US.UTF-8}
export ESPEAK_VOICE=${ESPEAK_VOICE:-en}

# Auto-detect Piper binary and a default voice if available
if [ -z "$PIPER_PATH" ] && command -v piper >/dev/null 2>&1; then
  export PIPER_PATH="$(command -v piper)"
fi
if [ -z "$PIPER_VOICE" ] && [ -f "voices/en_US-amy-low.onnx" ]; then
  export PIPER_VOICE="voices/en_US-amy-low.onnx"
fi

# Launch Streamlit app
streamlit run app/app.py
