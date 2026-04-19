"""
Web Crawler Implementation
Handles URL discovery, content extraction, and crawling coordination.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Set, Dict, Optional, List
from urllib.parse import urljoin, urlparse
from collections import defaultdict, deque

import aiohttp
from bs4 import BeautifulSoup

from ..database.db_manager import DatabaseManager
from ..utils.url_utils import normalize_url, is_valid_url, get_domain
from .robots_handler import RobotsHandler


class WebCrawler:
    """
    Asynchronous web crawler with depth-limited crawling and backpressure management.
    """

    def __init__(self, config, db_manager: DatabaseManager, search_engine=None):
        """
        Initialize the web crawler.

        Args:
            config: Crawler configuration object
            db_manager: Database manager instance
            search_engine: Optional search engine for real-time indexing
        """
        self.config = config
        self.db_manager = db_manager
        self.search_engine = search_engine
        self.logger = logging.getLogger(__name__)

        # Crawling state
        self.visited_urls: Set[str] = set()
        self.url_queue: deque = deque()
        self.domain_last_access: Dict[str, float] = defaultdict(float)

        # Statistics
        self.pages_crawled = 0
        self.pages_failed = 0
        self.start_time = None

        # Rate limiting
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)

        # Robots.txt handler
        self.robots_handler: Optional[RobotsHandler] = None
        if config.respect_robots_txt:
            self.robots_handler = RobotsHandler(config.user_agent)

    async def crawl(self, origin_url: str, max_depth: int, max_pages: Optional[int] = None) -> AsyncGenerator[int, None]:
        """
        Start crawling from origin URL to specified depth.

        Args:
            origin_url: Starting URL for crawling
            max_depth: Maximum crawl depth
            max_pages: Optional maximum number of pages to crawl

        Yields:
            int: Number of pages crawled so far
        """
        self.start_time = time.time()
        self.logger.info(f"Starting crawl from {origin_url} to depth {max_depth}")

        try:
            # Initialize HTTP session
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            connector = aiohttp.TCPConnector(limit=self.config.max_concurrent_requests)
            headers = {'User-Agent': self.config.user_agent}

            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers
            ) as session:
                self.session = session

                # Add origin URL to queue
                normalized_origin = normalize_url(origin_url)
                await self._add_url_to_queue(normalized_origin, normalized_origin, 0)

                # Process URLs until queue is empty or limits reached
                while self.url_queue and (not max_pages or self.pages_crawled < max_pages):
                    # Check queue depth for backpressure
                    if len(self.url_queue) > self.config.max_queue_depth:
                        self.logger.warning("Queue depth exceeded, implementing backpressure")
                        await asyncio.sleep(1)
                        continue

                    # Process batch of URLs concurrently
                    batch_size = min(self.config.max_concurrent_requests, len(self.url_queue))
                    tasks = []

                    for _ in range(batch_size):
                        if not self.url_queue:
                            break

                        url_data = self.url_queue.popleft()
                        task = self._crawl_url(url_data, max_depth)
                        tasks.append(task)

                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)

                    yield self.pages_crawled

        except Exception as e:
            self.logger.error(f"Crawling error: {e}", exc_info=True)
            raise
        finally:
            self.session = None
            self.logger.info(f"Crawling completed: {self.pages_crawled} pages crawled, "
                           f"{self.pages_failed} failed")

    async def _crawl_url(self, url_data: Dict, max_depth: int) -> None:
        """
        Crawl a single URL and extract content and links.

        Args:
            url_data: Dictionary containing url, origin_url, and depth
            max_depth: Maximum crawl depth
        """
        url = url_data['url']
        origin_url = url_data['origin_url']
        depth = url_data['depth']

        # Skip if already visited
        if url in self.visited_urls:
            return

        self.visited_urls.add(url)

        async with self.semaphore:
            try:
                # Check robots.txt compliance
                if self.robots_handler:
                    can_crawl = await self.robots_handler.can_crawl(url, self.session)
                    if not can_crawl:
                        self.logger.debug(f"Robots.txt disallows crawling: {url}")
                        return

                    # Respect crawl delay from robots.txt
                    crawl_delay_wait = await self.robots_handler.should_wait_for_crawl_delay(url, self.session)
                    if crawl_delay_wait > 0:
                        await asyncio.sleep(crawl_delay_wait)

                # Rate limiting by domain
                domain = get_domain(url)
                await self._respect_rate_limit(domain)

                # Fetch page content
                page_content = await self._fetch_page(url)
                if not page_content:
                    self.pages_failed += 1
                    return

                # Parse content and extract information
                soup = BeautifulSoup(page_content['content'], 'html.parser')

                # Extract page information
                page_info = {
                    'url': url,
                    'origin_url': origin_url,
                    'depth': depth,
                    'title': self._extract_title(soup),
                    'content': self._extract_text_content(soup),
                    'meta_description': self._extract_meta_description(soup),
                    'content_type': page_content.get('content_type', ''),
                    'content_length': len(page_content['content']),
                    'crawled_at': time.time()
                }

                # Store page in database
                await self.db_manager.store_page(page_info)

                # Index page for search if search engine is available
                if self.search_engine:
                    await self.search_engine.index_document(page_info['url'], page_info)

                # Record robots.txt access time
                if self.robots_handler:
                    await self.robots_handler.record_access(url)

                # Extract and queue new URLs if not at max depth
                if depth < max_depth:
                    links = self._extract_links(soup, url)
                    for link_url in links:
                        await self._add_url_to_queue(link_url, origin_url, depth + 1)

                self.pages_crawled += 1
                self.logger.debug(f"Crawled: {url} (depth {depth})")

            except Exception as e:
                self.pages_failed += 1
                self.logger.error(f"Error crawling {url}: {e}")
                await self.db_manager.store_error(url, origin_url, depth, str(e))

    async def _fetch_page(self, url: str) -> Optional[Dict]:
        """
        Fetch a web page with error handling and retries.

        Args:
            url: URL to fetch

        Returns:
            Dictionary with content and metadata, or None if failed
        """
        retries = 0
        while retries <= self.config.max_retries:
            try:
                async with self.session.get(url) as response:
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if not any(ct in content_type for ct in self.config.allowed_content_types):
                        self.logger.debug(f"Skipping {url}: unsupported content type {content_type}")
                        return None

                    # Check response status
                    if response.status != 200:
                        self.logger.warning(f"HTTP {response.status} for {url}")
                        return None

                    # Read content with size limit
                    content = await response.read()
                    if len(content) > self.config.max_page_size:
                        self.logger.warning(f"Page too large: {url} ({len(content)} bytes)")
                        return None

                    return {
                        'content': content.decode('utf-8', errors='ignore'),
                        'content_type': content_type,
                        'status_code': response.status,
                        'headers': dict(response.headers)
                    }

            except asyncio.TimeoutError:
                retries += 1
                if retries <= self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * retries)
                    self.logger.debug(f"Timeout, retrying {url} ({retries}/{self.config.max_retries})")
                else:
                    self.logger.error(f"Max retries exceeded for {url}")
                    return None

            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}")
                return None

    async def _respect_rate_limit(self, domain: str) -> None:
        """
        Implement rate limiting per domain.

        Args:
            domain: Domain to check rate limit for
        """
        current_time = time.time()
        last_access = self.domain_last_access[domain]
        time_since_last = current_time - last_access

        if time_since_last < self.config.request_delay:
            sleep_time = self.config.request_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.domain_last_access[domain] = time.time()

    async def _add_url_to_queue(self, url: str, origin_url: str, depth: int) -> None:
        """
        Add URL to crawling queue with validation.

        Args:
            url: URL to add
            origin_url: Origin URL for tracking
            depth: Crawl depth
        """
        if not is_valid_url(url) or url in self.visited_urls:
            return

        # Check if URL already queued
        for queued_item in self.url_queue:
            if queued_item['url'] == url:
                return

        self.url_queue.append({
            'url': url,
            'origin_url': origin_url,
            'depth': depth
        })

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract and normalize links from HTML.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for relative links

        Returns:
            List of normalized URLs
        """
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            normalized_url = normalize_url(absolute_url)

            if normalized_url and is_valid_url(normalized_url):
                links.append(normalized_url)

        return links

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title_tag = soup.find('title')
        return title_tag.get_text().strip() if title_tag else ""

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract main text content from page."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text content
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description."""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '').strip()
        return ""