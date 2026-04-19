"""
Unit tests for URL utilities.
"""

import pytest
from src.utils.url_utils import (
    normalize_url,
    is_valid_url,
    get_domain,
    is_same_domain,
    join_url,
    should_crawl_url
)


class TestNormalizeUrl:
    """Test URL normalization functionality."""

    def test_normalize_basic_url(self):
        """Test basic URL normalization."""
        url = "HTTP://EXAMPLE.COM/Path/"
        expected = "http://example.com/Path"
        assert normalize_url(url) == expected

    def test_normalize_with_default_ports(self):
        """Test normalization removes default ports."""
        http_url = "http://example.com:80/path"
        https_url = "https://example.com:443/path"

        assert normalize_url(http_url) == "http://example.com/path"
        assert normalize_url(https_url) == "https://example.com/path"

    def test_normalize_removes_fragment(self):
        """Test that URL fragments are removed."""
        url = "https://example.com/page#section"
        expected = "https://example.com/page"
        assert normalize_url(url) == expected

    def test_normalize_preserves_query(self):
        """Test that query parameters are preserved."""
        url = "https://example.com/search?q=test&page=1"
        assert normalize_url(url) == url

    def test_normalize_invalid_url(self):
        """Test normalization of invalid URLs."""
        assert normalize_url("not-a-url") is None
        assert normalize_url("ftp://example.com") is None
        assert normalize_url("") is None
        assert normalize_url(None) is None

    def test_normalize_trailing_slash(self):
        """Test removal of trailing slash for non-root paths."""
        assert normalize_url("https://example.com/") == "https://example.com/"
        assert normalize_url("https://example.com/path/") == "https://example.com/path"


class TestIsValidUrl:
    """Test URL validation functionality."""

    def test_valid_urls(self):
        """Test validation of valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://subdomain.example.com/path?query=value",
            "http://localhost:8080/test"
        ]

        for url in valid_urls:
            assert is_valid_url(url), f"URL should be valid: {url}"

    def test_invalid_urls(self):
        """Test validation of invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')",
            "https://",
            "https://example.com with spaces",
            "https://example.com<script>",
            "a" * 3000  # Too long
        ]

        for url in invalid_urls:
            assert not is_valid_url(url), f"URL should be invalid: {url}"

    def test_url_length_limit(self):
        """Test URL length validation."""
        # Create a very long URL
        long_url = "https://example.com/" + "a" * 2500
        assert not is_valid_url(long_url)

        # Normal length should be fine
        normal_url = "https://example.com/" + "a" * 100
        assert is_valid_url(normal_url)


class TestGetDomain:
    """Test domain extraction functionality."""

    def test_get_domain_basic(self):
        """Test basic domain extraction."""
        assert get_domain("https://example.com/path") == "example.com"
        assert get_domain("http://subdomain.example.com") == "subdomain.example.com"
        assert get_domain("https://example.com:8080") == "example.com:8080"

    def test_get_domain_with_port(self):
        """Test domain extraction with port numbers."""
        assert get_domain("https://example.com:8080/path") == "example.com:8080"

    def test_get_domain_invalid(self):
        """Test domain extraction from invalid URLs."""
        assert get_domain("not-a-url") is None
        assert get_domain("") is None
        assert get_domain(None) is None


class TestIsSameDomain:
    """Test domain comparison functionality."""

    def test_same_domain(self):
        """Test detection of same domains."""
        assert is_same_domain(
            "https://example.com/page1",
            "https://example.com/page2"
        )

        assert is_same_domain(
            "http://example.com",
            "https://example.com/path"
        )

    def test_different_domains(self):
        """Test detection of different domains."""
        assert not is_same_domain(
            "https://example.com",
            "https://other.com"
        )

        assert not is_same_domain(
            "https://subdomain.example.com",
            "https://example.com"
        )

    def test_invalid_urls_same_domain(self):
        """Test domain comparison with invalid URLs."""
        assert not is_same_domain("invalid", "https://example.com")
        assert not is_same_domain("https://example.com", "invalid")


class TestJoinUrl:
    """Test URL joining functionality."""

    def test_join_absolute_url(self):
        """Test joining with absolute URL."""
        base = "https://example.com/base"
        relative = "https://other.com/page"
        result = join_url(base, relative)
        assert result == normalize_url(relative)

    def test_join_relative_path(self):
        """Test joining with relative path."""
        base = "https://example.com/base"
        relative = "page.html"
        expected = "https://example.com/page.html"
        assert join_url(base, relative) == expected

    def test_join_relative_path_with_slash(self):
        """Test joining with relative path starting with slash."""
        base = "https://example.com/base/page"
        relative = "/other"
        expected = "https://example.com/other"
        assert join_url(base, relative) == expected

    def test_join_invalid_urls(self):
        """Test joining with invalid URLs."""
        assert join_url("invalid", "page") is None
        assert join_url("https://example.com", "javascript:void(0)") is None


class TestShouldCrawlUrl:
    """Test URL crawling decision functionality."""

    def test_should_crawl_valid_url(self):
        """Test crawling decision for valid URLs."""
        assert should_crawl_url("https://example.com")
        assert should_crawl_url("http://example.com/page")

    def test_should_not_crawl_invalid_url(self):
        """Test crawling decision for invalid URLs."""
        assert not should_crawl_url("invalid-url")
        assert not should_crawl_url("ftp://example.com")

    def test_should_crawl_with_blocked_domains(self):
        """Test crawling decision with blocked domains."""
        blocked_domains = ["blocked.com", "spam"]

        assert not should_crawl_url(
            "https://blocked.com/page",
            blocked_domains=blocked_domains
        )

        assert not should_crawl_url(
            "https://spam-site.com/page",
            blocked_domains=blocked_domains
        )

        assert should_crawl_url(
            "https://allowed.com/page",
            blocked_domains=blocked_domains
        )

    def test_should_crawl_with_allowed_schemes(self):
        """Test crawling decision with allowed schemes."""
        allowed_schemes = ["https"]

        assert should_crawl_url(
            "https://example.com",
            allowed_schemes=allowed_schemes
        )

        assert not should_crawl_url(
            "http://example.com",
            allowed_schemes=allowed_schemes
        )

    def test_empty_filters(self):
        """Test crawling decision with empty filters."""
        assert should_crawl_url("https://example.com", blocked_domains=[])
        assert should_crawl_url("https://example.com", allowed_schemes=[])


if __name__ == "__main__":
    pytest.main([__file__])