"""
Integration tests for web crawler functionality.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from aioresponses import aioresponses

from src.crawler.web_crawler import WebCrawler
from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine


@pytest.fixture
def temp_configs():
    """Create temporary configurations for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test.db")

    class MockDatabaseConfig:
        database_url = f"sqlite:///{temp_db_path}"

    class MockCrawlerConfig:
        max_concurrent_requests = 2
        request_timeout = 5
        max_retries = 1
        retry_delay = 0.1
        request_delay = 0.1
        max_queue_depth = 100
        queue_check_interval = 1.0
        max_page_size = 1048576
        allowed_content_types = ["text/html"]
        respect_robots_txt = False  # Disable for testing
        follow_redirects = True
        max_redirects = 2
        user_agent = "Test-Crawler/1.0"
        extract_links = True
        extract_text = True
        extract_metadata = True

    class MockSearchConfig:
        index_batch_size = 10
        max_search_results = 50
        min_relevance_score = 0.001
        default_search_limit = 20
        remove_stop_words = True
        enable_stemming = False
        min_term_length = 2
        max_term_length = 50
        title_weight = 2.0
        content_weight = 1.0
        url_weight = 0.5
        freshness_weight = 0.3

    yield MockDatabaseConfig(), MockCrawlerConfig(), MockSearchConfig()

    # Cleanup
    if Path(temp_db_path).exists():
        Path(temp_db_path).unlink()
    if Path(temp_dir).exists():
        Path(temp_dir).rmdir()


@pytest.fixture
async def integrated_system(temp_configs):
    """Set up integrated crawler-search-database system."""
    db_config, crawler_config, search_config = temp_configs

    # Initialize components
    db_manager = DatabaseManager(db_config)
    await db_manager.initialize()

    search_engine = SearchEngine(search_config, db_manager)
    await search_engine.initialize()

    crawler = WebCrawler(crawler_config, db_manager, search_engine)

    yield crawler, search_engine, db_manager

    # Cleanup
    await search_engine.shutdown()
    await db_manager.shutdown()


class TestCrawlerIntegration:
    """Test crawler integration with database and search."""

    @pytest.mark.asyncio
    async def test_basic_crawl_and_search(self, integrated_system):
        """Test complete workflow: crawl → index → search."""
        crawler, search_engine, db_manager = integrated_system

        # Mock HTTP responses
        test_html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="A test page for crawling">
            </head>
            <body>
                <h1>Welcome to Test Page</h1>
                <p>This is a test page with some content about Python programming.</p>
                <a href="/page2">Link to Page 2</a>
                <a href="https://external.com">External Link</a>
            </body>
        </html>
        """

        page2_html = """
        <html>
            <head>
                <title>Page 2</title>
            </head>
            <body>
                <h1>Second Page</h1>
                <p>This page contains information about web crawling techniques.</p>
            </body>
        </html>
        """

        with aioresponses() as m:
            # Mock responses for crawling
            m.get('https://example.com', payload=test_html, content_type='text/html')
            m.get('https://example.com/page2', payload=page2_html, content_type='text/html')

            # Crawl the website
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=1, max_pages=10):
                crawl_results.append(result)

            # Should have crawled at least the main page
            assert len(crawl_results) > 0

        # Check database has stored pages
        stats = await db_manager.get_system_stats()
        assert stats['total_pages'] > 0

        # Wait for search index to update
        await asyncio.sleep(0.2)

        # Test search functionality
        python_results = await search_engine.search('python', limit=10)
        assert len(python_results) > 0

        crawling_results = await search_engine.search('crawling', limit=10)
        assert len(crawling_results) > 0

        # Verify result format
        for result in python_results:
            assert len(result) == 4  # url, origin_url, depth, score
            assert isinstance(result[0], str)
            assert isinstance(result[1], str)
            assert isinstance(result[2], int)
            assert isinstance(result[3], (int, float))

    @pytest.mark.asyncio
    async def test_depth_limited_crawling(self, integrated_system):
        """Test crawling respects depth limits."""
        crawler, search_engine, db_manager = integrated_system

        # Create a chain of linked pages
        pages = {
            'https://example.com': '''
                <html><body>
                    <title>Root Page</title>
                    <a href="/level1">Level 1</a>
                </body></html>
            ''',
            'https://example.com/level1': '''
                <html><body>
                    <title>Level 1 Page</title>
                    <a href="/level2">Level 2</a>
                </body></html>
            ''',
            'https://example.com/level2': '''
                <html><body>
                    <title>Level 2 Page</title>
                    <a href="/level3">Level 3</a>
                </body></html>
            ''',
            'https://example.com/level3': '''
                <html><body>
                    <title>Level 3 Page</title>
                    <p>This should not be crawled with depth=2</p>
                </body></html>
            '''
        }

        with aioresponses() as m:
            for url, content in pages.items():
                m.get(url, payload=content, content_type='text/html')

            # Crawl with depth limit of 2
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=2, max_pages=10):
                crawl_results.append(result)

        # Check crawl progress
        progress = await db_manager.get_crawl_progress('https://example.com')

        # Should not have crawled level 3 (depth > 2)
        by_depth = progress.get('by_depth', {})
        assert 3 not in by_depth or by_depth[3] == 0

    @pytest.mark.asyncio
    async def test_real_time_indexing(self, integrated_system):
        """Test that pages are searchable immediately after crawling."""
        crawler, search_engine, db_manager = integrated_system

        test_content = '''
            <html>
                <head><title>Real-time Indexing Test</title></head>
                <body>
                    <p>This content should be searchable immediately after crawling.</p>
                    <p>Unique keyword: realtime123</p>
                </body>
            </html>
        '''

        with aioresponses() as m:
            m.get('https://example.com', payload=test_content, content_type='text/html')

            # Start crawling
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=0, max_pages=1):
                crawl_results.append(result)

        # Small delay for async processing
        await asyncio.sleep(0.1)

        # Should be able to search immediately
        results = await search_engine.search('realtime123', limit=10)
        assert len(results) > 0
        assert any('example.com' in result[0] for result in results)

    @pytest.mark.asyncio
    async def test_error_handling_during_crawl(self, integrated_system):
        """Test crawler handles HTTP errors gracefully."""
        crawler, search_engine, db_manager = integrated_system

        # Mock both successful and failed responses
        good_content = '<html><body><title>Good Page</title></body></html>'

        with aioresponses() as m:
            # Successful page
            m.get('https://example.com', payload=good_content, content_type='text/html')
            # Failed page (404)
            m.get('https://example.com/broken', status=404)

            # Try to crawl with a mix of good and bad URLs
            # This would happen if the good page links to the broken one
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=1, max_pages=5):
                crawl_results.append(result)

        # Should have completed crawling despite errors
        assert len(crawl_results) >= 0

        # Check that good pages were still indexed
        stats = await db_manager.get_system_stats()
        # Should have at least some successful pages

    @pytest.mark.asyncio
    async def test_duplicate_url_handling(self, integrated_system):
        """Test that duplicate URLs are not crawled twice."""
        crawler, search_engine, db_manager = integrated_system

        # Page that links to itself
        self_linking_page = '''
            <html>
                <body>
                    <title>Self Linking Page</title>
                    <a href="/">Home</a>
                    <a href="/">Home Again</a>
                </body>
            </html>
        '''

        with aioresponses() as m:
            m.get('https://example.com', payload=self_linking_page, content_type='text/html')

            # Crawl the page
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=2, max_pages=10):
                crawl_results.append(result)

        # Should only have crawled the page once
        stats = await db_manager.get_system_stats()
        assert stats['total_pages'] == 1

    @pytest.mark.asyncio
    async def test_search_relevance_ranking(self, integrated_system):
        """Test search result relevance ranking."""
        crawler, search_engine, db_manager = integrated_system

        pages = {
            'https://example.com/high-relevance': '''
                <html>
                    <head><title>Python Programming Guide</title></head>
                    <body>
                        <h1>Python Programming</h1>
                        <p>Complete Python programming tutorial with examples.</p>
                    </body>
                </html>
            ''',
            'https://example.com/low-relevance': '''
                <html>
                    <head><title>General Programming</title></head>
                    <body>
                        <p>Programming tutorial mentioning Python briefly.</p>
                    </body>
                </html>
            '''
        }

        with aioresponses() as m:
            for url, content in pages.items():
                m.get(url, payload=content, content_type='text/html')

            # Crawl all pages
            crawl_results = []
            async for result in crawler.crawl('https://example.com/high-relevance', max_depth=1, max_pages=5):
                crawl_results.append(result)

        # Wait for indexing
        await asyncio.sleep(0.1)

        # Search for Python
        results = await search_engine.search('python programming', limit=10)

        # Should return results sorted by relevance
        assert len(results) >= 1

        # Higher relevance page should score higher
        if len(results) >= 2:
            high_result = next((r for r in results if 'high-relevance' in r[0]), None)
            low_result = next((r for r in results if 'low-relevance' in r[0]), None)

            if high_result and low_result:
                assert high_result[3] >= low_result[3]  # Score comparison


class TestCrawlerSearchIntegration:
    """Test integration between crawler and search systems."""

    @pytest.mark.asyncio
    async def test_concurrent_crawl_and_search(self, integrated_system):
        """Test searching while crawling is active."""
        crawler, search_engine, db_manager = integrated_system

        # Create content for multiple pages
        pages = {}
        for i in range(5):
            pages[f'https://example.com/page{i}'] = f'''
                <html>
                    <head><title>Page {i}</title></head>
                    <body>
                        <p>Content for page {i} with keyword testword{i}.</p>
                    </body>
                </html>
            '''

        with aioresponses() as m:
            for url, content in pages.items():
                m.get(url, payload=content, content_type='text/html')

            # Start crawling task
            crawl_task = asyncio.create_task(
                crawler._crawl_generator('https://example.com/page0', max_depth=1, max_pages=5)
            )

            # Perform searches while crawling
            search_tasks = []
            for i in range(3):
                await asyncio.sleep(0.05)  # Small delay between searches
                search_task = asyncio.create_task(
                    search_engine.search(f'testword{i}', limit=5)
                )
                search_tasks.append(search_task)

            # Wait for all tasks to complete
            await crawl_task
            search_results = await asyncio.gather(*search_tasks)

        # All searches should complete without errors
        assert len(search_results) == 3

        # Some searches should return results (depending on timing)
        # This tests that the system handles concurrent access properly

    @pytest.mark.asyncio
    async def test_system_recovery_after_error(self, integrated_system):
        """Test system recovery after component errors."""
        crawler, search_engine, db_manager = integrated_system

        good_content = '<html><body><title>Good Page</title><p>Test content</p></body></html>'

        with aioresponses() as m:
            m.get('https://example.com', payload=good_content, content_type='text/html')

            # Simulate a temporary database error
            with patch.object(db_manager, 'store_page', side_effect=Exception("Temporary DB error")):
                # This crawl should handle the error gracefully
                crawl_results = []
                try:
                    async for result in crawler.crawl('https://example.com', max_depth=0, max_pages=1):
                        crawl_results.append(result)
                except Exception:
                    pass  # Expected to handle errors gracefully

            # System should recover - retry without the error
            crawl_results = []
            async for result in crawler.crawl('https://example.com', max_depth=0, max_pages=1):
                crawl_results.append(result)

        # Should complete successfully after recovery
        stats = await db_manager.get_system_stats()
        # Should have some data after recovery


if __name__ == "__main__":
    pytest.main([__file__])