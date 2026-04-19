"""
URL processing and validation utilities.
"""

import re
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Optional


def normalize_url(url: str) -> Optional[str]:
    """
    Normalize a URL by removing fragments, normalizing case, etc.

    Args:
        url: Raw URL to normalize

    Returns:
        Normalized URL or None if invalid
    """
    if not url or not isinstance(url, str):
        return None

    try:
        # Parse the URL
        parsed = urlparse(url.strip())

        # Check if scheme is valid
        if parsed.scheme not in ['http', 'https']:
            return None

        # Convert scheme and domain to lowercase
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove default ports
        if ':80' in netloc and scheme == 'http':
            netloc = netloc.replace(':80', '')
        elif ':443' in netloc and scheme == 'https':
            netloc = netloc.replace(':443', '')

        # Normalize path (remove trailing slash for non-root paths)
        path = parsed.path
        if path and path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Remove fragment
        fragment = ''

        # Keep query parameters as-is for now
        query = parsed.query

        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        return normalized

    except Exception:
        return None


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid for crawling.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid for crawling
    """
    if not url or not isinstance(url, str):
        return False

    # Length check
    if len(url) > 2048:
        return False

    try:
        parsed = urlparse(url)

        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False

        # Must be HTTP or HTTPS
        if parsed.scheme not in ['http', 'https']:
            return False

        # Check for invalid characters
        if any(char in url for char in [' ', '<', '>', '"', '{', '}', '|', '\\', '^', '`']):
            return False

        # Check domain format
        domain = get_domain(url)
        if not _is_valid_domain(domain):
            return False

        return True

    except Exception:
        return False


def get_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL.

    Args:
        url: URL to extract domain from

    Returns:
        Domain name or None if invalid
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return None


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if URLs are from the same domain
    """
    domain1 = get_domain(url1)
    domain2 = get_domain(url2)
    return domain1 is not None and domain1 == domain2


def get_url_depth(origin_url: str, current_url: str) -> int:
    """
    Calculate the relative depth of current_url from origin_url.
    This is a simplified calculation based on path depth.

    Args:
        origin_url: Origin URL
        current_url: Current URL

    Returns:
        Depth level (0 for same URL, positive for deeper)
    """
    try:
        origin_parsed = urlparse(origin_url)
        current_parsed = urlparse(current_url)

        # If different domains, treat as depth 1
        if origin_parsed.netloc != current_parsed.netloc:
            return 1

        # Count path segments
        origin_segments = [seg for seg in origin_parsed.path.split('/') if seg]
        current_segments = [seg for seg in current_parsed.path.split('/') if seg]

        # Simple depth calculation based on path length difference
        return max(0, len(current_segments) - len(origin_segments))

    except Exception:
        return 1


def join_url(base_url: str, relative_url: str) -> Optional[str]:
    """
    Join a base URL with a relative URL.

    Args:
        base_url: Base URL
        relative_url: Relative URL to join

    Returns:
        Joined URL or None if invalid
    """
    try:
        joined = urljoin(base_url, relative_url)
        return normalize_url(joined)
    except Exception:
        return None


def extract_urls_from_text(text: str, base_url: str = None) -> list:
    """
    Extract URLs from text content.

    Args:
        text: Text to search for URLs
        base_url: Base URL for resolving relative URLs

    Returns:
        List of found URLs
    """
    if not text:
        return []

    # URL regex pattern
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )

    urls = []
    matches = url_pattern.findall(text)

    for match in matches:
        normalized = normalize_url(match)
        if normalized and is_valid_url(normalized):
            urls.append(normalized)

    # If base URL provided, also look for relative URLs
    if base_url:
        relative_pattern = re.compile(r'href=["\']([^"\']+)["\']')
        relative_matches = relative_pattern.findall(text)

        for relative in relative_matches:
            if not relative.startswith(('http://', 'https://', 'mailto:', 'javascript:')):
                joined = join_url(base_url, relative)
                if joined and joined not in urls:
                    urls.append(joined)

    return urls


def _is_valid_domain(domain: str) -> bool:
    """
    Validate domain name format.

    Args:
        domain: Domain name to validate

    Returns:
        True if domain format is valid
    """
    if not domain:
        return False

    # Remove port if present
    if ':' in domain:
        domain = domain.split(':')[0]

    # Domain length check
    if len(domain) > 253:
        return False

    # Simple domain format check
    domain_pattern = re.compile(
        r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )

    return bool(domain_pattern.match(domain))


def get_robots_txt_url(base_url: str) -> str:
    """
    Get the robots.txt URL for a given base URL.

    Args:
        base_url: Base URL

    Returns:
        robots.txt URL
    """
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        return robots_url
    except Exception:
        return None


def should_crawl_url(url: str, blocked_domains: list = None, allowed_schemes: list = None) -> bool:
    """
    Check if a URL should be crawled based on filtering rules.

    Args:
        url: URL to check
        blocked_domains: List of blocked domain patterns
        allowed_schemes: List of allowed URL schemes

    Returns:
        True if URL should be crawled
    """
    if not is_valid_url(url):
        return False

    # Check scheme
    if allowed_schemes:
        parsed = urlparse(url)
        if parsed.scheme not in allowed_schemes:
            return False

    # Check blocked domains
    if blocked_domains:
        domain = get_domain(url)
        if domain:
            for blocked_pattern in blocked_domains:
                if blocked_pattern in domain:
                    return False

    return True