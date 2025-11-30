#!/bin/bash
echo "Starting API..."
pip install -r ./requirements.txt -q
python3 database/session.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000 