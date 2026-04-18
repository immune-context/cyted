#!/bin/bash

# Activate venv if you use one
source ~/.zshrc
conda activate science-reading

# Start FastAPI
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
echo $! > server.pid

# IGNORE: for debugging
# sleep 20
# ngrok http 8000


