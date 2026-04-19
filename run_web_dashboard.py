#!/usr/bin/env python3
"""
WebCrawler Pro Web Dashboard Launcher
Simple script to start the web-based dashboard interface.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = str(project_root)

# Import and run the web dashboard
try:
    from src.web_dashboard import run_server

    print("🚀 Starting WebCrawler Pro Web Dashboard...")
    print("=" * 50)

    # Run the web server
    asyncio.run(run_server())

except KeyboardInterrupt:
    print("\n✅ Web dashboard stopped successfully!")

except Exception as e:
    print(f"❌ Error starting web dashboard: {e}")
    print("\n💡 Make sure you have:")
    print("   1. Initialized the database: python scripts/init_db.py")
    print("   2. Installed dependencies: pip install -r requirements.txt aiohttp-cors")
    print("   3. Have some crawled data in the system")
    sys.exit(1)