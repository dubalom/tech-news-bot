import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from config import MAX_ARTICLES_PER_SITE

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_rss(rss_url: str) -> list[dict]:
    """Fetch articles from an RSS feed."""
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries[:MAX_ARTICLES_PER_SITE]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            # Strip HTML tags from summary
            if summary:
                soup = BeautifulSoup(summary, "html.parser")
                summary = soup.get_text(separator=" ").strip()
            link = entry.get("link", "")
            if title:
                articles.append({"title": title, "summary": summary[:500], "url": link})
        return articles
    except Exception as e:
        logger.warning(f"RSS fetch failed for {rss_url}: {e}")
        return []


def fetch_html_bloomberg(url: str) -> list[dict]:
    """Scrape Bloomberg Technology headlines."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        # Bloomberg uses data-component or specific classes
        for tag in soup.find_all(["h1", "h2", "h3"], limit=30):
            text = tag.get_text(strip=True)
            if len(text) > 20:  # Filter noise
                link_tag = tag.find_parent("a") or tag.find("a")
                url_href = link_tag["href"] if link_tag and link_tag.get("href") else ""
                if url_href and not url_href.startswith("http"):
                    url_href = "https://www.bloomberg.com" + url_href
                articles.append({"title": text, "summary": "", "url": url_href})
                if len(articles) >= MAX_ARTICLES_PER_SITE:
                    break
        return articles
    except Exception as e:
        logger.warning(f"HTML scrape failed for {url}: {e}")
        return []


def fetch_html_wsj(url: str) -> list[dict]:
    """Scrape WSJ Tech headlines."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        for tag in soup.find_all(["h2", "h3"], limit=30):
            text = tag.get_text(strip=True)
            if len(text) > 20:
                link_tag = tag.find_parent("a") or tag.find("a")
                url_href = link_tag["href"] if link_tag and link_tag.get("href") else ""
                if url_href and not url_href.startswith("http"):
                    url_href = "https://www.wsj.com" + url_href
                articles.append({"title": text, "summary": "", "url": url_href})
                if len(articles) >= MAX_ARTICLES_PER_SITE:
                    break
        return articles
    except Exception as e:
        logger.warning(f"HTML scrape failed for {url}: {e}")
        return []


def fetch_site_articles(site: dict) -> list[dict]:
    """Fetch articles for a site using RSS if available, else HTML scraping."""
    name = site["name"]
    rss = site.get("rss")
    url = site["url"]

    if rss:
        articles = fetch_rss(rss)
        if articles:
            logger.info(f"[{name}] Fetched {len(articles)} articles via RSS")
            return articles
        logger.warning(f"[{name}] RSS failed, falling back to HTML")

    # Site-specific HTML scrapers
    if "bloomberg" in url:
        articles = fetch_html_bloomberg(url)
    elif "wsj.com" in url:
        articles = fetch_html_wsj(url)
    else:
        articles = fetch_html_generic(url)

    logger.info(f"[{name}] Fetched {len(articles)} articles via HTML")
    return articles


def fetch_html_generic(url: str) -> list[dict]:
    """Generic HTML scraper — extracts all h2/h3 headlines."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        seen = set()
        for tag in soup.find_all(["h2", "h3"], limit=50):
            text = tag.get_text(strip=True)
            if len(text) < 20 or text in seen:
                continue
            seen.add(text)
            link_tag = tag.find_parent("a") or tag.find("a")
            url_href = ""
            if link_tag and link_tag.get("href"):
                url_href = link_tag["href"]
                if not url_href.startswith("http"):
                    from urllib.parse import urljoin
                    url_href = urljoin(url, url_href)
            articles.append({"title": text, "summary": "", "url": url_href})
            if len(articles) >= MAX_ARTICLES_PER_SITE:
                break
        return articles
    except Exception as e:
        logger.warning(f"Generic HTML scrape failed for {url}: {e}")
        return []
