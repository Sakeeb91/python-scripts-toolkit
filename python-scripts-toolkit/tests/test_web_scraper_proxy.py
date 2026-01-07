"""Tests for web scraper proxy functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import tempfile
import os

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.web_scraper.scraper import ProxyManager, WebScraper


class TestProxyManagerParseUrl:
    """Tests for ProxyManager.parse_proxy_url()."""

    def test_parse_http_proxy(self):
        """Test parsing HTTP proxy URL."""
        result = ProxyManager.parse_proxy_url("http://proxy.example.com:8080")
        assert result is not None
        assert result["scheme"] == "http"
        assert result["host"] == "proxy.example.com"
        assert result["port"] == 8080

    def test_parse_https_proxy(self):
        """Test parsing HTTPS proxy URL."""
        result = ProxyManager.parse_proxy_url("https://proxy.example.com:8443")
        assert result is not None
        assert result["scheme"] == "https"
        assert result["host"] == "proxy.example.com"
        assert result["port"] == 8443

    def test_parse_socks5_proxy(self):
        """Test parsing SOCKS5 proxy URL."""
        result = ProxyManager.parse_proxy_url("socks5://proxy.example.com:1080")
        assert result is not None
        assert result["scheme"] == "socks5"
        assert result["host"] == "proxy.example.com"
        assert result["port"] == 1080

    def test_parse_socks4_proxy(self):
        """Test parsing SOCKS4 proxy URL."""
        result = ProxyManager.parse_proxy_url("socks4://proxy.example.com:1080")
        assert result is not None
        assert result["scheme"] == "socks4"

    def test_parse_proxy_with_auth(self):
        """Test parsing proxy URL with authentication."""
        result = ProxyManager.parse_proxy_url("http://user:pass@proxy.example.com:8080")
        assert result is not None
        assert result["username"] == "user"
        assert result["password"] == "pass"
        assert result["host"] == "proxy.example.com"

    def test_parse_invalid_scheme(self):
        """Test that invalid schemes return None."""
        result = ProxyManager.parse_proxy_url("ftp://proxy.example.com:21")
        assert result is None

    def test_parse_missing_port(self):
        """Test that missing port returns None."""
        result = ProxyManager.parse_proxy_url("http://proxy.example.com")
        assert result is None

    def test_parse_empty_url(self):
        """Test that empty URL returns None."""
        result = ProxyManager.parse_proxy_url("")
        assert result is None

    def test_parse_none_url(self):
        """Test that None URL returns None."""
        result = ProxyManager.parse_proxy_url(None)
        assert result is None


class TestProxyManagerIsValid:
    """Tests for ProxyManager.is_valid_proxy()."""

    def test_valid_http_proxy(self):
        """Test that valid HTTP proxy is accepted."""
        assert ProxyManager.is_valid_proxy("http://proxy:8080") is True

    def test_valid_socks5_proxy(self):
        """Test that valid SOCKS5 proxy is accepted."""
        assert ProxyManager.is_valid_proxy("socks5://proxy:1080") is True

    def test_invalid_proxy(self):
        """Test that invalid proxy is rejected."""
        assert ProxyManager.is_valid_proxy("invalid://proxy:8080") is False

    def test_empty_string_invalid(self):
        """Test that empty string is invalid."""
        assert ProxyManager.is_valid_proxy("") is False


class TestProxyManagerFormatDict:
    """Tests for ProxyManager.format_proxy_dict()."""

    def test_format_http_proxy(self):
        """Test formatting HTTP proxy as dict."""
        result = ProxyManager.format_proxy_dict("http://proxy:8080")
        assert result is not None
        assert result["http"] == "http://proxy:8080"
        assert result["https"] == "http://proxy:8080"

    def test_format_socks5_proxy(self):
        """Test formatting SOCKS5 proxy as dict."""
        result = ProxyManager.format_proxy_dict("socks5://proxy:1080")
        assert result is not None
        assert result["http"] == "socks5://proxy:1080"
        assert result["https"] == "socks5://proxy:1080"

    def test_format_invalid_proxy(self):
        """Test that invalid proxy returns None."""
        result = ProxyManager.format_proxy_dict("invalid")
        assert result is None


class TestProxyManagerAddProxy:
    """Tests for ProxyManager.add_proxy()."""

    def test_add_single_proxy(self):
        """Test adding a single proxy."""
        manager = ProxyManager()
        result = manager.add_proxy("http://proxy:8080")
        assert result is True
        assert len(manager.proxies) == 1
        assert "http://proxy:8080" in manager.proxies

    def test_add_duplicate_proxy(self):
        """Test that duplicate proxies are rejected."""
        manager = ProxyManager()
        manager.add_proxy("http://proxy:8080")
        result = manager.add_proxy("http://proxy:8080")
        assert result is False
        assert len(manager.proxies) == 1

    def test_add_empty_proxy(self):
        """Test that empty proxy is rejected."""
        manager = ProxyManager()
        result = manager.add_proxy("")
        assert result is False
        assert len(manager.proxies) == 0

    def test_add_whitespace_proxy(self):
        """Test that whitespace-only proxy is rejected."""
        manager = ProxyManager()
        result = manager.add_proxy("   ")
        assert result is False


class TestProxyManagerLoadFromFile:
    """Tests for ProxyManager.load_from_file()."""

    def test_load_proxies_from_file(self):
        """Test loading proxies from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("http://proxy1:8080\n")
            f.write("http://proxy2:8080\n")
            f.write("socks5://proxy3:1080\n")
            f.flush()

            manager = ProxyManager()
            count = manager.load_from_file(Path(f.name))

            assert count == 3
            assert len(manager.proxies) == 3

        os.unlink(f.name)

    def test_load_skips_comments(self):
        """Test that comments are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# This is a comment\n")
            f.write("http://proxy1:8080\n")
            f.write("# Another comment\n")
            f.flush()

            manager = ProxyManager()
            count = manager.load_from_file(Path(f.name))

            assert count == 1
            assert len(manager.proxies) == 1

        os.unlink(f.name)

    def test_load_skips_empty_lines(self):
        """Test that empty lines are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("http://proxy1:8080\n")
            f.write("\n")
            f.write("   \n")
            f.write("http://proxy2:8080\n")
            f.flush()

            manager = ProxyManager()
            count = manager.load_from_file(Path(f.name))

            assert count == 2

        os.unlink(f.name)

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        manager = ProxyManager()
        count = manager.load_from_file(Path("/nonexistent/file.txt"))
        assert count == 0


class TestProxyManagerRotation:
    """Tests for proxy rotation strategies."""

    def test_round_robin_rotation(self):
        """Test round-robin rotation cycles through proxies."""
        manager = ProxyManager(rotation="round-robin")
        manager.add_proxy("http://proxy1:8080")
        manager.add_proxy("http://proxy2:8080")
        manager.add_proxy("http://proxy3:8080")

        # Should cycle through in order
        assert manager.get_next_proxy() == "http://proxy1:8080"
        assert manager.get_next_proxy() == "http://proxy2:8080"
        assert manager.get_next_proxy() == "http://proxy3:8080"
        assert manager.get_next_proxy() == "http://proxy1:8080"  # Wraps around

    def test_random_rotation(self):
        """Test random rotation returns valid proxy."""
        manager = ProxyManager(rotation="random")
        manager.add_proxy("http://proxy1:8080")
        manager.add_proxy("http://proxy2:8080")

        proxy = manager.get_next_proxy()
        assert proxy in manager.proxies

    def test_empty_pool_returns_none(self):
        """Test that empty pool returns None."""
        manager = ProxyManager()
        assert manager.get_next_proxy() is None


class TestProxyManagerFailure:
    """Tests for proxy failure handling."""

    def test_mark_proxy_failed(self):
        """Test marking a proxy as failed."""
        manager = ProxyManager()
        manager.add_proxy("http://proxy1:8080")
        manager.add_proxy("http://proxy2:8080")

        result = manager.mark_proxy_failed("http://proxy1:8080")

        assert result is True
        assert len(manager.proxies) == 1
        assert "http://proxy1:8080" not in manager.proxies
        assert "http://proxy1:8080" in manager.failed_proxies

    def test_mark_nonexistent_proxy_failed(self):
        """Test marking nonexistent proxy as failed."""
        manager = ProxyManager()
        manager.add_proxy("http://proxy1:8080")

        result = manager.mark_proxy_failed("http://nonexistent:8080")

        assert result is False
        assert len(manager.proxies) == 1

    def test_has_proxies(self):
        """Test has_proxies method."""
        manager = ProxyManager()
        assert manager.has_proxies() is False

        manager.add_proxy("http://proxy:8080")
        assert manager.has_proxies() is True

        manager.mark_proxy_failed("http://proxy:8080")
        assert manager.has_proxies() is False

    def test_proxy_count(self):
        """Test proxy_count method."""
        manager = ProxyManager()
        assert manager.proxy_count() == 0

        manager.add_proxy("http://proxy1:8080")
        manager.add_proxy("http://proxy2:8080")
        assert manager.proxy_count() == 2

    def test_failed_count(self):
        """Test failed_count method."""
        manager = ProxyManager()
        manager.add_proxy("http://proxy1:8080")
        assert manager.failed_count() == 0

        manager.mark_proxy_failed("http://proxy1:8080")
        assert manager.failed_count() == 1


class TestProxyManagerIsProxyError:
    """Tests for ProxyManager.is_proxy_error()."""

    def test_proxy_error_detection(self):
        """Test detection of proxy-related errors."""
        proxy_error = Exception("ProxyError: Connection refused")
        assert ProxyManager.is_proxy_error(proxy_error) is True

    def test_connection_error_detection(self):
        """Test detection of connection errors."""
        conn_error = Exception("Connection refused by proxy")
        assert ProxyManager.is_proxy_error(conn_error) is True

    def test_timeout_error_detection(self):
        """Test detection of timeout errors."""
        timeout_error = Exception("Connection timed out")
        assert ProxyManager.is_proxy_error(timeout_error) is True

    def test_non_proxy_error(self):
        """Test that non-proxy errors return False."""
        other_error = Exception("Some other error")
        assert ProxyManager.is_proxy_error(other_error) is False


class TestWebScraperProxyIntegration:
    """Tests for WebScraper proxy integration."""

    def test_scraper_without_proxy(self):
        """Test scraper initialization without proxy."""
        scraper = WebScraper()
        assert scraper.proxy_manager is None

    def test_scraper_with_single_proxy(self):
        """Test scraper initialization with single proxy."""
        scraper = WebScraper(proxy="http://proxy:8080")
        assert scraper.proxy_manager is not None
        assert scraper.proxy_manager.proxy_count() == 1

    def test_scraper_with_proxy_file(self):
        """Test scraper initialization with proxy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("http://proxy1:8080\n")
            f.write("http://proxy2:8080\n")
            f.flush()

            scraper = WebScraper(proxy_file=Path(f.name))
            assert scraper.proxy_manager is not None
            assert scraper.proxy_manager.proxy_count() == 2

        os.unlink(f.name)

    def test_scraper_with_rotation_strategy(self):
        """Test scraper respects rotation strategy."""
        scraper = WebScraper(
            proxy="http://proxy:8080",
            proxy_rotation="random"
        )
        assert scraper.proxy_manager.rotation == "random"

    def test_get_proxy_dict_returns_none_without_manager(self):
        """Test _get_proxy_dict returns None when no proxy configured."""
        scraper = WebScraper()
        assert scraper._get_proxy_dict() is None

    def test_get_proxy_dict_returns_dict_with_proxy(self):
        """Test _get_proxy_dict returns dict when proxy configured."""
        scraper = WebScraper(proxy="http://proxy:8080")
        result = scraper._get_proxy_dict()
        assert result is not None
        assert "http" in result
        assert "https" in result

    def test_rate_stats_include_proxy_info(self):
        """Test that rate stats include proxy information."""
        scraper = WebScraper(proxy="http://proxy:8080")
        stats = scraper.get_rate_stats()

        assert "proxies_active" in stats
        assert "proxies_failed" in stats
        assert stats["proxies_active"] == 1
        assert stats["proxies_failed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
