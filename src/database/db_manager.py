"""
Database Manager for Web Crawler and Search System
Handles data persistence, retrieval, and database operations.
"""

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

import aiosqlite


class DatabaseManager:
    """
    Manages database operations for the web crawler and search system.
    """

    def __init__(self, config):
        """
        Initialize the database manager.

        Args:
            config: Database configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db_path = self._extract_db_path(config.database_url)

        # Connection management
        self._connection_pool = None
        self._initialized = False

    async def initialize(self):
        """Initialize the database and create necessary tables."""
        if self._initialized:
            return

        self.logger.info("Initializing database")

        # Ensure database directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create tables
            await self._create_tables()
            self._initialized = True
            self.logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    async def shutdown(self):
        """Shutdown the database manager and close connections."""
        if self._connection_pool:
            # Close any open connections
            pass

        self.logger.info("Database manager shutdown complete")

    async def store_page(self, page_info: Dict) -> None:
        """
        Store crawled page information in the database.

        Args:
            page_info: Dictionary containing page information
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO crawled_pages
                    (url, origin_url, depth, title, content, meta_description,
                     content_type, content_length, crawled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    page_info['url'],
                    page_info['origin_url'],
                    page_info['depth'],
                    page_info.get('title', ''),
                    page_info.get('content', ''),
                    page_info.get('meta_description', ''),
                    page_info.get('content_type', ''),
                    page_info.get('content_length', 0),
                    page_info.get('crawled_at', time.time())
                ))
                await db.commit()

            self.logger.debug(f"Stored page: {page_info['url']}")

        except Exception as e:
            self.logger.error(f"Error storing page {page_info['url']}: {e}")
            raise

    async def store_error(self, url: str, origin_url: str, depth: int, error_message: str) -> None:
        """
        Store crawling error information.

        Args:
            url: URL that failed to crawl
            origin_url: Origin URL for tracking
            depth: Crawl depth
            error_message: Error description
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO crawl_errors
                    (url, origin_url, depth, error_message, error_time)
                    VALUES (?, ?, ?, ?, ?)
                ''', (url, origin_url, depth, error_message, time.time()))
                await db.commit()

        except Exception as e:
            self.logger.error(f"Error storing crawl error for {url}: {e}")

    async def get_document_info(self, doc_id: str) -> Optional[Dict]:
        """
        Get document information by ID.

        Args:
            doc_id: Document identifier (URL)

        Returns:
            Dictionary with document information or None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT url, origin_url, depth, title, content,
                           meta_description, content_type, crawled_at
                    FROM crawled_pages
                    WHERE url = ?
                ''', (doc_id,)) as cursor:
                    row = await cursor.fetchone()

                    if row:
                        return {
                            'url': row['url'],
                            'origin_url': row['origin_url'],
                            'depth': row['depth'],
                            'title': row['title'],
                            'content': row['content'],
                            'meta_description': row['meta_description'],
                            'content_type': row['content_type'],
                            'crawled_at': row['crawled_at']
                        }

        except Exception as e:
            self.logger.error(f"Error retrieving document {doc_id}: {e}")

        return None

    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics.

        Returns:
            Dictionary with system statistics
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total pages crawled
                async with db.execute('SELECT COUNT(*) FROM crawled_pages') as cursor:
                    total_pages = (await cursor.fetchone())[0]

                # Unique domains - simpler approach
                async with db.execute('''
                    SELECT COUNT(DISTINCT
                        CASE
                            WHEN url LIKE 'https://%' THEN
                                substr(url, 9,
                                    CASE
                                        WHEN instr(substr(url, 9), '/') > 0
                                        THEN instr(substr(url, 9), '/') - 1
                                        ELSE length(substr(url, 9))
                                    END)
                            WHEN url LIKE 'http://%' THEN
                                substr(url, 8,
                                    CASE
                                        WHEN instr(substr(url, 8), '/') > 0
                                        THEN instr(substr(url, 8), '/') - 1
                                        ELSE length(substr(url, 8))
                                    END)
                            ELSE 'unknown'
                        END
                    )
                    FROM crawled_pages
                ''') as cursor:
                    unique_domains = (await cursor.fetchone())[0]

                # Last crawl time
                async with db.execute('''
                    SELECT MAX(crawled_at) FROM crawled_pages
                ''') as cursor:
                    last_crawl_timestamp = (await cursor.fetchone())[0]

                last_crawl = 'Never'
                if last_crawl_timestamp:
                    last_crawl_time = time.time() - last_crawl_timestamp
                    if last_crawl_time < 3600:
                        last_crawl = f"{int(last_crawl_time / 60)} minutes ago"
                    elif last_crawl_time < 86400:
                        last_crawl = f"{int(last_crawl_time / 3600)} hours ago"
                    else:
                        last_crawl = f"{int(last_crawl_time / 86400)} days ago"

                # Database size (approximate)
                db_size = Path(self.db_path).stat().st_size / (1024 * 1024) if Path(self.db_path).exists() else 0

                return {
                    'total_pages': total_pages,
                    'unique_domains': unique_domains,
                    'index_size': total_pages,  # Simplified
                    'db_size': round(db_size, 2),
                    'last_crawl': last_crawl,
                    'uptime': 'Active'
                }

        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            return {
                'total_pages': 0,
                'unique_domains': 0,
                'index_size': 0,
                'db_size': 0,
                'last_crawl': 'Error',
                'uptime': 'Error'
            }

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Get detailed system statistics.

        Returns:
            Dictionary with detailed statistics
        """
        basic_stats = await self.get_system_stats()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Performance metrics (simplified)
                performance = {
                    'avg_page_size': 0,
                    'crawl_success_rate': 100,
                    'pages_per_domain': 0,
                    'avg_depth': 0
                }

                # Average page size
                async with db.execute('''
                    SELECT AVG(content_length) FROM crawled_pages WHERE content_length > 0
                ''') as cursor:
                    avg_size = (await cursor.fetchone())[0]
                    performance['avg_page_size'] = round(avg_size or 0)

                # Average depth
                async with db.execute('SELECT AVG(depth) FROM crawled_pages') as cursor:
                    avg_depth = (await cursor.fetchone())[0]
                    performance['avg_depth'] = round(avg_depth or 0, 2)

                # Queue status (placeholder)
                queue_status = [
                    {
                        'name': 'crawl_queue',
                        'depth': 'mixed',
                        'pending': 0
                    }
                ]

                return {
                    **basic_stats,
                    'performance': performance,
                    'queue_status': queue_status
                }

        except Exception as e:
            self.logger.error(f"Error getting detailed stats: {e}")
            return basic_stats

    async def search_pages(self, query_terms: List[str], limit: int = 50) -> List[Tuple[str, str, int, float]]:
        """
        Search pages for matching content.

        Args:
            query_terms: List of search terms
            limit: Maximum number of results

        Returns:
            List of tuples: (url, origin_url, depth, score)
        """
        if not query_terms:
            return []

        try:
            # Simple text matching search (could be improved with FTS)
            search_pattern = ' '.join(query_terms).lower()

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                query = '''
                    SELECT url, origin_url, depth, title, content,
                           CASE
                               WHEN LOWER(title) LIKE ? THEN 3.0
                               WHEN LOWER(content) LIKE ? THEN 1.0
                               ELSE 0.1
                           END as relevance_score
                    FROM crawled_pages
                    WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ?
                    ORDER BY relevance_score DESC, crawled_at DESC
                    LIMIT ?
                '''

                pattern = f'%{search_pattern}%'
                async with db.execute(query, (pattern, pattern, pattern, pattern, limit)) as cursor:
                    results = []
                    async for row in cursor:
                        results.append((
                            row['url'],
                            row['origin_url'],
                            row['depth'],
                            row['relevance_score']
                        ))

                    return results

        except Exception as e:
            self.logger.error(f"Error searching pages: {e}")
            return []

    async def _create_tables(self):
        """Create necessary database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Crawled pages table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS crawled_pages (
                    url TEXT PRIMARY KEY,
                    origin_url TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    title TEXT,
                    content TEXT,
                    meta_description TEXT,
                    content_type TEXT,
                    content_length INTEGER,
                    crawled_at REAL NOT NULL,
                    FOREIGN KEY (origin_url) REFERENCES crawled_pages (url)
                )
            ''')

            # Create indexes for performance
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_crawled_pages_origin
                ON crawled_pages(origin_url)
            ''')

            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_crawled_pages_depth
                ON crawled_pages(depth)
            ''')

            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_crawled_pages_crawled_at
                ON crawled_pages(crawled_at)
            ''')

            # Crawl errors table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS crawl_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    origin_url TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    error_message TEXT NOT NULL,
                    error_time REAL NOT NULL
                )
            ''')

            # Search index table (for persistent search index)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS search_index (
                    term TEXT NOT NULL,
                    document_url TEXT NOT NULL,
                    tf_score REAL NOT NULL,
                    PRIMARY KEY (term, document_url),
                    FOREIGN KEY (document_url) REFERENCES crawled_pages (url)
                )
            ''')

            # System metadata table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS system_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL NOT NULL
                )
            ''')

            await db.commit()

    async def _execute_query(self, query: str, params=None):
        """
        Execute a query and return all results.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of rows from the query result
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if params:
                    async with db.execute(query, params) as cursor:
                        return await cursor.fetchall()
                else:
                    async with db.execute(query) as cursor:
                        return await cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Database query error: {e}")
            return []

    async def bulk_insert_search_terms(self, terms_data: List[Tuple[str, str, float]]):
        """
        Bulk insert search index terms.

        Args:
            terms_data: List of (term, document_url, tf_score) tuples
        """
        if not terms_data:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany(
                    "INSERT OR REPLACE INTO search_index (term, document_url, tf_score) VALUES (?, ?, ?)",
                    terms_data
                )
                await db.commit()
                self.logger.debug(f"Bulk inserted {len(terms_data)} search index terms")
        except Exception as e:
            self.logger.error(f"Error bulk inserting search terms: {e}")

    async def delete_search_terms(self, document_url: str):
        """
        Delete all search index terms for a document.

        Args:
            document_url: Document URL to delete terms for
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM search_index WHERE document_url = ?", (document_url,))
                await db.commit()
                self.logger.debug(f"Deleted search terms for document: {document_url}")
        except Exception as e:
            self.logger.error(f"Error deleting search terms for {document_url}: {e}")

    def _extract_db_path(self, database_url: str) -> str:
        """Extract file path from database URL."""
        if database_url.startswith('sqlite:///'):
            return database_url[10:]  # Remove 'sqlite:///'
        elif database_url.startswith('sqlite://'):
            return database_url[9:]   # Remove 'sqlite://'
        else:
            # Default fallback
            return 'data/webcrawler.db'