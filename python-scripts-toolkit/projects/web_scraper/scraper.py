"""
Web Scraper + Saver - Fetches web pages and saves structured data to CSV.

Usage:
    python -m projects.web_scraper.scraper https://news.ycombinator.com --output hn_stories.csv
    python -m projects.web_scraper.scraper https://example.com --selector "h2.title" --output titles.csv
"""
import argparse
import csv
import random
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from config import WEB_SCRAPER_CONFIG, DATA_DIR
from utils.logger import setup_logger
from utils.helpers import load_json, save_json


class RobotsChecker:
    """Checks and enforces robots.txt compliance for web scraping."""

    def __init__(self, user_agent: str = "*"):
        """Initialize the RobotsChecker.

        Args:
            user_agent: User agent string to check permissions for.
        """
        self.user_agent = user_agent
        self._cache: Dict[str, RobotFileParser] = {}
        self._crawl_delays: Dict[str, Optional[float]] = {}
        self.logger = setup_logger("robots_checker")

    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for caching."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _fetch_robots(self, url: str) -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt for a domain.

        Args:
            url: Any URL from the target domain.

        Returns:
            RobotFileParser instance or None if fetch failed.
        """
        domain = self._get_domain(url)

        # Check cache first
        if domain in self._cache:
            return self._cache[domain]

        robots_url = self._get_robots_url(url)
        self.logger.info(f"Fetching robots.txt from {robots_url}")

        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            rp.read()
            self._cache[domain] = rp

            # Cache crawl delay
            crawl_delay = rp.crawl_delay(self.user_agent)
            self._crawl_delays[domain] = crawl_delay
            if crawl_delay:
                self.logger.info(f"Crawl-delay for {domain}: {crawl_delay}s")

            return rp
        except Exception as e:
            self.logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
            # Cache None to avoid repeated failed fetches
            self._cache[domain] = None
            self._crawl_delays[domain] = None
            return None

    def can_fetch(self, url: str) -> bool:
        """Check if the URL is allowed by robots.txt.

        Args:
            url: The URL to check.

        Returns:
            True if allowed, False if disallowed.
        """
        rp = self._fetch_robots(url)

        # If robots.txt doesn't exist or failed to fetch, allow by default
        if rp is None:
            return True

        allowed = rp.can_fetch(self.user_agent, url)
        if not allowed:
            self.logger.warning(f"URL disallowed by robots.txt: {url}")

        return allowed

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get the Crawl-delay directive for a domain.

        Args:
            url: Any URL from the target domain.

        Returns:
            Crawl delay in seconds, or None if not specified.
        """
        domain = self._get_domain(url)

        # Ensure robots.txt is fetched
        if domain not in self._crawl_delays:
            self._fetch_robots(url)

        return self._crawl_delays.get(domain)

    def clear_cache(self):
        """Clear the robots.txt cache."""
        self._cache.clear()
        self._crawl_delays.clear()


class ProxyManager:
    """Manages proxy rotation for web scraping requests."""

    # Rotation strategy constants
    ROTATION_ROUND_ROBIN = "round-robin"
    ROTATION_RANDOM = "random"

    # Supported proxy schemes
    SUPPORTED_SCHEMES = {"http", "https", "socks4", "socks5"}

    @staticmethod
    def parse_proxy_url(proxy_url: str) -> Optional[Dict[str, str]]:
        """Parse and validate a proxy URL.

        Args:
            proxy_url: Proxy URL string.

        Returns:
            Dictionary with parsed components or None if invalid.
            Keys: scheme, host, port, username, password (optional)
        """
        if not proxy_url:
            return None

        parsed = urlparse(proxy_url)

        # Validate scheme
        if parsed.scheme not in ProxyManager.SUPPORTED_SCHEMES:
            return None

        # Must have host and port
        if not parsed.hostname or not parsed.port:
            return None

        result = {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
        }

        # Optional authentication
        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password

        return result

    @staticmethod
    def is_valid_proxy(proxy_url: str) -> bool:
        """Check if a proxy URL is valid.

        Args:
            proxy_url: Proxy URL to validate.

        Returns:
            True if valid, False otherwise.
        """
        return ProxyManager.parse_proxy_url(proxy_url) is not None

    @staticmethod
    def format_proxy_dict(proxy_url: str) -> Optional[Dict[str, str]]:
        """Format a proxy URL as a requests-compatible proxy dict.

        Handles authentication by including credentials in the URL.
        For SOCKS proxies, uses the appropriate scheme prefix.

        Args:
            proxy_url: Proxy URL string.

        Returns:
            Dict with 'http' and 'https' keys for requests library,
            or None if proxy URL is invalid.

        Example:
            {"http": "http://user:pass@proxy:8080",
             "https": "http://user:pass@proxy:8080"}
        """
        if not ProxyManager.is_valid_proxy(proxy_url):
            return None

        # For SOCKS proxies, requests uses the same URL for both
        # For HTTP proxies, we typically use the same proxy for both protocols
        return {
            "http": proxy_url,
            "https": proxy_url
        }

    def __init__(self, rotation: str = "round-robin"):
        """Initialize the ProxyManager.

        Args:
            rotation: Rotation strategy - "round-robin" or "random".
        """
        self.rotation = rotation
        self.proxies: List[str] = []
        self.failed_proxies: List[str] = []
        self.current_index: int = 0
        self.logger = setup_logger("proxy_manager")

    def add_proxy(self, proxy_url: str) -> bool:
        """Add a single proxy to the rotation pool.

        Args:
            proxy_url: Proxy URL (e.g., "http://proxy:8080", "socks5://user:pass@proxy:1080")

        Returns:
            True if proxy was added successfully, False if invalid or duplicate.
        """
        if not proxy_url or not proxy_url.strip():
            return False

        proxy_url = proxy_url.strip()

        # Avoid duplicates
        if proxy_url in self.proxies:
            self.logger.debug(f"Proxy already in pool: {proxy_url}")
            return False

        self.proxies.append(proxy_url)
        self.logger.info(f"Added proxy to pool: {proxy_url}")
        return True

    def load_from_file(self, file_path: Path) -> int:
        """Load proxies from a file (one proxy per line).

        Args:
            file_path: Path to the proxy list file.

        Returns:
            Number of proxies successfully loaded.

        File format:
            http://proxy1:8080
            http://user:pass@proxy2:8080
            socks5://proxy3:1080
            # Comments and empty lines are ignored
        """
        file_path = Path(file_path)
        if not file_path.exists():
            self.logger.error(f"Proxy file not found: {file_path}")
            return 0

        loaded_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    if self.add_proxy(line):
                        loaded_count += 1

            self.logger.info(f"Loaded {loaded_count} proxies from {file_path}")
            return loaded_count

        except Exception as e:
            self.logger.error(f"Error reading proxy file {file_path}: {e}")
            return loaded_count

    def _get_next_round_robin(self) -> Optional[str]:
        """Get next proxy using round-robin rotation.

        Returns:
            Next proxy URL in rotation, or None if pool is empty.
        """
        if not self.proxies:
            return None

        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

    def _get_next_random(self) -> Optional[str]:
        """Get next proxy using random selection.

        Returns:
            Randomly selected proxy URL, or None if pool is empty.
        """
        if not self.proxies:
            return None

        return random.choice(self.proxies)

    def get_next_proxy(self) -> Optional[str]:
        """Get the next proxy based on configured rotation strategy.

        Returns:
            Next proxy URL, or None if pool is empty.
        """
        if self.rotation == self.ROTATION_RANDOM:
            return self._get_next_random()
        else:
            # Default to round-robin
            return self._get_next_round_robin()

    @staticmethod
    def is_proxy_error(exception: Exception) -> bool:
        """Check if an exception indicates a proxy failure.

        Args:
            exception: The exception to check.

        Returns:
            True if the exception is likely caused by a proxy issue.
        """
        if not HAS_DEPENDENCIES:
            return False

        # Check for proxy-related connection errors
        error_str = str(exception).lower()
        proxy_error_indicators = [
            "proxyerror",
            "proxy",
            "tunnel",
            "connection refused",
            "connection reset",
            "connection aborted",
            "timed out",
            "timeout",
            "socks",
            "sockshttp",
        ]

        for indicator in proxy_error_indicators:
            if indicator in error_str:
                return True

        # Check exception type
        if hasattr(requests, 'exceptions'):
            if isinstance(exception, (
                requests.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            )):
                return True

        return False

    def mark_proxy_failed(self, proxy_url: str) -> bool:
        """Mark a proxy as failed and remove it from rotation.

        Args:
            proxy_url: The proxy URL that failed.

        Returns:
            True if proxy was removed, False if not found.
        """
        if proxy_url not in self.proxies:
            return False

        self.proxies.remove(proxy_url)
        self.failed_proxies.append(proxy_url)

        # Adjust current_index if needed to prevent out-of-bounds
        if self.current_index >= len(self.proxies) and self.proxies:
            self.current_index = 0

        self.logger.warning(f"Removed failed proxy from pool: {proxy_url}")
        self.logger.info(f"Proxies remaining: {len(self.proxies)}")
        return True

    def has_proxies(self) -> bool:
        """Check if there are any proxies available in the pool.

        Returns:
            True if at least one proxy is available.
        """
        return len(self.proxies) > 0

    def proxy_count(self) -> int:
        """Get the number of active proxies in the pool.

        Returns:
            Number of proxies currently available.
        """
        return len(self.proxies)

    def failed_count(self) -> int:
        """Get the number of failed proxies.

        Returns:
            Number of proxies that have been marked as failed.
        """
        return len(self.failed_proxies)

    def get_current_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Get the current proxy formatted for requests library.

        Returns:
            Proxy dict for requests, or None if no proxies available.
        """
        proxy_url = self.get_next_proxy()
        if proxy_url:
            return self.format_proxy_dict(proxy_url)
        return None


class WebScraper:
    """Scrapes web pages and extracts structured data."""

    # Robots.txt mode constants
    ROBOTS_WARN = "warn"      # Default: check and warn but don't block
    ROBOTS_RESPECT = "respect"  # Enforce: skip disallowed URLs
    ROBOTS_IGNORE = "ignore"   # Skip checking entirely

    def __init__(
        self,
        dedupe_file: Optional[Path] = None,
        delay: Optional[float] = None,
        random_delay: Optional[tuple] = None,
        respect_rate_limits: bool = False,
        robots_mode: str = "warn",
        proxy: Optional[str] = None,
        proxy_file: Optional[Path] = None,
        proxy_rotation: str = "round-robin"
    ):
        self.logger = setup_logger("web_scraper")
        self.config = WEB_SCRAPER_CONFIG
        self.session = requests.Session() if HAS_DEPENDENCIES else None
        self.dedupe_file = dedupe_file or (DATA_DIR / "scraped" / "seen_urls.json")
        self.seen_urls = set(load_json(self.dedupe_file).get("urls", []))

        # Rate limiting configuration
        self.delay = delay if delay is not None else self.config["delay"]
        self.random_delay = random_delay or self.config["random_delay"]
        self.respect_rate_limits = respect_rate_limits or self.config["respect_rate_limits"]

        # Robots.txt configuration
        self.robots_mode = robots_mode
        self.robots_checker = None
        if robots_mode != self.ROBOTS_IGNORE:
            self.robots_checker = RobotsChecker(
                user_agent=self.config["user_agent"]
            )

        # Proxy configuration
        self.proxy_manager: Optional[ProxyManager] = None
        self.current_proxy: Optional[str] = None
        if proxy or proxy_file:
            self.proxy_manager = ProxyManager(rotation=proxy_rotation)
            if proxy:
                self.proxy_manager.add_proxy(proxy)
            if proxy_file:
                self.proxy_manager.load_from_file(Path(proxy_file))

        # Statistics
        self.request_count = 0
        self.total_delay_time = 0.0
        self.start_time = None
        self.blocked_urls: List[str] = []  # URLs blocked by robots.txt

        if self.session:
            self.session.headers.update({
                "User-Agent": self.config["user_agent"]
            })

    @staticmethod
    def parse_random_delay(delay_str: str) -> Optional[tuple]:
        """Parse a random delay range string like '1-5' into (min, max) tuple.

        Args:
            delay_str: A string in format 'min-max' (e.g., '1-5' or '0.5-2')

        Returns:
            Tuple of (min, max) floats, or None if parsing fails.
        """
        try:
            parts = delay_str.split('-')
            if len(parts) != 2:
                return None
            min_delay = float(parts[0])
            max_delay = float(parts[1])
            if min_delay < 0 or max_delay < 0 or min_delay > max_delay:
                return None
            return (min_delay, max_delay)
        except (ValueError, IndexError):
            return None

    def _parse_rate_limit_headers(self, response) -> Optional[float]:
        """Parse rate limit headers from server response.

        Supports common rate limiting headers:
        - Retry-After: seconds to wait before retrying
        - X-RateLimit-Reset: Unix timestamp when rate limit resets
        - X-RateLimit-Remaining: if 0, wait until reset

        Returns delay in seconds, or None if no rate limiting detected.
        """
        headers = response.headers

        # Check Retry-After header (429 responses typically include this)
        retry_after = headers.get('Retry-After')
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                # Retry-After can be a date string, ignore for now
                pass

        # Check X-RateLimit headers
        remaining = headers.get('X-RateLimit-Remaining')
        reset = headers.get('X-RateLimit-Reset')

        if remaining is not None and reset:
            try:
                if int(remaining) == 0:
                    reset_time = int(reset)
                    current_time = int(time.time())
                    if reset_time > current_time:
                        return float(reset_time - current_time)
            except (ValueError, TypeError):
                pass

        return None

    def _wait(self, response=None, url: str = None) -> float:
        """Apply rate limiting delay between requests.

        Uses random delay if configured, otherwise uses fixed delay.
        If respect_rate_limits is enabled and response contains rate limit
        headers, that delay takes priority.
        If robots.txt Crawl-delay is set, it's used as a minimum delay.

        Args:
            response: HTTP response to check for rate limit headers.
            url: URL being fetched (for Crawl-delay lookup).

        Returns the actual delay applied in seconds.
        """
        actual_delay = 0.0

        # Check server rate limit headers if enabled
        if self.respect_rate_limits and response is not None:
            server_delay = self._parse_rate_limit_headers(response)
            if server_delay is not None and server_delay > 0:
                self.logger.info(f"Rate limit detected, waiting {server_delay:.1f}s")
                time.sleep(server_delay)
                return server_delay

        # Get robots.txt Crawl-delay as minimum
        crawl_delay = 0.0
        if url and self.robots_checker:
            cd = self.robots_checker.get_crawl_delay(url)
            if cd is not None:
                crawl_delay = cd

        if self.random_delay:
            min_delay, max_delay = self.random_delay
            actual_delay = random.uniform(min_delay, max_delay)
        elif self.delay > 0:
            actual_delay = self.delay

        # Use the larger of configured delay and Crawl-delay
        actual_delay = max(actual_delay, crawl_delay)

        if actual_delay > 0:
            time.sleep(actual_delay)

        return actual_delay

    def get_rate_stats(self) -> Dict[str, float]:
        """Get request rate statistics.

        Returns a dictionary with:
        - request_count: total number of requests made
        - total_delay_time: total time spent waiting (seconds)
        - elapsed_time: total time since first request (seconds)
        - avg_delay: average delay per request (seconds)
        - requests_per_minute: effective request rate
        - blocked_by_robots: count of URLs blocked by robots.txt
        - proxies_active: number of active proxies (if proxy configured)
        - proxies_failed: number of failed proxies (if proxy configured)
        """
        elapsed = 0.0
        if self.start_time is not None:
            elapsed = time.time() - self.start_time

        avg_delay = 0.0
        if self.request_count > 0:
            avg_delay = self.total_delay_time / self.request_count

        rpm = 0.0
        if elapsed > 0:
            rpm = (self.request_count / elapsed) * 60

        stats = {
            "request_count": self.request_count,
            "total_delay_time": round(self.total_delay_time, 2),
            "elapsed_time": round(elapsed, 2),
            "avg_delay": round(avg_delay, 2),
            "requests_per_minute": round(rpm, 1),
            "blocked_by_robots": len(self.blocked_urls)
        }

        # Add proxy statistics if proxy manager is configured
        if self.proxy_manager:
            stats["proxies_active"] = self.proxy_manager.proxy_count()
            stats["proxies_failed"] = self.proxy_manager.failed_count()

        return stats

    def check_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt based on current mode.

        Args:
            url: The URL to check.

        Returns:
            True if the URL should be fetched, False if blocked.
        """
        if self.robots_mode == self.ROBOTS_IGNORE or not self.robots_checker:
            return True

        allowed = self.robots_checker.can_fetch(url)

        if not allowed:
            if self.robots_mode == self.ROBOTS_RESPECT:
                self.logger.warning(f"Skipping URL disallowed by robots.txt: {url}")
                self.blocked_urls.append(url)
                return False
            else:  # ROBOTS_WARN
                self.logger.warning(f"WARNING: URL is disallowed by robots.txt: {url}")

        return True

    def _get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Get the current proxy configuration for requests.

        Returns:
            Proxy dict for requests library, or None if no proxies configured.
        """
        if not self.proxy_manager or not self.proxy_manager.has_proxies():
            return None

        proxy_url = self.proxy_manager.get_next_proxy()
        if proxy_url:
            self.current_proxy = proxy_url
            return ProxyManager.format_proxy_dict(proxy_url)
        return None

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL with retry logic, rate limiting, proxy support, and robots.txt checking."""
        if not HAS_DEPENDENCIES:
            self.logger.error("Missing dependencies. Run: pip install requests beautifulsoup4")
            return None

        # Check robots.txt before fetching
        if not self.check_robots(url):
            return None

        # Track start time on first request
        if self.start_time is None:
            self.start_time = time.time()

        # Apply rate limiting delay before request (except first)
        if self.request_count > 0:
            delay_applied = self._wait(url=url)
            self.total_delay_time += delay_applied

        # Get proxy configuration
        proxy_dict = self._get_proxy_dict()
        if proxy_dict:
            self.logger.debug(f"Using proxy: {self.current_proxy}")

        for attempt in range(self.config["retry_attempts"]):
            try:
                response = self.session.get(
                    url,
                    timeout=self.config["timeout"],
                    proxies=proxy_dict
                )
                self.request_count += 1

                # Check for rate limit headers and wait if needed
                if self.respect_rate_limits:
                    header_delay = self._wait(response, url=url)
                    if header_delay > 0:
                        self.total_delay_time += header_delay

                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")

            except requests.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")

                # Check if this is a proxy error and handle it
                if proxy_dict and self.proxy_manager and ProxyManager.is_proxy_error(e):
                    self.logger.warning(f"Proxy failure detected: {self.current_proxy}")
                    self.proxy_manager.mark_proxy_failed(self.current_proxy)

                    # Try next proxy if available
                    if self.proxy_manager.has_proxies():
                        proxy_dict = self._get_proxy_dict()
                        self.logger.info(f"Switching to next proxy: {self.current_proxy}")
                        continue
                    else:
                        # All proxies exhausted, fall back to direct connection
                        self.logger.warning("All proxies exhausted, falling back to direct connection")
                        proxy_dict = None

                if attempt < self.config["retry_attempts"] - 1:
                    time.sleep(self.config["retry_delay"])

        self.logger.error(f"Failed to fetch: {url}")
        return None

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract all links from a page."""
        results = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(base_url, href)
            text = link.get_text(strip=True)

            if text and full_url.startswith("http"):
                results.append({
                    "title": text[:200],  # Truncate long titles
                    "url": full_url,
                    "scraped_at": datetime.now().isoformat()
                })
        return results

    def extract_by_selector(
        self,
        soup: BeautifulSoup,
        selector: str,
        base_url: str
    ) -> List[Dict[str, str]]:
        """Extract elements matching a CSS selector."""
        results = []
        for element in soup.select(selector):
            item = {
                "text": element.get_text(strip=True)[:500],
                "scraped_at": datetime.now().isoformat()
            }

            # Try to find associated link
            link = element.find("a", href=True) or element.find_parent("a", href=True)
            if link:
                item["url"] = urljoin(base_url, link["href"])

            results.append(item)
        return results

    def scrape_hacker_news(self, url: str = "https://news.ycombinator.com") -> List[Dict[str, str]]:
        """Scrape Hacker News front page stories."""
        soup = self.fetch(url)
        if not soup:
            return []

        results = []
        # HN uses specific class names for stories
        for item in soup.select("tr.athing"):
            title_elem = item.select_one("span.titleline > a")
            if not title_elem:
                continue

            story_id = item.get("id", "")
            title = title_elem.get_text(strip=True)
            link = title_elem["href"]

            # Get score and comments from next sibling row
            subtext = item.find_next_sibling("tr")
            score = "0"
            comments = "0"

            if subtext:
                score_elem = subtext.select_one("span.score")
                if score_elem:
                    score = score_elem.get_text(strip=True).replace(" points", "")

                comment_links = subtext.select("a")
                for a in comment_links:
                    text = a.get_text(strip=True)
                    if "comment" in text:
                        comments = text.split()[0]
                        break

            results.append({
                "id": story_id,
                "title": title,
                "url": link if link.startswith("http") else urljoin(url, link),
                "score": score,
                "comments": comments,
                "scraped_at": datetime.now().isoformat()
            })

        return results

    def scrape_generic(
        self,
        url: str,
        selector: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Generic scraping - extracts links or uses custom selector."""
        soup = self.fetch(url)
        if not soup:
            return []

        if selector:
            return self.extract_by_selector(soup, selector, url)
        else:
            return self.extract_links(soup, url)

    def scrape_paginated(
        self,
        base_url: str,
        selector: Optional[str] = None,
        max_pages: int = 10,
        page_param: str = "page"
    ) -> List[Dict[str, str]]:
        """Scrape multiple pages with rate limiting between requests.

        Args:
            base_url: Base URL (page parameter will be appended)
            selector: Optional CSS selector for extraction
            max_pages: Maximum number of pages to scrape
            page_param: URL parameter name for pagination (default: 'page')

        Returns:
            Combined list of all scraped items from all pages.
        """
        all_items = []

        for page in range(1, max_pages + 1):
            # Build paginated URL
            separator = "&" if "?" in base_url else "?"
            url = f"{base_url}{separator}{page_param}={page}"

            self.logger.info(f"Scraping page {page}/{max_pages}: {url}")
            items = self.scrape_generic(url, selector)

            if not items:
                self.logger.info(f"No items found on page {page}, stopping pagination")
                break

            all_items.extend(items)

        return all_items

    def dedupe(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove items we've already seen (by URL)."""
        new_items = []
        for item in items:
            url = item.get("url", "")
            if url and url not in self.seen_urls:
                new_items.append(item)
                self.seen_urls.add(url)

        # Save updated seen URLs
        save_json({"urls": list(self.seen_urls)}, self.dedupe_file)
        return new_items

    def save_to_csv(
        self,
        items: List[Dict[str, str]],
        output_path: Path,
        append: bool = False
    ) -> bool:
        """Save scraped items to CSV."""
        if not items:
            self.logger.warning("No items to save")
            return False

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        mode = 'a' if append and output_path.exists() else 'w'
        write_header = mode == 'w' or not output_path.exists()

        try:
            with open(output_path, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=items[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(items)

            self.logger.info(f"Saved {len(items)} items to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving CSV: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Scrape web pages and save data to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://news.ycombinator.com --output stories.csv
  %(prog)s https://example.com --selector "h2.title" --output titles.csv
  %(prog)s https://example.com --dedupe --append --output data.csv

Rate limiting:
  %(prog)s https://example.com --delay 2 --output data.csv
  %(prog)s https://example.com --random-delay 1-5 --output data.csv
  %(prog)s https://example.com --respect-rate-limits --output data.csv

Robots.txt compliance:
  %(prog)s https://example.com --respect-robots --output data.csv
  %(prog)s https://example.com --ignore-robots --output data.csv

Preset scrapers:
  %(prog)s --preset hackernews --output hn.csv
        """
    )

    parser.add_argument("url", nargs="?", help="URL to scrape")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output CSV file")
    parser.add_argument("--selector", "-s", help="CSS selector to extract elements")
    parser.add_argument("--preset", choices=["hackernews"], help="Use a preset scraper")
    parser.add_argument("--dedupe", "-d", action="store_true", help="Skip URLs seen before")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing CSV")
    # Rate limiting options
    parser.add_argument("--delay", type=float, metavar="SECONDS",
                        help="Fixed delay between requests (seconds)")
    parser.add_argument("--random-delay", metavar="MIN-MAX",
                        help="Random delay range (e.g., '1-5' for 1-5 seconds)")
    parser.add_argument("--respect-rate-limits", action="store_true",
                        help="Honor server rate limit headers (Retry-After, X-RateLimit)")
    # Robots.txt options (mutually exclusive)
    robots_group = parser.add_mutually_exclusive_group()
    robots_group.add_argument("--respect-robots", action="store_true",
                              help="Enforce robots.txt rules (skip disallowed URLs)")
    robots_group.add_argument("--ignore-robots", action="store_true",
                              help="Ignore robots.txt checking entirely")
    # Proxy options
    parser.add_argument("--proxy", metavar="URL",
                        help="Single proxy URL (e.g., 'http://proxy:8080', 'socks5://proxy:1080')")
    parser.add_argument("--proxy-file", type=Path, metavar="FILE",
                        help="File containing proxy list (one per line)")

    args = parser.parse_args()

    if not HAS_DEPENDENCIES:
        print("ERROR: Missing dependencies. Install with:")
        print("  pip install requests beautifulsoup4")
        sys.exit(1)

    # Parse rate limiting options
    random_delay = None
    if args.random_delay:
        random_delay = WebScraper.parse_random_delay(args.random_delay)
        if random_delay is None:
            parser.error("Invalid random delay format. Use 'min-max' (e.g., '1-5')")

    # Determine robots mode
    if args.respect_robots:
        robots_mode = WebScraper.ROBOTS_RESPECT
    elif args.ignore_robots:
        robots_mode = WebScraper.ROBOTS_IGNORE
    else:
        robots_mode = WebScraper.ROBOTS_WARN

    scraper = WebScraper(
        delay=args.delay,
        random_delay=random_delay,
        respect_rate_limits=args.respect_rate_limits,
        robots_mode=robots_mode,
        proxy=args.proxy,
        proxy_file=args.proxy_file
    )

    # Use preset or generic scraper
    if args.preset == "hackernews":
        items = scraper.scrape_hacker_news()
    elif args.url:
        items = scraper.scrape_generic(args.url, args.selector)
    else:
        parser.error("Either URL or --preset is required")
        return

    print(f"Scraped {len(items)} items")

    # Dedupe if requested
    if args.dedupe:
        original_count = len(items)
        items = scraper.dedupe(items)
        print(f"After deduplication: {len(items)} new items (skipped {original_count - len(items)})")

    # Save results
    if items:
        scraper.save_to_csv(items, args.output, append=args.append)
    else:
        print("No new items to save")

    # Print statistics
    stats = scraper.get_rate_stats()
    if args.delay or args.random_delay or args.respect_rate_limits:
        print(f"\nRate stats: {stats['request_count']} requests, "
              f"{stats['total_delay_time']}s delay, "
              f"{stats['requests_per_minute']} req/min")

    # Print robots.txt statistics if applicable
    if stats['blocked_by_robots'] > 0:
        print(f"Robots.txt: {stats['blocked_by_robots']} URLs blocked")


if __name__ == "__main__":
    main()
