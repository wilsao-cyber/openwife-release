#!/bin/bash
# AI Wife App — Stop all services

cd "$(dirname "$0")"

echo "🔴 Stopping AI Wife App..."

# Stop main server
if [ -f logs/server.pid ]; then
    PID=$(cat logs/server.pid)
    kill "$PID" 2>/dev/null && echo "  ✓ Server stopped (PID: $PID)" || echo "  - Server not running"
    rm -f logs/server.pid
else
    pkill -f "python main.py" 2>/dev/null && echo "  ✓ Server stopped" || echo "  - Server not running"
fi

# Stop Voicebox
if [ -f logs/voicebox.pid ]; then
    PID=$(cat logs/voicebox.pid)
    kill "$PID" 2>/dev/null && echo "  ✓ Voicebox stopped (PID: $PID)" || echo "  - Voicebox not running"
    rm -f logs/voicebox.pid
else
    pkill -f "backend.main --port 17493" 2>/dev/null && echo "  ✓ Voicebox stopped" || echo "  - Voicebox not running"
fi

# Stop SearXNG (optional — keep running)
# docker stop searxng 2>/dev/null && echo "  ✓ SearXNG stopped" || echo "  - SearXNG not running"

echo "🔴 All services stopped."
