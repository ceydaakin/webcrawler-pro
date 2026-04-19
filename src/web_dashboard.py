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
    <title>WebCrawler Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --gray-50: #fafafa;
            --gray-100: #f4f4f5;
            --gray-200: #e4e4e7;
            --gray-300: #d4d4d8;
            --gray-400: #a1a1aa;
            --gray-500: #71717a;
            --gray-600: #52525b;
            --gray-700: #3f3f46;
            --gray-800: #27272a;
            --gray-900: #18181b;

            --blue-500: #3b82f6;
            --blue-600: #2563eb;
            --green-500: #10b981;
            --green-600: #059669;
            --purple-500: #8b5cf6;
            --purple-600: #7c3aed;

            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);

            --radius: 12px;
            --radius-sm: 8px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--gray-50);
            color: var(--gray-900);
            line-height: 1.5;
            font-weight: 400;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px 24px;
        }

        .header {
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 32px;
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 8px;
            letter-spacing: -0.025em;
        }

        .header p {
            font-size: 16px;
            color: var(--gray-500);
            font-weight: 400;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
            margin-bottom: 40px;
        }

        .card {
            background: white;
            border-radius: var(--radius);
            padding: 24px;
            border: 1px solid var(--gray-200);
            transition: all 0.2s ease;
        }

        .card:hover {
            border-color: var(--gray-300);
            box-shadow: var(--shadow-md);
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }

        .card h3 {
            font-size: 16px;
            font-weight: 600;
            color: var(--gray-900);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .icon {
            width: 16px;
            height: 16px;
            opacity: 0.6;
        }

        .status-grid {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--gray-100);
        }

        .status-item:last-child {
            border-bottom: none;
        }

        .status-label {
            font-size: 14px;
            color: var(--gray-600);
            font-weight: 400;
        }

        .status-value {
            font-size: 14px;
            font-weight: 600;
            color: var(--gray-900);
        }

        .status-value.highlight {
            color: var(--blue-600);
        }

        .search-section {
            background: white;
            border-radius: var(--radius);
            padding: 24px;
            border: 1px solid var(--gray-200);
        }

        .search-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
        }

        .search-header h3 {
            font-size: 16px;
            font-weight: 600;
            color: var(--gray-900);
        }

        .search-box {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }

        .search-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid var(--gray-300);
            border-radius: var(--radius-sm);
            font-size: 14px;
            font-family: inherit;
            transition: all 0.2s ease;
            background: var(--gray-50);
        }

        .search-input:focus {
            outline: none;
            border-color: var(--blue-500);
            background: white;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .search-input::placeholder {
            color: var(--gray-400);
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 12px 20px;
            border: none;
            border-radius: var(--radius-sm);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }

        .btn-primary {
            background: var(--blue-600);
            color: white;
        }

        .btn-primary:hover {
            background: var(--blue-700);
            box-shadow: var(--shadow-sm);
        }

        .btn-secondary {
            background: var(--gray-100);
            color: var(--gray-700);
            border: 1px solid var(--gray-200);
        }

        .btn-secondary:hover {
            background: var(--gray-200);
            border-color: var(--gray-300);
        }

        .results-container {
            min-height: 200px;
        }

        .results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        .results-table th {
            text-align: left;
            padding: 12px 16px;
            font-weight: 500;
            color: var(--gray-600);
            border-bottom: 1px solid var(--gray-200);
            background: var(--gray-50);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }

        .results-table th:first-child {
            border-radius: var(--radius-sm) 0 0 0;
        }

        .results-table th:last-child {
            border-radius: 0 var(--radius-sm) 0 0;
        }

        .results-table td {
            padding: 16px;
            border-bottom: 1px solid var(--gray-100);
            vertical-align: top;
        }

        .results-table tr:hover {
            background: var(--gray-50);
        }

        .url-cell {
            max-width: 400px;
        }

        .url-cell a {
            color: var(--blue-600);
            text-decoration: none;
            font-weight: 500;
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .url-cell a:hover {
            color: var(--blue-700);
            text-decoration: underline;
        }

        .origin-cell {
            color: var(--gray-500);
            font-size: 13px;
        }

        .depth-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            background: var(--blue-100);
            color: var(--blue-700);
            border-radius: 50%;
            font-size: 12px;
            font-weight: 600;
        }

        .score-cell {
            font-weight: 600;
            color: var(--green-600);
            font-family: 'SF Mono', Consolas, monospace;
            font-size: 13px;
        }

        .loading {
            text-align: center;
            padding: 48px 24px;
            color: var(--gray-500);
            font-size: 14px;
        }

        .loading-spinner {
            width: 20px;
            height: 20px;
            border: 2px solid var(--gray-200);
            border-top: 2px solid var(--blue-500);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 12px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 48px 24px;
            color: var(--gray-400);
            font-size: 14px;
        }

        .empty-state-icon {
            width: 48px;
            height: 48px;
            margin: 0 auto 16px;
            opacity: 0.3;
        }

        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green-500);
            display: inline-block;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        @media (max-width: 768px) {
            .container {
                padding: 24px 16px;
            }

            .dashboard-grid {
                grid-template-columns: 1fr;
                gap: 16px;
            }

            .search-box {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WebCrawler Pro</h1>
            <p>Multi-Agent Web Crawler & Search System</p>
        </div>

        <div class="dashboard-grid">
            <div class="card">
                <div class="card-header">
                    <h3>
                        <span class="status-indicator"></span>
                        System Status
                    </h3>
                    <button class="btn btn-secondary" onclick="loadSystemStatus()">Refresh</button>
                </div>
                <div class="status-grid" id="system-status">
                    <div class="loading">
                        <div class="loading-spinner"></div>
                        Loading system status...
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3>Performance Metrics</h3>
                    <button class="btn btn-secondary" onclick="loadPerformanceMetrics()">Refresh</button>
                </div>
                <div class="status-grid" id="performance-metrics">
                    <div class="loading">
                        <div class="loading-spinner"></div>
                        Loading performance data...
                    </div>
                </div>
            </div>
        </div>

        <div class="search-section">
            <div class="search-header">
                <h3>Search Indexed Content</h3>
            </div>
            <div class="search-box">
                <input type="text" id="search-query" class="search-input" placeholder="Search your crawled content..." onkeypress="handleEnter(event)">
                <button class="btn btn-primary" onclick="performSearch()">Search</button>
            </div>
            <div class="results-container" id="search-results">
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    Enter a search query above to find relevant content
                </div>
            </div>
        </div>
    </div>

    <script>
        // Load system status
        async function loadSystemStatus() {
            const statusDiv = document.getElementById('system-status');
            statusDiv.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    Loading...
                </div>
            `;

            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                const statusItems = [
                    { key: 'total_pages', label: 'Total Pages Crawled', highlight: true },
                    { key: 'unique_domains', label: 'Unique Domains' },
                    { key: 'index_size', label: 'Index Size' },
                    { key: 'db_size', label: 'Database Size' },
                    { key: 'last_crawl', label: 'Last Crawl' },
                    { key: 'uptime', label: 'System Uptime' }
                ];

                const html = statusItems
                    .filter(item => data[item.key] !== undefined)
                    .map(item => `
                        <div class="status-item">
                            <span class="status-label">${item.label}</span>
                            <span class="status-value ${item.highlight ? 'highlight' : ''}">${data[item.key]}</span>
                        </div>
                    `).join('');

                statusDiv.innerHTML = html || '<div class="empty-state">No status data available</div>';
            } catch (error) {
                statusDiv.innerHTML = '<div class="empty-state" style="color: var(--red-500);">Error loading status data</div>';
            }
        }

        // Load performance metrics
        async function loadPerformanceMetrics() {
            const metricsDiv = document.getElementById('performance-metrics');
            metricsDiv.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    Loading...
                </div>
            `;

            try {
                const response = await fetch('/api/performance');
                const data = await response.json();

                const metricItems = [
                    { key: 'avg_page_size', label: 'Avg Page Size' },
                    { key: 'crawl_success_rate', label: 'Success Rate', suffix: '%' },
                    { key: 'pages_per_domain', label: 'Pages Per Domain' },
                    { key: 'avg_depth', label: 'Average Depth' }
                ];

                const html = metricItems
                    .filter(item => data[item.key] !== undefined)
                    .map(item => `
                        <div class="status-item">
                            <span class="status-label">${item.label}</span>
                            <span class="status-value">${data[item.key]}${item.suffix || ''}</span>
                        </div>
                    `).join('');

                metricsDiv.innerHTML = html || '<div class="empty-state">No performance data available</div>';
            } catch (error) {
                metricsDiv.innerHTML = '<div class="empty-state" style="color: var(--red-500);">Error loading performance data</div>';
            }
        }

        // Perform search
        async function performSearch() {
            const query = document.getElementById('search-query').value.trim();
            if (!query) return;

            const resultsDiv = document.getElementById('search-results');
            resultsDiv.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    Searching for "${query}"...
                </div>
            `;

            try {
                const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
                const results = await response.json();

                if (results.length === 0) {
                    resultsDiv.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">🔍</div>
                            No results found for "${query}"
                        </div>
                    `;
                    return;
                }

                const tableHtml = `
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>URL</th>
                                <th>Origin</th>
                                <th>Depth</th>
                                <th>Relevance</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${results.map(result => `
                                <tr>
                                    <td class="url-cell">
                                        <a href="${result.url}" target="_blank">${result.url}</a>
                                    </td>
                                    <td class="origin-cell">${result.origin}</td>
                                    <td>
                                        <span class="depth-badge">${result.depth}</span>
                                    </td>
                                    <td class="score-cell">${result.score.toFixed(3)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;

                resultsDiv.innerHTML = tableHtml;
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

    site = web.TCPSite(runner, '127.0.0.1', 8888)
    await site.start()

    print("🌐 WebCrawler Pro Dashboard running at: http://127.0.0.1:8888")
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