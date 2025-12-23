"""
Web Scraper + Saver - Fetches web pages and saves structured data to CSV.

Usage:
    python -m projects.web_scraper.scraper https://news.ycombinator.com --output hn_stories.csv
    python -m projects.web_scraper.scraper https://example.com --selector "h2.title" --output titles.csv
"""
import argparse
import csv
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
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


class WebScraper:
    """Scrapes web pages and extracts structured data."""

    def __init__(self, dedupe_file: Optional[Path] = None):
        self.logger = setup_logger("web_scraper")
        self.config = WEB_SCRAPER_CONFIG
        self.session = requests.Session() if HAS_DEPENDENCIES else None
        self.dedupe_file = dedupe_file or (DATA_DIR / "scraped" / "seen_urls.json")
        self.seen_urls = set(load_json(self.dedupe_file).get("urls", []))

        if self.session:
            self.session.headers.update({
                "User-Agent": self.config["user_agent"]
            })

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL with retry logic."""
        if not HAS_DEPENDENCIES:
            self.logger.error("Missing dependencies. Run: pip install requests beautifulsoup4")
            return None

        for attempt in range(self.config["retry_attempts"]):
            try:
                response = self.session.get(
                    url,
                    timeout=self.config["timeout"]
                )
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")

            except requests.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
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

    args = parser.parse_args()

    if not HAS_DEPENDENCIES:
        print("ERROR: Missing dependencies. Install with:")
        print("  pip install requests beautifulsoup4")
        sys.exit(1)

    scraper = WebScraper()

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


if __name__ == "__main__":
    main()
