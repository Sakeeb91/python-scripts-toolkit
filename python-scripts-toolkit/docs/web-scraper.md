# Web Scraper + Saver - Technical Documentation

A Python script that fetches web pages, extracts structured data using CSS selectors, and saves results to CSV files with deduplication support.

## Table of Contents

- [Concepts Overview](#concepts-overview)
- [Technologies Used](#technologies-used)
- [Core Code Explained](#core-code-explained)
- [HTTP and Web Fundamentals](#http-and-web-fundamentals)
- [HTML Parsing Patterns](#html-parsing-patterns)
- [Ethical Scraping](#ethical-scraping)
- [Extending the Project](#extending-the-project)

---

## Concepts Overview

### What Problem Does This Solve?

The web contains vast amounts of data that isn't available via APIs—news headlines, job listings, product prices, etc. Web scraping automates the extraction of this data by:

1. **Fetching** HTML pages via HTTP requests
2. **Parsing** the HTML structure into a navigable tree
3. **Extracting** specific elements using CSS selectors
4. **Saving** structured data to CSV for analysis

### How Web Scraping Works

```
┌──────────────┐      HTTP GET      ┌──────────────┐
│   Python     │  ───────────────>  │  Web Server  │
│   Script     │                    │              │
│              │  <───────────────  │              │
└──────────────┘    HTML Response   └──────────────┘
       │
       ▼
┌──────────────┐
│    Parse     │
│    HTML      │──> BeautifulSoup Tree
│              │
└──────────────┘
       │
       ▼
┌──────────────┐
│   Extract    │
│   Data       │──> [{'title': '...', 'url': '...'}]
│              │
└──────────────┘
       │
       ▼
┌──────────────┐
│   Save to    │
│   CSV        │──> output.csv
└──────────────┘
```

---

## Technologies Used

### External Libraries

| Library | Purpose | Installation |
|---------|---------|--------------|
| `requests` | HTTP requests | `pip install requests` |
| `beautifulsoup4` | HTML parsing | `pip install beautifulsoup4` |

### Standard Library Modules

| Module | Purpose |
|--------|---------|
| `csv` | Writing extracted data |
| `time` | Retry delays |
| `urllib.parse` | URL manipulation |
| `datetime` | Timestamps |

### Why These Libraries?

**requests vs urllib:**
```python
# urllib (standard library) - verbose
import urllib.request
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
html = response.read().decode('utf-8')

# requests (third-party) - clean and simple
import requests
response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
html = response.text
```

**BeautifulSoup vs regex:**
```python
# Regex - fragile, breaks easily
import re
titles = re.findall(r'<h2 class="title">(.*?)</h2>', html)

# BeautifulSoup - understands HTML structure
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')
titles = [h2.text for h2 in soup.select('h2.title')]
```

---

## Core Code Explained

### 1. HTTP Requests with Retry Logic

```python
def fetch(self, url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL with retry logic."""

    for attempt in range(self.config["retry_attempts"]):  # Default: 3
        try:
            response = self.session.get(
                url,
                timeout=self.config["timeout"]  # Default: 10 seconds
            )
            response.raise_for_status()  # Raise exception for 4xx/5xx
            return BeautifulSoup(response.text, "html.parser")

        except requests.RequestException as e:
            self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < self.config["retry_attempts"] - 1:
                time.sleep(self.config["retry_delay"])  # Wait before retry

    self.logger.error(f"Failed to fetch: {url}")
    return None
```

**Key concepts:**

1. **Session reuse:** `self.session = requests.Session()` maintains cookies and connection pooling
2. **Timeout:** Prevents hanging on slow/dead servers
3. **Retry pattern:** Handles transient network errors
4. **raise_for_status():** Converts HTTP errors to exceptions

**HTTP status codes:**
```
2xx - Success (200 OK)
3xx - Redirect (301 Moved, 302 Found)
4xx - Client error (404 Not Found, 403 Forbidden)
5xx - Server error (500 Internal Error, 503 Service Unavailable)
```

### 2. Setting Up Request Headers

```python
def __init__(self, ...):
    self.session = requests.Session()
    self.session.headers.update({
        "User-Agent": self.config["user_agent"]
    })

# In config.py
WEB_SCRAPER_CONFIG = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    # ...
}
```

**Why set User-Agent?**
- Default requests User-Agent is `python-requests/2.x.x`
- Many sites block or limit requests from known bots
- Browser-like User-Agent improves success rate

### 3. Parsing HTML with BeautifulSoup

```python
soup = BeautifulSoup(response.text, "html.parser")
```

**Parser options:**
| Parser | Speed | Lenient | Install |
|--------|-------|---------|---------|
| `html.parser` | Medium | Medium | Built-in |
| `lxml` | Fast | Medium | `pip install lxml` |
| `html5lib` | Slow | Very | `pip install html5lib` |

**Navigation methods:**
```python
# Find single element
soup.find('h1')                      # First <h1>
soup.find('div', class_='content')   # First <div class="content">
soup.find('a', href=True)            # First <a> with href attribute

# Find all elements
soup.find_all('p')                   # All <p> tags
soup.find_all(['h1', 'h2', 'h3'])   # All h1, h2, h3 tags

# CSS selectors (most powerful)
soup.select('div.article h2')        # h2 inside div.article
soup.select('a[href^="https"]')      # Links starting with https
soup.select('#main > p:first-child') # First p directly under #main
```

### 4. Extracting Links from a Page

```python
def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """Extract all links from a page."""
    results = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(base_url, href)  # Handle relative URLs
        text = link.get_text(strip=True)

        if text and full_url.startswith("http"):
            results.append({
                "title": text[:200],  # Truncate long titles
                "url": full_url,
                "scraped_at": datetime.now().isoformat()
            })

    return results
```

**URL handling with urljoin:**
```python
from urllib.parse import urljoin

base = "https://example.com/page/"
urljoin(base, "article")           # https://example.com/page/article
urljoin(base, "/about")            # https://example.com/about
urljoin(base, "../other")          # https://example.com/other
urljoin(base, "https://x.com")     # https://x.com (absolute unchanged)
```

### 5. Custom CSS Selector Extraction

```python
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
```

**CSS selector examples:**
```css
/* Element selectors */
h2                    /* All h2 elements */
div p                 /* p inside div (any depth) */
div > p               /* p directly inside div */

/* Class and ID */
.article              /* class="article" */
#main                 /* id="main" */
div.content           /* div with class="content" */

/* Attributes */
a[href]              /* a with href attribute */
a[href^="https"]     /* href starts with "https" */
a[href$=".pdf"]      /* href ends with ".pdf" */
a[href*="download"]  /* href contains "download" */

/* Pseudo-selectors */
li:first-child       /* First li in its parent */
li:nth-child(2)      /* Second li */
li:last-child        /* Last li */
```

### 6. Hacker News Scraper (Real Example)

```python
def scrape_hacker_news(self, url: str = "https://news.ycombinator.com") -> List[Dict]:
    """Scrape Hacker News front page stories."""
    soup = self.fetch(url)
    if not soup:
        return []

    results = []

    # HN structure: each story is a <tr class="athing">
    for item in soup.select("tr.athing"):
        title_elem = item.select_one("span.titleline > a")
        if not title_elem:
            continue

        story_id = item.get("id", "")
        title = title_elem.get_text(strip=True)
        link = title_elem["href"]

        # Score and comments are in the NEXT row
        subtext = item.find_next_sibling("tr")
        score = "0"
        comments = "0"

        if subtext:
            score_elem = subtext.select_one("span.score")
            if score_elem:
                score = score_elem.get_text(strip=True).replace(" points", "")

            # Find comments link
            for a in subtext.select("a"):
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
```

**Understanding HN's HTML structure:**
```html
<tr class="athing" id="12345">
  <td class="title">
    <span class="titleline">
      <a href="https://example.com">Story Title</a>
    </span>
  </td>
</tr>
<tr>
  <td class="subtext">
    <span class="score">142 points</span>
    ...
    <a href="item?id=12345">85 comments</a>
  </td>
</tr>
```

### 7. URL Deduplication

```python
def __init__(self, dedupe_file: Optional[Path] = None):
    self.dedupe_file = dedupe_file or (DATA_DIR / "scraped" / "seen_urls.json")
    self.seen_urls = set(load_json(self.dedupe_file).get("urls", []))

def dedupe(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Remove items we've already seen (by URL)."""
    new_items = []

    for item in items:
        url = item.get("url", "")
        if url and url not in self.seen_urls:
            new_items.append(item)
            self.seen_urls.add(url)

    # Persist updated seen URLs
    save_json({"urls": list(self.seen_urls)}, self.dedupe_file)
    return new_items
```

**Why sets for deduplication?**
```python
# List lookup: O(n) - slow for large lists
if url in seen_list:  # Scans entire list

# Set lookup: O(1) - constant time
if url in seen_set:   # Hash table lookup
```

---

## HTTP and Web Fundamentals

### The HTTP Request/Response Cycle

```
Client                              Server
  │                                   │
  │  GET /page HTTP/1.1               │
  │  Host: example.com                │
  │  User-Agent: Mozilla/5.0          │
  │ ────────────────────────────────> │
  │                                   │
  │  HTTP/1.1 200 OK                  │
  │  Content-Type: text/html          │
  │                                   │
  │  <html>...</html>                 │
  │ <──────────────────────────────── │
```

### Common HTTP Headers

```python
headers = {
    # Identify the client
    "User-Agent": "Mozilla/5.0 ...",

    # What content types we accept
    "Accept": "text/html,application/xhtml+xml",

    # Language preference
    "Accept-Language": "en-US,en;q=0.9",

    # Where we came from (for some sites)
    "Referer": "https://google.com/",
}
```

### Handling Different Response Types

```python
response = requests.get(url)

# Check content type
content_type = response.headers.get('Content-Type', '')

if 'text/html' in content_type:
    soup = BeautifulSoup(response.text, 'html.parser')
elif 'application/json' in content_type:
    data = response.json()
elif 'text/csv' in content_type:
    # Parse as CSV
    lines = response.text.splitlines()
```

---

## HTML Parsing Patterns

### Navigating the DOM Tree

```python
soup = BeautifulSoup(html, 'html.parser')

# Navigate down
soup.body.div.p              # First p in first div in body
soup.find('div').children    # Direct children (iterator)
soup.find('div').descendants # All descendants (iterator)

# Navigate up
element.parent               # Direct parent
element.parents              # All ancestors (iterator)
element.find_parent('div')   # First div ancestor

# Navigate sideways
element.next_sibling         # Next sibling node
element.previous_sibling     # Previous sibling node
element.find_next_sibling('p')  # Next p sibling
```

### Extracting Text and Attributes

```python
element = soup.find('a', class_='link')

# Get text content
element.text                 # Raw text (includes whitespace)
element.get_text()           # Same as .text
element.get_text(strip=True) # Stripped whitespace
element.get_text(' ', strip=True)  # Join with space

# Get attributes
element['href']              # Raises KeyError if missing
element.get('href')          # Returns None if missing
element.get('href', '')      # Returns '' if missing
element.attrs                # All attributes as dict
```

### Common Scraping Patterns

**Pattern 1: List of items**
```python
# Structure: <ul><li>Item 1</li><li>Item 2</li></ul>
items = [li.text for li in soup.select('ul li')]
```

**Pattern 2: Table data**
```python
# Structure: <table><tr><td>Name</td><td>Value</td></tr></table>
rows = []
for tr in soup.select('table tr'):
    cells = [td.text.strip() for td in tr.select('td')]
    if cells:
        rows.append(cells)
```

**Pattern 3: Article cards**
```python
# Structure: <div class="card"><h2>Title</h2><p>Desc</p><a href="..."></div>
articles = []
for card in soup.select('div.card'):
    articles.append({
        'title': card.select_one('h2').text,
        'description': card.select_one('p').text,
        'link': card.select_one('a')['href']
    })
```

---

## Ethical Scraping

### Best Practices

1. **Respect robots.txt**
   ```python
   from urllib.robotparser import RobotFileParser

   rp = RobotFileParser()
   rp.set_url("https://example.com/robots.txt")
   rp.read()

   if rp.can_fetch("*", "/page"):
       # OK to scrape
   ```

2. **Rate limiting**
   ```python
   import time

   for url in urls:
       data = scrape(url)
       time.sleep(1)  # Wait 1 second between requests
   ```

3. **Identify yourself**
   ```python
   headers = {
       "User-Agent": "MyBot/1.0 (contact@example.com)"
   }
   ```

4. **Cache responses**
   ```python
   import requests_cache

   session = requests_cache.CachedSession('scraper_cache')
   response = session.get(url)  # Cached for subsequent runs
   ```

### Legal Considerations

- **Terms of Service:** Check if scraping is allowed
- **Copyright:** Extracted content may be copyrighted
- **Personal Data:** GDPR/CCPA may apply
- **Rate Limits:** Excessive requests may be illegal (CFAA)

---

## Extending the Project

### 1. Add Pagination Support

```python
def scrape_all_pages(self, base_url: str, max_pages: int = 10):
    """Scrape multiple pages."""
    all_items = []

    for page in range(1, max_pages + 1):
        url = f"{base_url}?page={page}"
        soup = self.fetch(url)

        items = self.extract_items(soup)
        if not items:
            break  # No more pages

        all_items.extend(items)
        time.sleep(1)  # Be polite

    return all_items
```

### 2. Handle JavaScript-Rendered Pages

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def fetch_with_js(url: str) -> str:
    """Fetch page that requires JavaScript."""
    options = Options()
    options.add_argument('--headless')

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Wait for content to load
    time.sleep(2)

    html = driver.page_source
    driver.quit()

    return html
```

### 3. Add Proxy Support

```python
def fetch_with_proxy(self, url: str, proxy: str):
    """Fetch through a proxy server."""
    proxies = {
        'http': proxy,
        'https': proxy,
    }
    return self.session.get(url, proxies=proxies)
```

### 4. Export to Database

```python
import sqlite3

def save_to_db(items: List[Dict], db_path: str):
    """Save scraped items to SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            title TEXT,
            url TEXT UNIQUE,
            scraped_at TEXT
        )
    ''')

    for item in items:
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO items (title, url, scraped_at) VALUES (?, ?, ?)',
                (item['title'], item['url'], item['scraped_at'])
            )
        except sqlite3.Error:
            continue

    conn.commit()
    conn.close()
```

---

## Summary

The Web Scraper teaches these core concepts:

| Concept | How It's Used |
|---------|---------------|
| HTTP requests | Fetching web pages |
| BeautifulSoup | Parsing HTML |
| CSS selectors | Finding elements |
| Sessions | Connection reuse |
| Error handling | Retries, timeouts |
| URL manipulation | urljoin, parsing |
| Deduplication | Sets for O(1) lookup |
| Data persistence | CSV export, JSON state |

This is a practical introduction to web scraping that demonstrates patterns used in production scrapers while emphasizing ethical practices.
