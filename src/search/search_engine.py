"""
Search Engine Implementation
Handles text indexing, query processing, and relevance scoring.
"""

import asyncio
import logging
import time
from typing import List, Tuple, Dict, Optional
from collections import defaultdict, Counter
import math
import re

from ..database.db_manager import DatabaseManager


class SearchEngine:
    """
    Full-text search engine with TF-IDF relevance scoring and real-time indexing.
    """

    def __init__(self, config, db_manager: DatabaseManager):
        """
        Initialize the search engine.

        Args:
            config: Search engine configuration
            db_manager: Database manager instance
        """
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # In-memory index structures
        self.inverted_index: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.document_lengths: Dict[str, int] = {}
        self.document_count = 0
        self.term_document_freq: Dict[str, int] = defaultdict(int)

        # Index update queue for real-time updates
        self.index_update_queue = asyncio.Queue()
        self.index_update_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the search engine and start background tasks."""
        self.logger.info("Initializing search engine")

        # Load existing index from database
        await self._load_index_from_database()

        # Start background index update task
        self.index_update_task = asyncio.create_task(self._process_index_updates())

        self.logger.info(f"Search engine initialized with {self.document_count} documents")

    async def shutdown(self):
        """Shutdown the search engine and cleanup resources."""
        if self.index_update_task:
            self.index_update_task.cancel()
            try:
                await self.index_update_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Search engine shutdown complete")

    async def search(self, query: str, limit: Optional[int] = None) -> List[Tuple[str, str, int, float]]:
        """
        Search for documents matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of tuples: (relevant_url, origin_url, depth, relevance_score)
        """
        if limit is None:
            limit = self.config.default_search_limit

        self.logger.debug(f"Searching for: '{query}' (limit: {limit})")

        # Preprocess query
        query_terms = self._preprocess_text(query)
        if not query_terms:
            return []

        # Calculate relevance scores for all documents
        scores = self._calculate_relevance_scores(query_terms)

        # Filter by minimum relevance threshold
        filtered_scores = [
            (doc_id, score) for doc_id, score in scores.items()
            if score >= self.config.min_relevance_score
        ]

        # Sort by relevance score (descending)
        sorted_results = sorted(filtered_scores, key=lambda x: x[1], reverse=True)

        # Limit results
        top_results = sorted_results[:limit]

        # Get document metadata for results
        result_docs = []
        for doc_id, score in top_results:
            doc_info = await self.db_manager.get_document_info(doc_id)
            if doc_info:
                result_docs.append((
                    doc_info['url'],
                    doc_info['origin_url'],
                    doc_info['depth'],
                    score
                ))

        self.logger.debug(f"Found {len(result_docs)} results for query '{query}'")
        return result_docs

    async def index_document(self, doc_id: str, content: Dict):
        """
        Add a document to the search index.

        Args:
            doc_id: Unique document identifier
            content: Document content dictionary
        """
        # Queue document for indexing to avoid blocking
        await self.index_update_queue.put(('add', doc_id, content))

    async def remove_document(self, doc_id: str):
        """
        Remove a document from the search index.

        Args:
            doc_id: Document identifier to remove
        """
        await self.index_update_queue.put(('remove', doc_id, None))

    async def _process_index_updates(self):
        """Background task to process index updates."""
        batch_size = self.config.index_batch_size
        batch = []

        try:
            while True:
                try:
                    # Wait for updates with timeout to process batches
                    update = await asyncio.wait_for(
                        self.index_update_queue.get(),
                        timeout=5.0
                    )
                    batch.append(update)

                    # Process batch when it reaches target size or queue is empty
                    if len(batch) >= batch_size or self.index_update_queue.empty():
                        await self._process_index_batch(batch)
                        batch = []

                except asyncio.TimeoutError:
                    # Process any pending updates
                    if batch:
                        await self._process_index_batch(batch)
                        batch = []

        except asyncio.CancelledError:
            # Process any remaining updates before shutdown
            if batch:
                await self._process_index_batch(batch)
            raise

    async def _process_index_batch(self, batch: List[Tuple]):
        """Process a batch of index updates."""
        self.logger.debug(f"Processing index batch of {len(batch)} updates")

        for operation, doc_id, content in batch:
            try:
                if operation == 'add':
                    await self._add_document_to_index(doc_id, content)
                elif operation == 'remove':
                    await self._remove_document_from_index(doc_id)
            except Exception as e:
                self.logger.error(f"Error processing index update for {doc_id}: {e}")

        # Persist index changes to database
        await self._persist_index_changes(batch)

    async def _add_document_to_index(self, doc_id: str, content: Dict):
        """Add a single document to the inverted index."""
        # Extract and preprocess text content
        text_content = self._extract_searchable_text(content)
        terms = self._preprocess_text(text_content)

        if not terms:
            return

        # Calculate term frequencies
        term_freq = Counter(terms)
        doc_length = sum(term_freq.values())

        # Update inverted index
        for term, freq in term_freq.items():
            # Calculate TF (term frequency)
            tf = freq / doc_length if doc_length > 0 else 0

            # Update inverted index
            self.inverted_index[term][doc_id] = tf

            # Update document frequency for IDF calculation
            if term not in [existing_term for existing_term in self.inverted_index
                           if doc_id in self.inverted_index[existing_term]]:
                self.term_document_freq[term] += 1

        # Store document length
        self.document_lengths[doc_id] = doc_length
        self.document_count += 1

        self.logger.debug(f"Indexed document {doc_id} with {len(term_freq)} unique terms")

    async def _remove_document_from_index(self, doc_id: str):
        """Remove a document from the inverted index."""
        if doc_id not in self.document_lengths:
            return

        # Remove from inverted index and update term document frequencies
        for term in list(self.inverted_index.keys()):
            if doc_id in self.inverted_index[term]:
                del self.inverted_index[term][doc_id]
                self.term_document_freq[term] -= 1

                # Remove term entirely if no documents contain it
                if not self.inverted_index[term]:
                    del self.inverted_index[term]
                    del self.term_document_freq[term]

        # Remove document metadata
        del self.document_lengths[doc_id]
        self.document_count -= 1

        self.logger.debug(f"Removed document {doc_id} from index")

    def _calculate_relevance_scores(self, query_terms: List[str]) -> Dict[str, float]:
        """
        Calculate relevance scores for all documents using TF-IDF.

        Args:
            query_terms: Preprocessed query terms

        Returns:
            Dictionary mapping document IDs to relevance scores
        """
        scores = defaultdict(float)

        for term in query_terms:
            if term not in self.inverted_index:
                continue

            # Calculate IDF (inverse document frequency)
            df = self.term_document_freq[term]
            idf = math.log(self.document_count / df) if df > 0 else 0

            # Calculate score for each document containing this term
            for doc_id, tf in self.inverted_index[term].items():
                # TF-IDF score
                tfidf_score = tf * idf

                # Apply weighting factors based on content type
                # (This would be enhanced based on where the term appears)
                scores[doc_id] += tfidf_score

        return scores

    def _preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text into searchable terms.

        Args:
            text: Raw text content

        Returns:
            List of preprocessed terms
        """
        if not text:
            return []

        # Convert to lowercase
        text = text.lower()

        # Extract alphanumeric terms
        terms = re.findall(r'\b\w+\b', text)

        # Filter terms
        filtered_terms = []
        for term in terms:
            # Length filtering
            if len(term) < self.config.min_term_length or len(term) > self.config.max_term_length:
                continue

            # Remove stop words (if configured)
            if self.config.remove_stop_words and term in self._get_stop_words():
                continue

            # Apply stemming (if configured)
            if self.config.enable_stemming:
                term = self._stem_word(term)

            filtered_terms.append(term)

        return filtered_terms

    def _extract_searchable_text(self, content: Dict) -> str:
        """
        Extract searchable text from document content.

        Args:
            content: Document content dictionary

        Returns:
            Combined searchable text
        """
        text_parts = []

        # Title (with higher weight through repetition)
        if content.get('title'):
            title_weight = int(self.config.title_weight)
            text_parts.extend([content['title']] * title_weight)

        # Main content
        if content.get('content'):
            text_parts.append(content['content'])

        # Meta description
        if content.get('meta_description'):
            text_parts.append(content['meta_description'])

        # URL (with lower weight)
        if content.get('url'):
            # Extract meaningful parts from URL
            url_parts = content['url'].split('/')
            url_text = ' '.join(part for part in url_parts if part and part != 'https:' and part != 'http:')
            url_weight = max(1, int(self.config.url_weight))
            text_parts.extend([url_text] * url_weight)

        return ' '.join(text_parts)

    def _get_stop_words(self) -> set:
        """Get set of stop words for filtering."""
        # Basic English stop words
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they',
            'have', 'had', 'what', 'said', 'each', 'which', 'their', 'time',
            'will', 'about', 'if', 'up', 'out', 'many', 'then', 'them', 'these',
            'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'has',
            'two', 'more', 'very', 'after', 'words', 'long', 'than', 'first',
            'been', 'call', 'who', 'its', 'now', 'find', 'could', 'made', 'may',
            'part', 'over', 'new', 'sound', 'take', 'only', 'little', 'work',
            'know', 'place', 'year', 'live', 'me', 'back', 'give', 'most', 'very',
            'good', 'man', 'think', 'say', 'great', 'where', 'much', 'before',
            'move', 'right', 'too', 'old', 'any', 'same', 'tell', 'boy', 'follow',
            'came', 'want', 'show', 'also', 'around', 'form', 'three', 'small',
            'set', 'put', 'end', 'why', 'again', 'turn', 'here', 'how', 'go',
            'come', 'its', 'own', 'under', 'last', 'read', 'never', 'am', 'us',
            'left', 'add', 'those', 'i', 'you', 'my', 'me', 'we', 'our', 'your'
        }

    def _stem_word(self, word: str) -> str:
        """
        Simple stemming algorithm.

        Args:
            word: Word to stem

        Returns:
            Stemmed word
        """
        # Simple rule-based stemming
        suffixes = ['ing', 'ed', 'er', 'est', 'ly', 's']

        for suffix in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)]

        return word

    async def _load_index_from_database(self):
        """Load existing search index from database."""
        try:
            self.logger.info("Loading search index from database...")

            # Query the search_index table
            query = "SELECT term, document_url, tf_score FROM search_index"
            rows = await self.db_manager._execute_query(query)

            loaded_terms = 0
            for row in rows:
                term, doc_url, tf_score = row

                # Rebuild the inverted index
                self.inverted_index[term][doc_url] = tf_score

                # Update term document frequency
                if term not in self.term_document_freq:
                    self.term_document_freq[term] = 0
                self.term_document_freq[term] += 1

                loaded_terms += 1

            # Get document count and lengths from crawled pages
            doc_query = "SELECT url, LENGTH(content) FROM crawled_pages WHERE content IS NOT NULL"
            doc_rows = await self.db_manager._execute_query(doc_query)

            for url, content_length in doc_rows:
                self.document_lengths[url] = content_length
                self.document_count += 1

            self.logger.info(f"Loaded search index: {loaded_terms} terms, {self.document_count} documents")

        except Exception as e:
            self.logger.error(f"Error loading index from database: {e}")
            # Start with empty index on error
            self.inverted_index.clear()
            self.term_document_freq.clear()
            self.document_lengths.clear()
            self.document_count = 0

    async def _persist_index_changes(self, batch: List[Tuple]):
        """Persist index changes to database."""
        try:
            if not batch:
                return

            terms_to_insert = []
            documents_to_delete = set()

            # Process batch of changes
            for operation, doc_id, content in batch:
                if operation == 'add':
                    # Extract terms for this document and add to insert list
                    if doc_id in self.inverted_index or any(doc_id in term_docs for term_docs in self.inverted_index.values()):
                        # Get all terms for this document
                        for term, doc_scores in self.inverted_index.items():
                            if doc_id in doc_scores:
                                tf_score = doc_scores[doc_id]
                                terms_to_insert.append((term, doc_id, tf_score))

                elif operation == 'remove':
                    # Mark document for deletion
                    documents_to_delete.add(doc_id)

            # Delete old terms for updated/removed documents
            for doc_id in documents_to_delete:
                await self.db_manager.delete_search_terms(doc_id)

            # Also delete terms for documents we're updating (add operations)
            updated_docs = {doc_id for operation, doc_id, content in batch if operation == 'add'}
            for doc_id in updated_docs:
                await self.db_manager.delete_search_terms(doc_id)

            # Bulk insert new/updated terms
            if terms_to_insert:
                await self.db_manager.bulk_insert_search_terms(terms_to_insert)

            self.logger.debug(f"Persisted {len(terms_to_insert)} terms, deleted terms for {len(documents_to_delete.union(updated_docs))} documents")

        except Exception as e:
            self.logger.error(f"Error persisting index changes: {e}")