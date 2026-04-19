"""
Unit tests for database manager.
"""

import pytest
import tempfile
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.database.db_manager import DatabaseManager
from src.utils.config import Config


@pytest.fixture
def temp_db_config():
    """Create a temporary database configuration for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test.db")

    # Create a minimal config object
    class MockConfig:
        def __init__(self):
            self.database_url = f"sqlite:///{temp_db_path}"

    config = MockConfig()
    yield config

    # Cleanup
    if Path(temp_db_path).exists():
        Path(temp_db_path).unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
async def db_manager(temp_db_config):
    """Create a database manager instance for testing."""
    manager = DatabaseManager(temp_db_config)
    await manager.initialize()
    yield manager
    await manager.shutdown()


class TestDatabaseManager:
    """Test database manager functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self, temp_db_config):
        """Test database initialization."""
        manager = DatabaseManager(temp_db_config)
        await manager.initialize()

        # Check that database file was created
        db_path = manager.db_path
        assert Path(db_path).exists()

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_store_page(self, db_manager):
        """Test storing page information."""
        page_info = {
            'url': 'https://example.com/test',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Test Page',
            'content': 'This is test content',
            'meta_description': 'Test description',
            'content_type': 'text/html',
            'content_length': 100,
            'crawled_at': 1234567890.0
        }

        # Should not raise an exception
        await db_manager.store_page(page_info)

        # Verify page was stored by checking stats
        stats = await db_manager.get_system_stats()
        assert stats['total_pages'] == 1

    @pytest.mark.asyncio
    async def test_store_duplicate_page(self, db_manager):
        """Test storing duplicate page overwrites existing."""
        page_info = {
            'url': 'https://example.com/test',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Original Title',
            'content': 'Original content',
            'meta_description': '',
            'content_type': 'text/html',
            'content_length': 50,
            'crawled_at': 1234567890.0
        }

        # Store original
        await db_manager.store_page(page_info)

        # Store updated version
        page_info.update({
            'title': 'Updated Title',
            'content': 'Updated content',
            'content_length': 100
        })
        await db_manager.store_page(page_info)

        # Should still have only one page
        stats = await db_manager.get_system_stats()
        assert stats['total_pages'] == 1

    @pytest.mark.asyncio
    async def test_store_error(self, db_manager):
        """Test storing crawl errors."""
        await db_manager.store_error(
            'https://example.com/error',
            'https://example.com',
            1,
            'Connection timeout'
        )

        # Should not raise an exception
        # Error count verification would require additional DB queries

    @pytest.mark.asyncio
    async def test_check_url_visited(self, db_manager):
        """Test checking if URL was visited."""
        test_url = 'https://example.com/test'

        # Should not be visited initially
        assert not await db_manager.is_url_visited(test_url)

        # Store a page
        page_info = {
            'url': test_url,
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Test',
            'content': 'Content',
            'crawled_at': 1234567890.0
        }
        await db_manager.store_page(page_info)

        # Now should be visited
        assert await db_manager.is_url_visited(test_url)

    @pytest.mark.asyncio
    async def test_get_system_stats(self, db_manager):
        """Test getting system statistics."""
        stats = await db_manager.get_system_stats()

        # Should return expected keys
        expected_keys = [
            'total_pages', 'unique_domains', 'index_size',
            'db_size', 'last_crawl', 'uptime'
        ]

        for key in expected_keys:
            assert key in stats

        # Initially should have zero pages
        assert stats['total_pages'] == 0

    @pytest.mark.asyncio
    async def test_get_detailed_stats(self, db_manager):
        """Test getting detailed system statistics."""
        stats = await db_manager.get_detailed_stats()

        # Should include basic stats plus performance info
        assert 'performance' in stats
        assert 'queue_status' in stats

        # Performance should have expected metrics
        assert 'avg_page_size' in stats['performance']
        assert 'crawl_success_rate' in stats['performance']

    @pytest.mark.asyncio
    async def test_search_pages(self, db_manager):
        """Test searching pages by terms."""
        # Store some test pages
        pages = [
            {
                'url': 'https://example.com/python',
                'origin_url': 'https://example.com',
                'depth': 1,
                'title': 'Python Programming',
                'content': 'Learn Python programming language',
                'crawled_at': 1234567890.0
            },
            {
                'url': 'https://example.com/javascript',
                'origin_url': 'https://example.com',
                'depth': 1,
                'title': 'JavaScript Guide',
                'content': 'JavaScript tutorial for beginners',
                'crawled_at': 1234567891.0
            }
        ]

        for page in pages:
            await db_manager.store_page(page)

        # Search for Python
        results = await db_manager.search_pages(['python'], limit=10)

        # Should return results
        assert len(results) > 0

        # Each result should be a tuple with expected format
        for result in results:
            assert len(result) == 4  # url, origin_url, depth, score
            assert isinstance(result[0], str)  # url
            assert isinstance(result[1], str)  # origin_url
            assert isinstance(result[2], int)  # depth
            assert isinstance(result[3], (int, float))  # score

    @pytest.mark.asyncio
    async def test_get_crawl_progress(self, db_manager):
        """Test getting crawl progress information."""
        # Store pages at different depths
        pages = []
        for depth in [0, 1, 1, 2, 2, 2]:
            page = {
                'url': f'https://example.com/page_{len(pages)}',
                'origin_url': 'https://example.com',
                'depth': depth,
                'title': f'Page {len(pages)}',
                'content': 'Test content',
                'crawled_at': 1234567890.0 + len(pages)
            }
            pages.append(page)
            await db_manager.store_page(page)

        # Get progress
        progress = await db_manager.get_crawl_progress('https://example.com')

        # Should include depth information
        assert 'total_pages' in progress
        assert 'by_depth' in progress
        assert progress['total_pages'] == 6

    @pytest.mark.asyncio
    async def test_database_path_extraction(self, temp_db_config):
        """Test database path extraction from URL."""
        manager = DatabaseManager(temp_db_config)

        # Should extract correct path
        expected_path = temp_db_config.database_url.replace("sqlite:///", "")
        assert manager.db_path == expected_path

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, db_manager):
        """Test concurrent database operations."""
        # Create multiple concurrent operations
        tasks = []

        for i in range(5):
            page_info = {
                'url': f'https://example.com/page_{i}',
                'origin_url': 'https://example.com',
                'depth': 1,
                'title': f'Page {i}',
                'content': f'Content {i}',
                'crawled_at': 1234567890.0
            }
            tasks.append(db_manager.store_page(page_info))

        # Wait for all operations to complete
        await asyncio.gather(*tasks)

        # Check that all pages were stored
        stats = await db_manager.get_system_stats()
        assert stats['total_pages'] == 5


class TestDatabaseManagerError:
    """Test database manager error handling."""

    @pytest.mark.asyncio
    async def test_invalid_database_path(self):
        """Test handling of invalid database paths."""
        class InvalidConfig:
            database_url = "invalid://path"

        manager = DatabaseManager(InvalidConfig())

        # Should handle gracefully
        with pytest.raises(Exception):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_store_page_with_missing_fields(self, db_manager):
        """Test storing page with missing required fields."""
        # Missing required fields
        incomplete_page = {
            'url': 'https://example.com/test'
            # Missing origin_url, depth, etc.
        }

        # Should handle missing fields gracefully
        with pytest.raises(Exception):
            await db_manager.store_page(incomplete_page)

    @pytest.mark.asyncio
    async def test_operations_on_uninitialized_db(self, temp_db_config):
        """Test operations on uninitialized database."""
        manager = DatabaseManager(temp_db_config)
        # Don't call initialize()

        # Operations should still work (auto-initialize)
        page_info = {
            'url': 'https://example.com/test',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Test',
            'content': 'Content',
            'crawled_at': 1234567890.0
        }

        # Should initialize automatically or handle gracefully
        await manager.store_page(page_info)


if __name__ == "__main__":
    pytest.main([__file__])