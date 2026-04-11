#!/bin/bash

echo "Starting AI Wife Server..."

cd "$(dirname "$0")/../server"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 main.py
