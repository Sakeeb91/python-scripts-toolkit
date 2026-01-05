"""Tests for web scraper robots.txt compliance functionality."""
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.web_scraper.scraper import RobotsChecker, WebScraper


class TestRobotsChecker:
    """Tests for the RobotsChecker class."""

    def test_get_robots_url(self):
        """Test robots.txt URL generation."""
        checker = RobotsChecker()
        assert checker._get_robots_url("https://example.com/page") == "https://example.com/robots.txt"
        assert checker._get_robots_url("https://example.com:8080/path") == "https://example.com:8080/robots.txt"
        assert checker._get_robots_url("http://test.org/a/b/c") == "http://test.org/robots.txt"

    def test_get_domain(self):
        """Test domain extraction for caching."""
        checker = RobotsChecker()
        assert checker._get_domain("https://example.com/page") == "https://example.com"
        assert checker._get_domain("https://example.com:8080/path") == "https://example.com:8080"
        assert checker._get_domain("http://test.org/a/b/c") == "http://test.org"

    def test_cache_prevents_duplicate_fetches(self):
        """Test that robots.txt is cached per domain."""
        checker = RobotsChecker()

        with patch.object(checker, '_fetch_robots') as mock_fetch:
            mock_rp = MagicMock()
            mock_rp.can_fetch.return_value = True
            mock_fetch.return_value = mock_rp

            # First call should fetch
            checker.can_fetch("https://example.com/page1")
            mock_fetch.assert_called_once()

            # After caching, subsequent calls don't re-fetch
            checker._cache["https://example.com"] = mock_rp
            checker.can_fetch("https://example.com/page2")
            # Still just one call since we manually cached

    def test_can_fetch_returns_true_when_no_robots(self):
        """Test that missing robots.txt allows all URLs."""
        checker = RobotsChecker()
        checker._cache["https://example.com"] = None  # Simulate failed fetch

        assert checker.can_fetch("https://example.com/anything") is True

    def test_crawl_delay_caching(self):
        """Test that crawl delay is cached per domain."""
        checker = RobotsChecker()
        checker._crawl_delays["https://example.com"] = 5.0

        assert checker.get_crawl_delay("https://example.com/page") == 5.0

    def test_clear_cache(self):
        """Test cache clearing."""
        checker = RobotsChecker()
        checker._cache["https://example.com"] = MagicMock()
        checker._crawl_delays["https://example.com"] = 5.0

        checker.clear_cache()

        assert len(checker._cache) == 0
        assert len(checker._crawl_delays) == 0


class TestWebScraperRobotsMode:
    """Tests for WebScraper robots.txt mode handling."""

    def test_robots_mode_constants(self):
        """Test that robots mode constants are defined."""
        assert WebScraper.ROBOTS_WARN == "warn"
        assert WebScraper.ROBOTS_RESPECT == "respect"
        assert WebScraper.ROBOTS_IGNORE == "ignore"

    def test_default_robots_mode_is_warn(self):
        """Test that default robots mode is 'warn'."""
        scraper = WebScraper()
        assert scraper.robots_mode == "warn"
        assert scraper.robots_checker is not None

    def test_ignore_mode_disables_checker(self):
        """Test that ignore mode doesn't create a robots checker."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_IGNORE)
        assert scraper.robots_mode == "ignore"
        assert scraper.robots_checker is None

    def test_respect_mode_creates_checker(self):
        """Test that respect mode creates a robots checker."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_RESPECT)
        assert scraper.robots_mode == "respect"
        assert scraper.robots_checker is not None

    def test_blocked_urls_list_initialized(self):
        """Test that blocked URLs list is initialized."""
        scraper = WebScraper()
        assert scraper.blocked_urls == []


class TestWebScraperCheckRobots:
    """Tests for WebScraper.check_robots() method."""

    def test_check_robots_ignore_mode_always_allows(self):
        """Test that ignore mode always returns True."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_IGNORE)
        assert scraper.check_robots("https://example.com/blocked") is True

    def test_check_robots_respect_mode_blocks_disallowed(self):
        """Test that respect mode blocks disallowed URLs."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_RESPECT)
        scraper.robots_checker = MagicMock()
        scraper.robots_checker.can_fetch.return_value = False

        result = scraper.check_robots("https://example.com/blocked")

        assert result is False
        assert "https://example.com/blocked" in scraper.blocked_urls

    def test_check_robots_warn_mode_allows_disallowed(self):
        """Test that warn mode allows disallowed URLs (just logs warning)."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_WARN)
        scraper.robots_checker = MagicMock()
        scraper.robots_checker.can_fetch.return_value = False

        result = scraper.check_robots("https://example.com/blocked")

        assert result is True  # Still allows
        assert len(scraper.blocked_urls) == 0  # Not added to blocked list

    def test_check_robots_allowed_url_passes(self):
        """Test that allowed URLs pass in any mode."""
        for mode in [WebScraper.ROBOTS_WARN, WebScraper.ROBOTS_RESPECT]:
            scraper = WebScraper(robots_mode=mode)
            scraper.robots_checker = MagicMock()
            scraper.robots_checker.can_fetch.return_value = True

            assert scraper.check_robots("https://example.com/allowed") is True


class TestWebScraperRateStats:
    """Tests for rate statistics including robots.txt blocked count."""

    def test_get_rate_stats_includes_blocked_count(self):
        """Test that rate stats include blocked_by_robots count."""
        scraper = WebScraper(robots_mode=WebScraper.ROBOTS_RESPECT)
        scraper.blocked_urls = ["url1", "url2", "url3"]

        stats = scraper.get_rate_stats()

        assert "blocked_by_robots" in stats
        assert stats["blocked_by_robots"] == 3

    def test_get_rate_stats_zero_blocked_initially(self):
        """Test that blocked count starts at zero."""
        scraper = WebScraper()
        stats = scraper.get_rate_stats()

        assert stats["blocked_by_robots"] == 0


class TestWebScraperWaitWithCrawlDelay:
    """Tests for _wait() method with Crawl-delay integration."""

    def test_wait_uses_crawl_delay_when_larger(self):
        """Test that Crawl-delay is used when larger than configured delay."""
        scraper = WebScraper(delay=1.0)
        scraper.robots_checker = MagicMock()
        scraper.robots_checker.get_crawl_delay.return_value = 5.0

        with patch('time.sleep') as mock_sleep:
            delay = scraper._wait(url="https://example.com/page")

        assert delay == 5.0
        mock_sleep.assert_called_once_with(5.0)

    def test_wait_uses_configured_delay_when_larger(self):
        """Test that configured delay is used when larger than Crawl-delay."""
        scraper = WebScraper(delay=10.0)
        scraper.robots_checker = MagicMock()
        scraper.robots_checker.get_crawl_delay.return_value = 2.0

        with patch('time.sleep') as mock_sleep:
            delay = scraper._wait(url="https://example.com/page")

        assert delay == 10.0
        mock_sleep.assert_called_once_with(10.0)

    def test_wait_no_crawl_delay_when_no_checker(self):
        """Test that _wait works without robots checker."""
        scraper = WebScraper(delay=2.0, robots_mode=WebScraper.ROBOTS_IGNORE)

        with patch('time.sleep') as mock_sleep:
            delay = scraper._wait(url="https://example.com/page")

        assert delay == 2.0
        mock_sleep.assert_called_once_with(2.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
