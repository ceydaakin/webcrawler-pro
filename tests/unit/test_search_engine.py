"""
Unit tests for search engine.
"""

import pytest
import tempfile
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.search.search_engine import SearchEngine
from src.database.db_manager import DatabaseManager


@pytest.fixture
def temp_db_config():
    """Create a temporary database configuration for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test.db")

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
def search_config():
    """Create search engine configuration for testing."""
    class MockSearchConfig:
        def __init__(self):
            self.index_batch_size = 10
            self.max_search_results = 50
            self.min_relevance_score = 0.001
            self.default_search_limit = 20
            self.remove_stop_words = True
            self.enable_stemming = False  # Disable for simpler testing
            self.min_term_length = 2
            self.max_term_length = 50
            self.title_weight = 2.0
            self.content_weight = 1.0
            self.url_weight = 0.5
            self.freshness_weight = 0.3

    return MockSearchConfig()


@pytest.fixture
async def setup_search_engine(temp_db_config, search_config):
    """Set up a search engine with database for testing."""
    db_manager = DatabaseManager(temp_db_config)
    await db_manager.initialize()

    search_engine = SearchEngine(search_config, db_manager)
    await search_engine.initialize()

    yield search_engine, db_manager

    await search_engine.shutdown()
    await db_manager.shutdown()


class TestSearchEngine:
    """Test search engine functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self, temp_db_config, search_config):
        """Test search engine initialization."""
        db_manager = DatabaseManager(temp_db_config)
        await db_manager.initialize()

        search_engine = SearchEngine(search_config, db_manager)
        await search_engine.initialize()

        # Should initialize without errors
        assert search_engine.document_count == 0
        assert len(search_engine.inverted_index) == 0

        await search_engine.shutdown()
        await db_manager.shutdown()

    @pytest.mark.asyncio
    async def test_index_document(self, setup_search_engine):
        """Test indexing a single document."""
        search_engine, db_manager = setup_search_engine

        # Index a document
        doc_info = {
            'url': 'https://example.com/test',
            'title': 'Python Programming',
            'content': 'Learn Python programming language basics',
            'crawled_at': 1234567890.0
        }

        await search_engine.index_document(doc_info)

        # Check that document was indexed
        assert search_engine.document_count == 1
        assert 'python' in search_engine.inverted_index
        assert 'programming' in search_engine.inverted_index

    @pytest.mark.asyncio
    async def test_search_basic(self, setup_search_engine):
        """Test basic search functionality."""
        search_engine, db_manager = setup_search_engine

        # Index some test documents
        docs = [
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

        for doc in docs:
            await db_manager.store_page(doc)
            await search_engine.index_document(doc)

        # Search for Python
        results = await search_engine.search('python', limit=10)

        # Should return relevant results
        assert len(results) > 0
        assert any('python' in result[0] for result in results)

        # Each result should be a tuple with expected format
        for result in results:
            assert len(result) == 4  # url, origin_url, depth, score
            assert isinstance(result[0], str)  # url
            assert isinstance(result[1], str)  # origin_url
            assert isinstance(result[2], int)  # depth
            assert isinstance(result[3], (int, float))  # score

    @pytest.mark.asyncio
    async def test_search_multiple_terms(self, setup_search_engine):
        """Test search with multiple terms."""
        search_engine, db_manager = setup_search_engine

        # Index a document with multiple relevant terms
        doc = {
            'url': 'https://example.com/tutorial',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Python Programming Tutorial',
            'content': 'Complete Python programming tutorial for beginners',
            'crawled_at': 1234567890.0
        }

        await db_manager.store_page(doc)
        await search_engine.index_document(doc)

        # Search for multiple terms
        results = await search_engine.search('python tutorial', limit=10)

        # Should return the document with higher score
        assert len(results) > 0
        assert results[0][0] == doc['url']  # Should be top result

    @pytest.mark.asyncio
    async def test_search_no_results(self, setup_search_engine):
        """Test search with no matching results."""
        search_engine, db_manager = setup_search_engine

        # Index a document
        doc = {
            'url': 'https://example.com/test',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'Test Document',
            'content': 'This is a test document',
            'crawled_at': 1234567890.0
        }

        await db_manager.store_page(doc)
        await search_engine.index_document(doc)

        # Search for non-existent term
        results = await search_engine.search('nonexistent', limit=10)

        # Should return empty results
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self, setup_search_engine):
        """Test search with empty query."""
        search_engine, db_manager = setup_search_engine

        # Search with empty query
        results = await search_engine.search('', limit=10)
        assert len(results) == 0

        results = await search_engine.search('   ', limit=10)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_text_preprocessing(self, setup_search_engine):
        """Test text preprocessing functionality."""
        search_engine, db_manager = setup_search_engine

        # Test preprocessing
        text = "This is a TEST with UPPERCASE and punctuation!!!"
        terms = search_engine._preprocess_text(text)

        # Should normalize to lowercase
        assert 'TEST' not in terms
        assert 'test' in terms

        # Should remove punctuation
        assert '!!!' not in terms

        # Should filter short words if configured
        if search_engine.config.min_term_length > 1:
            assert 'a' not in terms

    @pytest.mark.asyncio
    async def test_relevance_scoring(self, setup_search_engine):
        """Test relevance scoring mechanism."""
        search_engine, db_manager = setup_search_engine

        # Index documents with different relevance levels
        docs = [
            {
                'url': 'https://example.com/high',
                'origin_url': 'https://example.com',
                'depth': 1,
                'title': 'Python Python Python',  # High title relevance
                'content': 'Python programming tutorial',
                'crawled_at': 1234567890.0
            },
            {
                'url': 'https://example.com/low',
                'origin_url': 'https://example.com',
                'depth': 2,
                'title': 'Tutorial',
                'content': 'General programming tutorial with Python mention',
                'crawled_at': 1234567889.0
            }
        ]

        for doc in docs:
            await db_manager.store_page(doc)
            await search_engine.index_document(doc)

        # Search for Python
        results = await search_engine.search('python', limit=10)

        # Document with higher relevance should score higher
        assert len(results) >= 2

        # Find results by URL
        high_result = next(r for r in results if 'high' in r[0])
        low_result = next(r for r in results if 'low' in r[0])

        # High relevance document should have higher score
        assert high_result[3] > low_result[3]

    @pytest.mark.asyncio
    async def test_index_update_queue(self, setup_search_engine):
        """Test asynchronous index updating."""
        search_engine, db_manager = setup_search_engine

        # Queue multiple documents for indexing
        docs = []
        for i in range(5):
            doc = {
                'url': f'https://example.com/doc{i}',
                'title': f'Document {i}',
                'content': f'Content for document number {i}',
                'crawled_at': 1234567890.0 + i
            }
            docs.append(doc)

        # Add to update queue
        for doc in docs:
            await search_engine.queue_index_update(doc)

        # Wait for queue processing
        await asyncio.sleep(0.1)

        # Documents should be indexed
        assert search_engine.document_count == 5

    @pytest.mark.asyncio
    async def test_term_filtering(self, setup_search_engine):
        """Test term filtering based on configuration."""
        search_engine, db_manager = setup_search_engine

        # Index document with various term types
        doc = {
            'url': 'https://example.com/test',
            'origin_url': 'https://example.com',
            'depth': 1,
            'title': 'a Test with VERY long word',
            'content': 'Short words: a an to of. Normal: test example. Long: ' + 'x' * 100,
            'crawled_at': 1234567890.0
        }

        await db_manager.store_page(doc)
        await search_engine.index_document(doc)

        # Very short and very long terms should be filtered
        terms = search_engine._preprocess_text(doc['content'])

        # Check term length filtering
        for term in terms:
            assert len(term) >= search_engine.config.min_term_length
            assert len(term) <= search_engine.config.max_term_length

    @pytest.mark.asyncio
    async def test_concurrent_indexing(self, setup_search_engine):
        """Test concurrent document indexing."""
        search_engine, db_manager = setup_search_engine

        # Create multiple concurrent indexing tasks
        docs = []
        for i in range(10):
            doc = {
                'url': f'https://example.com/doc{i}',
                'title': f'Document {i}',
                'content': f'Content for document {i}',
                'crawled_at': 1234567890.0 + i
            }
            docs.append(doc)

        # Index concurrently
        index_tasks = [search_engine.index_document(doc) for doc in docs]
        await asyncio.gather(*index_tasks)

        # All documents should be indexed
        assert search_engine.document_count == 10

        # Search should work
        results = await search_engine.search('document', limit=10)
        assert len(results) == 10


class TestSearchEngineError:
    """Test search engine error handling."""

    @pytest.mark.asyncio
    async def test_index_invalid_document(self, setup_search_engine):
        """Test indexing invalid documents."""
        search_engine, db_manager = setup_search_engine

        # Document with missing required fields
        invalid_doc = {
            'title': 'Test'
            # Missing url, content, etc.
        }

        # Should handle gracefully
        with pytest.raises(Exception):
            await search_engine.index_document(invalid_doc)

    @pytest.mark.asyncio
    async def test_search_with_database_error(self, setup_search_engine):
        """Test search behavior when database is unavailable."""
        search_engine, db_manager = setup_search_engine

        # Mock database error
        with patch.object(db_manager, 'search_pages', side_effect=Exception('DB Error')):
            results = await search_engine.search('test', limit=10)

            # Should return empty results gracefully
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_index_document_with_none_values(self, setup_search_engine):
        """Test indexing document with None values."""
        search_engine, db_manager = setup_search_engine

        doc = {
            'url': 'https://example.com/test',
            'title': None,
            'content': None,
            'crawled_at': 1234567890.0
        }

        # Should handle None values gracefully
        await search_engine.index_document(doc)

        # Document count should still increase
        assert search_engine.document_count == 1


if __name__ == "__main__":
    pytest.main([__file__])