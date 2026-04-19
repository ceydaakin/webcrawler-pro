#!/bin/bash

# WebCrawler Pro UI Demo Script
echo "🎉 WebCrawler Pro - Complete UI Demonstration"
echo "=============================================="
cd /Users/ceydaakin/BLG480E_Project2
export PYTHONPATH=$(pwd)

echo ""
echo "📊 1. System Status Check"
python3 -m src.main status

echo ""
echo "🕷️ 2. Quick Crawling Demo"
python3 -m src.main index --origin "https://example.com" --depth 1 --max-pages 5

echo ""
echo "🔍 3. Search Demo - Table Format"
python3 -m src.main search --query "example" --limit 3

echo ""
echo "📋 4. Search Demo - JSON Format"
python3 -m src.main search --query "example" --format json --limit 2

echo ""
echo "📈 5. Detailed Performance Metrics"
python3 -m src.main stats --detailed

echo ""
echo "✅ Demo Complete! All UI features demonstrated."
echo "🚀 Your WebCrawler Pro is ready for production use!"