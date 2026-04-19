#!/bin/bash

# WebCrawler Pro Dashboard Launcher
# Double-click this file to start the dashboard

echo "🚀 Starting WebCrawler Pro Dashboard..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Navigate to project directory
cd "$(dirname "$0")"

# Set environment
export PYTHONPATH="$(pwd)"

# Check if database exists
if [ ! -f "data/webcrawler.db" ]; then
    echo "📊 Initializing database..."
    python3 scripts/init_db.py
fi

echo "🌐 Starting web dashboard..."
echo "📍 Dashboard URL: http://127.0.0.1:8888"
echo "⚠️  Keep this window open to keep the dashboard running"
echo "🛑 Press Ctrl+C to stop the dashboard"
echo ""

# Start dashboard
python3 run_web_dashboard.py

echo ""
echo "✅ Dashboard stopped successfully"
echo "Press any key to close this window..."
read -n 1