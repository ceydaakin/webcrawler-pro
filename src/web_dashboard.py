#!/usr/bin/env python3
"""
Simple Web Dashboard for WebCrawler Pro
Provides a browser-based interface to view system status and search results.
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import aiohttp
from aiohttp import web, web_request
import aiohttp_cors
import asyncio
import logging

# Import our components
from .database.db_manager import DatabaseManager
from .search.search_engine import SearchEngine
from .utils.config import Config

class WebDashboard:
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = Config.load(config_path)
        self.db_manager = None
        self.search_engine = None

    async def initialize(self):
        """Initialize database and search components"""
        self.db_manager = DatabaseManager(self.config.database)
        await self.db_manager.initialize()

        self.search_engine = SearchEngine(self.config.search, self.db_manager)
        await self.search_engine.initialize()

    async def shutdown(self):
        """Clean shutdown"""
        if self.search_engine:
            await self.search_engine.shutdown()
        if self.db_manager:
            await self.db_manager.shutdown()

    async def index_handler(self, request):
        """Serve the main dashboard HTML"""
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebCrawler Pro Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }

        .header h1 {
            color: #4a5568;
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            color: #718096;
            font-size: 1.2em;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .card h3 {
            color: #4a5568;
            margin-bottom: 15px;
            font-size: 1.3em;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e2e8f0;
        }

        .status-value {
            font-weight: bold;
            color: #38a169;
        }

        .search-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        .search-input {
            flex: 1;
            padding: 10px;
            border: 2px solid #e2e8f0;
            border-radius: 5px;
            font-size: 16px;
        }

        .search-btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }

        .search-btn:hover {
            background: #5a67d8;
        }

        .results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }

        .results-table th,
        .results-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        .results-table th {
            background: #f7fafc;
            font-weight: bold;
            color: #4a5568;
        }

        .url-cell {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .score {
            font-weight: bold;
            color: #38a169;
        }

        .refresh-btn {
            padding: 8px 15px;
            background: #48bb78;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-left: 10px;
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: #718096;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕷️ WebCrawler Pro Dashboard</h1>
            <p>BLG 480E Project 2 - Multi-Agent Web Crawler & Search System</p>
        </div>

        <div class="dashboard-grid">
            <div class="card">
                <h3>📊 System Status</h3>
                <div id="system-status">
                    <div class="loading">Loading...</div>
                </div>
                <button class="refresh-btn" onclick="loadSystemStatus()">🔄 Refresh</button>
            </div>

            <div class="card">
                <h3>⚡ Performance Metrics</h3>
                <div id="performance-metrics">
                    <div class="loading">Loading...</div>
                </div>
                <button class="refresh-btn" onclick="loadPerformanceMetrics()">🔄 Refresh</button>
            </div>
        </div>

        <div class="search-section">
            <h3>🔍 Search Indexed Content</h3>
            <div class="search-box">
                <input type="text" id="search-query" class="search-input" placeholder="Enter search query..." onkeypress="handleEnter(event)">
                <button class="search-btn" onclick="performSearch()">Search</button>
            </div>
            <div id="search-results"></div>
        </div>
    </div>

    <script>
        // Load system status
        async function loadSystemStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                const html = Object.entries(data)
                    .map(([key, value]) => `
                        <div class="status-item">
                            <span>${key.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())}</span>
                            <span class="status-value">${value}</span>
                        </div>
                    `).join('');

                document.getElementById('system-status').innerHTML = html;
            } catch (error) {
                document.getElementById('system-status').innerHTML = '<div style="color: red;">Error loading status</div>';
            }
        }

        // Load performance metrics
        async function loadPerformanceMetrics() {
            try {
                const response = await fetch('/api/performance');
                const data = await response.json();

                const html = Object.entries(data)
                    .map(([key, value]) => `
                        <div class="status-item">
                            <span>${key.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())}</span>
                            <span class="status-value">${value}</span>
                        </div>
                    `).join('');

                document.getElementById('performance-metrics').innerHTML = html;
            } catch (error) {
                document.getElementById('performance-metrics').innerHTML = '<div style="color: red;">Error loading metrics</div>';
            }
        }

        // Perform search
        async function performSearch() {
            const query = document.getElementById('search-query').value.trim();
            if (!query) return;

            document.getElementById('search-results').innerHTML = '<div class="loading">Searching...</div>';

            try {
                const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
                const results = await response.json();

                if (results.length === 0) {
                    document.getElementById('search-results').innerHTML = '<div>No results found.</div>';
                    return;
                }

                const tableHtml = `
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>URL</th>
                                <th>Origin</th>
                                <th>Depth</th>
                                <th>Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${results.map(result => `
                                <tr>
                                    <td class="url-cell"><a href="${result.url}" target="_blank">${result.url}</a></td>
                                    <td>${result.origin}</td>
                                    <td>${result.depth}</td>
                                    <td class="score">${result.score.toFixed(3)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;

                document.getElementById('search-results').innerHTML = tableHtml;
            } catch (error) {
                document.getElementById('search-results').innerHTML = '<div style="color: red;">Error performing search</div>';
            }
        }

        // Handle Enter key in search box
        function handleEnter(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        }

        // Auto-load data on page load
        window.onload = function() {
            loadSystemStatus();
            loadPerformanceMetrics();
        };

        // Auto-refresh every 30 seconds
        setInterval(() => {
            loadSystemStatus();
            loadPerformanceMetrics();
        }, 30000);
    </script>
</body>
</html>
        """
        return web.Response(text=html_content, content_type='text/html')

    async def status_api(self, request):
        """API endpoint for system status"""
        try:
            stats = await self.db_manager.get_system_stats()
            return web.json_response(stats)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def performance_api(self, request):
        """API endpoint for performance metrics"""
        try:
            stats = await self.db_manager.get_detailed_stats()
            return web.json_response(stats.get('performance', {}))
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def search_api(self, request):
        """API endpoint for search functionality"""
        try:
            query = request.query.get('query', '')
            if not query:
                return web.json_response({'error': 'Query parameter required'}, status=400)

            results = await self.search_engine.search(query, 20)

            # Convert results to JSON format
            json_results = [
                {
                    'url': url,
                    'origin': origin,
                    'depth': depth,
                    'score': score
                }
                for url, origin, depth, score in results
            ]

            return web.json_response(json_results)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

async def create_app():
    """Create and configure the web application"""
    dashboard = WebDashboard()
    await dashboard.initialize()

    app = web.Application()

    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })

    # Routes
    app.router.add_get('/', dashboard.index_handler)
    app.router.add_get('/api/status', dashboard.status_api)
    app.router.add_get('/api/performance', dashboard.performance_api)
    app.router.add_get('/api/search', dashboard.search_api)

    # Add CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    return app

async def run_server():
    """Run the web dashboard server"""
    app = await create_app()

    # Configure and start server
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, '127.0.0.1', 8080)
    await site.start()

    print("🌐 WebCrawler Pro Dashboard running at: http://127.0.0.1:8080")
    print("📊 Features: Real-time status, performance metrics, search interface")
    print("🔄 Auto-refresh: Status updates every 30 seconds")
    print("⏹️  Press Ctrl+C to stop the server")

    # Keep server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(run_server())