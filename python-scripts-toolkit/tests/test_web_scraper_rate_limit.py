"""Tests for Web Scraper rate limiting functionality."""
import time
from unittest.mock import Mock, patch
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.web_scraper.scraper import WebScraper


class TestParseRandomDelay:
    """Tests for the parse_random_delay static method."""

    def test_valid_integer_range(self):
        """Test parsing valid integer range like '1-5'."""
        result = WebScraper.parse_random_delay("1-5")
        assert result == (1.0, 5.0)

    def test_valid_float_range(self):
        """Test parsing valid float range like '0.5-2.5'."""
        result = WebScraper.parse_random_delay("0.5-2.5")
        assert result == (0.5, 2.5)

    def test_same_min_max(self):
        """Test range with same min and max values."""
        result = WebScraper.parse_random_delay("2-2")
        assert result == (2.0, 2.0)

    def test_zero_to_number(self):
        """Test range starting from zero."""
        result = WebScraper.parse_random_delay("0-3")
        assert result == (0.0, 3.0)

    def test_invalid_format_no_dash(self):
        """Test invalid format without dash."""
        result = WebScraper.parse_random_delay("5")
        assert result is None

    def test_invalid_format_multiple_dashes(self):
        """Test invalid format with multiple dashes."""
        result = WebScraper.parse_random_delay("1-2-3")
        assert result is None

    def test_invalid_negative_values(self):
        """Test negative values are rejected."""
        result = WebScraper.parse_random_delay("-1-5")
        assert result is None

    def test_invalid_min_greater_than_max(self):
        """Test min > max is rejected."""
        result = WebScraper.parse_random_delay("5-1")
        assert result is None

    def test_invalid_non_numeric(self):
        """Test non-numeric values are rejected."""
        result = WebScraper.parse_random_delay("one-five")
        assert result is None


class TestWaitMethod:
    """Tests for the _wait method."""

    def test_wait_with_fixed_delay(self):
        """Test _wait applies fixed delay correctly."""
        scraper = WebScraper(delay=0.1)

        start = time.time()
        actual_delay = scraper._wait()
        elapsed = time.time() - start

        assert elapsed >= 0.1
        assert actual_delay == 0.1

    def test_wait_with_random_delay(self):
        """Test _wait applies random delay within range."""
        scraper = WebScraper(random_delay=(0.1, 0.2))

        start = time.time()
        actual_delay = scraper._wait()
        elapsed = time.time() - start

        assert 0.1 <= elapsed <= 0.3  # Allow small overhead
        assert 0.1 <= actual_delay <= 0.2

    def test_wait_with_no_delay(self):
        """Test _wait returns 0 when no delay configured."""
        scraper = WebScraper()

        start = time.time()
        actual_delay = scraper._wait()
        elapsed = time.time() - start

        assert elapsed < 0.05  # Should be nearly instant
        assert actual_delay == 0.0

    def test_random_delay_takes_priority(self):
        """Test random delay takes priority over fixed delay."""
        scraper = WebScraper(delay=5.0, random_delay=(0.1, 0.2))

        start = time.time()
        actual_delay = scraper._wait()
        elapsed = time.time() - start

        # Should use random delay (0.1-0.2), not fixed delay (5.0)
        assert elapsed < 0.5
        assert actual_delay < 0.5


class TestParseRateLimitHeaders:
    """Tests for the _parse_rate_limit_headers method."""

    def test_retry_after_seconds(self):
        """Test parsing Retry-After header with seconds."""
        scraper = WebScraper()
        mock_response = Mock()
        mock_response.headers = {"Retry-After": "30"}

        delay = scraper._parse_rate_limit_headers(mock_response)
        assert delay == 30.0

    def test_retry_after_float(self):
        """Test parsing Retry-After header with float seconds."""
        scraper = WebScraper()
        mock_response = Mock()
        mock_response.headers = {"Retry-After": "2.5"}

        delay = scraper._parse_rate_limit_headers(mock_response)
        assert delay == 2.5

    def test_x_ratelimit_remaining_zero(self):
        """Test X-RateLimit headers when remaining is zero."""
        scraper = WebScraper()
        mock_response = Mock()
        future_time = int(time.time()) + 60  # 60 seconds from now
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(future_time)
        }

        delay = scraper._parse_rate_limit_headers(mock_response)
        assert delay is not None
        assert 55 <= delay <= 65  # Allow some tolerance

    def test_x_ratelimit_remaining_nonzero(self):
        """Test X-RateLimit headers when remaining is nonzero."""
        scraper = WebScraper()
        mock_response = Mock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": str(int(time.time()) + 60)
        }

        delay = scraper._parse_rate_limit_headers(mock_response)
        assert delay is None  # No delay needed, still have requests

    def test_no_rate_limit_headers(self):
        """Test response without rate limit headers."""
        scraper = WebScraper()
        mock_response = Mock()
        mock_response.headers = {"Content-Type": "text/html"}

        delay = scraper._parse_rate_limit_headers(mock_response)
        assert delay is None


class TestGetRateStats:
    """Tests for the get_rate_stats method."""

    def test_initial_stats(self):
        """Test initial stats are zero."""
        scraper = WebScraper()
        stats = scraper.get_rate_stats()

        assert stats["request_count"] == 0
        assert stats["total_delay_time"] == 0.0
        assert stats["elapsed_time"] == 0.0
        assert stats["avg_delay"] == 0.0
        assert stats["requests_per_minute"] == 0.0

    def test_stats_after_simulated_requests(self):
        """Test stats after simulated request activity."""
        scraper = WebScraper()
        scraper.start_time = time.time() - 60  # Started 60 seconds ago
        scraper.request_count = 30
        scraper.total_delay_time = 15.0

        stats = scraper.get_rate_stats()

        assert stats["request_count"] == 30
        assert stats["total_delay_time"] == 15.0
        assert 55 <= stats["elapsed_time"] <= 65  # ~60 seconds
        assert stats["avg_delay"] == 0.5  # 15.0 / 30
        assert 25 <= stats["requests_per_minute"] <= 35  # ~30 rpm


class TestWebScraperInitialization:
    """Tests for WebScraper initialization with rate limiting."""

    def test_default_rate_limiting_disabled(self):
        """Test rate limiting is disabled by default."""
        scraper = WebScraper()

        assert scraper.delay == 0
        assert scraper.random_delay is None
        assert scraper.respect_rate_limits is False

    def test_fixed_delay_initialization(self):
        """Test initialization with fixed delay."""
        scraper = WebScraper(delay=2.0)

        assert scraper.delay == 2.0
        assert scraper.random_delay is None

    def test_random_delay_initialization(self):
        """Test initialization with random delay."""
        scraper = WebScraper(random_delay=(1.0, 5.0))

        assert scraper.random_delay == (1.0, 5.0)

    def test_respect_rate_limits_initialization(self):
        """Test initialization with respect_rate_limits."""
        scraper = WebScraper(respect_rate_limits=True)

        assert scraper.respect_rate_limits is True

    def test_statistics_initialized(self):
        """Test request statistics are initialized."""
        scraper = WebScraper()

        assert scraper.request_count == 0
        assert scraper.total_delay_time == 0.0
        assert scraper.start_time is None
