"""
BLG 480E Project 2 - Multi-Agent Web Crawler & Search System

A scalable web crawler and search system developed using multi-agent AI workflow.
Provides real-time web crawling with configurable depth and intelligent search
capabilities with relevance scoring.
"""

__version__ = "1.0.0"
__author__ = "BLG 480E Student"
__description__ = "Multi-Agent Web Crawler & Search System"

# Core components
from .crawler.web_crawler import WebCrawler
from .search.search_engine import SearchEngine
from .database.db_manager import DatabaseManager
from .utils.config import Config

__all__ = [
    "WebCrawler",
    "SearchEngine",
    "DatabaseManager",
    "Config"
]