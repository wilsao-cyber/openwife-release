#!/bin/bash
# AI Wife App — One-click startup
# Starts: SearXNG (Docker) → Voicebox (TTS) → Main Server

set -e
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "🌸 AI Wife App Starting..."
echo "================================================"

# ── 1. SearXNG (Web Search) ──
echo "[1/3] SearXNG..."
if docker ps --format '{{.Names}}' | grep -q '^searxng$'; then
    echo "  ✓ Already running"
elif docker ps -a --format '{{.Names}}' | grep -q '^searxng$'; then
    docker start searxng >/dev/null 2>&1
    echo "  ✓ Restarted"
else
    docker run -d --name searxng -p 8080:8080 searxng/searxng:latest >/dev/null 2>&1
    sleep 2
    docker exec searxng sed -i '/^  formats:/,/^[^ ]/{s/    - html/    - html\n    - json/}' /etc/searxng/settings.yml 2>/dev/null
    docker restart searxng >/dev/null 2>&1
    echo "  ✓ Created and started"
fi

# ── 2. Voicebox (TTS Engine) ──
echo "[2/3] Voicebox TTS..."
if curl -s http://localhost:17493/profiles >/dev/null 2>&1; then
    echo "  ✓ Already running"
else
    cd /home/wilsao6666/voicebox
    source backend/venv/bin/activate
    nohup python -m backend.main --port 17493 > "$PROJECT_DIR/logs/voicebox.log" 2>&1 &
    echo $! > "$PROJECT_DIR/logs/voicebox.pid"
    deactivate
    cd "$PROJECT_DIR"
    echo "  ✓ Started (PID: $(cat logs/voicebox.pid))"
    echo "  ⏳ Waiting for Voicebox to initialize..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:17493/profiles >/dev/null 2>&1; then
            echo "  ✓ Voicebox ready"
            break
        fi
        sleep 1
    done
fi

# ── 3. Main Server ──
echo "[3/3] AI Wife App Server..."
cd "$PROJECT_DIR/server"
source venv/bin/activate

echo "================================================"
echo "🌸 All services started!"
echo "   Web UI: http://localhost:8000"
echo "   Voicebox: http://localhost:17493"
echo "   SearXNG: http://localhost:8080"
echo ""
echo "   Press Ctrl+C to stop server"
echo "================================================"

# Open browser
(sleep 2 && xdg-open http://localhost:8000 2>/dev/null) &

# Run server in foreground (keeps terminal open)
python main.py 2>&1 | tee "$PROJECT_DIR/logs/server.log"
