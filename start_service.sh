#!/bin/bash

# WebCrawler Pro Background Service
# Starts dashboard as a background service

cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"

# Check if already running
if lsof -i :8888 >/dev/null 2>&1; then
    echo "⚠️  Dashboard is already running at http://127.0.0.1:8888"
    exit 1
fi

# Start in background
echo "🚀 Starting WebCrawler Pro Dashboard as background service..."
nohup python3 run_web_dashboard.py > logs/dashboard.log 2>&1 &

# Get the process ID
PID=$!
echo $PID > dashboard.pid

echo "✅ Dashboard started successfully!"
echo "📍 URL: http://127.0.0.1:8888"
echo "📝 Logs: logs/dashboard.log"
echo "🆔 PID: $PID (saved to dashboard.pid)"
echo ""
echo "To stop the dashboard:"
echo "   ./stop_service.sh"