#!/usr/bin/env bash
set -e

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# Launch Streamlit app
streamlit run app/app.py
