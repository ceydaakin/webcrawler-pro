"""
Robots.txt Handler for Web Crawler
Implements ethical crawling by respecting robots.txt directives.
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from ..utils.url_utils import get_domain


class RobotsHandler:
    """
    Handles robots.txt fetching, parsing, and compliance checking.
    """

    def __init__(self, user_agent: str = "BLG480E-WebCrawler/1.0"):
        """
        Initialize the robots handler.

        Args:
            user_agent: User agent string for robots.txt compliance
        """
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)

        # Cache robots.txt parsers by domain
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_ttl = 3600  # 1 hour TTL for robots.txt cache

        # Crawl delays per domain
        self.crawl_delays: Dict[str, float] = {}
        self.last_access_times: Dict[str, float] = {}

        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None

    async def can_crawl(self, url: str, session: Optional[aiohttp.ClientSession] = None) -> bool:
        """
        Check if a URL can be crawled according to robots.txt.

        Args:
            url: URL to check
            session: Optional aiohttp session to use

        Returns:
            True if URL can be crawled, False otherwise
        """
        try:
            domain = get_domain(url)
            if not domain:
                return False

            # Get robots parser for domain
            robots_parser = await self._get_robots_parser(domain, session)
            if not robots_parser:
                # If we can't fetch robots.txt, assume crawling is allowed
                return True

            # Check if URL is allowed
            parsed_url = urlparse(url)
            path = parsed_url.path or "/"

            return robots_parser.can_fetch(self.user_agent, path)

        except Exception as e:
            self.logger.warning(f"Error checking robots.txt for {url}: {e}")
            # On error, be conservative and allow crawling
            return True

    async def get_crawl_delay(self, url: str, session: Optional[aiohttp.ClientSession] = None) -> float:
        """
        Get the crawl delay for a domain from robots.txt.

        Args:
            url: URL to check
            session: Optional aiohttp session to use

        Returns:
            Crawl delay in seconds (default: 0.0)
        """
        try:
            domain = get_domain(url)
            if not domain:
                return 0.0

            # Check cache first
            if domain in self.crawl_delays:
                return self.crawl_delays[domain]

            # Get robots parser for domain
            robots_parser = await self._get_robots_parser(domain, session)
            if not robots_parser:
                return 0.0

            # Get crawl delay
            delay = robots_parser.crawl_delay(self.user_agent)
            crawl_delay = float(delay) if delay is not None else 0.0

            # Cache the result
            self.crawl_delays[domain] = crawl_delay

            return crawl_delay

        except Exception as e:
            self.logger.warning(f"Error getting crawl delay for {url}: {e}")
            return 0.0

    async def should_wait_for_crawl_delay(self, url: str, session: Optional[aiohttp.ClientSession] = None) -> float:
        """
        Check if we need to wait before crawling a URL due to crawl delay.

        Args:
            url: URL to check
            session: Optional aiohttp session to use

        Returns:
            Number of seconds to wait (0.0 if no wait needed)
        """
        try:
            domain = get_domain(url)
            if not domain:
                return 0.0

            # Get crawl delay for domain
            crawl_delay = await self.get_crawl_delay(url, session)
            if crawl_delay <= 0:
                return 0.0

            # Check last access time
            current_time = time.time()
            last_access = self.last_access_times.get(domain, 0)
            time_since_last = current_time - last_access

            if time_since_last < crawl_delay:
                wait_time = crawl_delay - time_since_last
                return max(0.0, wait_time)

            return 0.0

        except Exception as e:
            self.logger.warning(f"Error calculating crawl delay for {url}: {e}")
            return 0.0

    async def record_access(self, url: str):
        """
        Record that we accessed a URL for crawl delay tracking.

        Args:
            url: URL that was accessed
        """
        domain = get_domain(url)
        if domain:
            self.last_access_times[domain] = time.time()

    async def _get_robots_parser(self, domain: str, session: Optional[aiohttp.ClientSession] = None) -> Optional[RobotFileParser]:
        """
        Get robots parser for domain, fetching if not cached.

        Args:
            domain: Domain to get robots.txt for
            session: Optional aiohttp session to use

        Returns:
            RobotFileParser instance or None if unavailable
        """
        # Check cache and TTL
        current_time = time.time()
        if (domain in self.robots_cache and
            domain in self.cache_timestamps and
            current_time - self.cache_timestamps[domain] < self.cache_ttl):
            return self.robots_cache[domain]

        # Fetch robots.txt
        robots_parser = await self._fetch_robots_txt(domain, session)

        # Cache the result (even if None)
        self.robots_cache[domain] = robots_parser
        self.cache_timestamps[domain] = current_time

        return robots_parser

    async def _fetch_robots_txt(self, domain: str, session: Optional[aiohttp.ClientSession] = None) -> Optional[RobotFileParser]:
        """
        Fetch and parse robots.txt for a domain.

        Args:
            domain: Domain to fetch robots.txt for
            session: Optional aiohttp session to use

        Returns:
            RobotFileParser instance or None if unavailable
        """
        # Construct robots.txt URL
        robots_url = f"https://{domain}/robots.txt"

        # Try HTTPS first, then HTTP
        for scheme in ['https', 'http']:
            try:
                robots_url = f"{scheme}://{domain}/robots.txt"

                # Use provided session or create temporary one
                use_session = session
                if not use_session:
                    timeout = aiohttp.ClientTimeout(total=10)
                    use_session = aiohttp.ClientSession(timeout=timeout)

                try:
                    async with use_session.get(robots_url) as response:
                        if response.status == 200:
                            content = await response.text()

                            # Create and parse robots.txt
                            robots_parser = RobotFileParser()
                            robots_parser.set_url(robots_url)
                            robots_parser.set_text(content)
                            robots_parser.read()

                            self.logger.debug(f"Successfully fetched robots.txt for {domain}")
                            return robots_parser

                        elif response.status in [404, 403]:
                            # No robots.txt found - treat as "allow all"
                            self.logger.debug(f"No robots.txt found for {domain} (status {response.status})")

                            # Create permissive robots parser
                            robots_parser = RobotFileParser()
                            robots_parser.set_url(robots_url)
                            robots_parser.set_text("")  # Empty robots.txt allows everything
                            robots_parser.read()
                            return robots_parser

                        else:
                            self.logger.debug(f"Unexpected status {response.status} for robots.txt at {robots_url}")

                finally:
                    # Close session if we created it
                    if not session and use_session:
                        await use_session.close()

            except asyncio.TimeoutError:
                self.logger.debug(f"Timeout fetching robots.txt from {robots_url}")
                continue
            except Exception as e:
                self.logger.debug(f"Error fetching robots.txt from {robots_url}: {e}")
                continue

        # If all attempts failed, return None (will default to allowing crawling)
        self.logger.debug(f"Could not fetch robots.txt for {domain}")
        return None

    async def prefetch_robots(self, domains: list, session: Optional[aiohttp.ClientSession] = None):
        """
        Prefetch robots.txt for multiple domains in parallel.

        Args:
            domains: List of domains to prefetch robots.txt for
            session: Optional aiohttp session to use
        """
        if not domains:
            return

        self.logger.info(f"Prefetching robots.txt for {len(domains)} domains")

        # Create tasks for parallel fetching
        tasks = []
        for domain in domains:
            task = self._get_robots_parser(domain, session)
            tasks.append(task)

        # Wait for all tasks to complete
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.info(f"Completed prefetching robots.txt for {len(domains)} domains")
        except Exception as e:
            self.logger.warning(f"Error during robots.txt prefetching: {e}")

    def clear_cache(self):
        """Clear the robots.txt cache."""
        self.robots_cache.clear()
        self.cache_timestamps.clear()
        self.crawl_delays.clear()
        self.last_access_times.clear()
        self.logger.debug("Robots.txt cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()
        valid_entries = sum(
            1 for domain, timestamp in self.cache_timestamps.items()
            if current_time - timestamp < self.cache_ttl
        )

        return {
            "total_cached": len(self.robots_cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.robots_cache) - valid_entries,
            "domains_with_delays": len(self.crawl_delays),
        }