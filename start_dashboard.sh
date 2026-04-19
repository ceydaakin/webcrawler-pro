#!/bin/bash

echo "🚀 Starting WebCrawler Pro Web Dashboard..."
cd /Users/ceydaakin/BLG480E_Project2
export PYTHONPATH=$(pwd)

echo "📍 Dashboard will be available at: http://127.0.0.1:8888"
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

python3 run_web_dashboard.py