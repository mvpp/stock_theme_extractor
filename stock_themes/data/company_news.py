"""Company official website news provider.

Scrapes news/press releases from company websites using:
1. Sitemap discovery (sitemap.xml)
2. Common path fallback (/news, /newsroom, /press-releases, etc.)
3. Markdown conversion via external services for LLM-friendly content
"""

from __future__ import annotations

import logging
import re
import time
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests

from stock_themes.config import (
    FAKE_USER_AGENT, PROXY_URL, CACHE_DIR,
    COMPANY_NEWS_MAX_ARTICLES, COMPANY_NEWS_MAX_DEPTH,
    COMPANY_NEWS_RATE_LIMIT, COMPANY_NEWS_CACHE_TTL_HOURS,
    COMPANY_NEWS_MARKDOWN_SERVICES, COMPANY_NEWS_SITEMAP_KEYWORDS,
    COMPANY_NEWS_COMMON_PATHS,
)
from stock_themes.models import CompanyProfile, DatedArticle

logger = logging.getLogger(__name__)

# Date patterns commonly found in URLs and page content
_DATE_PATTERNS = [
    # ISO: 2025-03-15, 2025/03/15
    re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"),
    # US: March 15, 2025
    re.compile(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        re.IGNORECASE,
    ),
]

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class CompanyNewsProvider:
    """Fetch news/press releases from a company's official website."""

    name = "company_news"

    def is_available(self) -> bool:
        return True  # no API key needed

    def fetch(
        self,
        ticker: str,
        company_name: str | None = None,
        website: str | None = None,
    ) -> CompanyProfile:
        """Fetch news articles from the company's official website."""
        if not website:
            logger.debug(f"{ticker}: no website URL — skipping company news")
            return CompanyProfile(
                ticker=ticker.upper(), name=company_name or "",
                data_sources=[],
            )

        # Normalise website URL
        website = website.rstrip("/")
        if not website.startswith("http"):
            website = f"https://{website}"

        # Check cache first
        cached = self._read_cache(ticker)
        if cached is not None:
            return cached

        article_urls = self._discover_news_urls(website)
        if not article_urls:
            logger.info(f"{ticker}: no news pages found on {website}")
            return CompanyProfile(
                ticker=ticker.upper(), name=company_name or "",
                data_sources=[],
            )

        # Limit articles
        article_urls = article_urls[:COMPANY_NEWS_MAX_ARTICLES]

        dated_articles: list[DatedArticle] = []
        titles: list[str] = []

        for url in article_urls:
            time.sleep(COMPANY_NEWS_RATE_LIMIT)
            article = self._fetch_article(url)
            if article and article.title:
                dated_articles.append(article)
                titles.append(article.title)

        logger.info(
            f"{ticker}: company website yielded {len(dated_articles)} articles "
            f"from {website}"
        )

        result = CompanyProfile(
            ticker=ticker.upper(),
            name=company_name or "",
            news_titles=titles,
            dated_articles=dated_articles,
            data_sources=["company_news"] if dated_articles else [],
        )

        # Write cache
        self._write_cache(ticker, result)
        return result

    # ---- Discovery ----

    def _discover_news_urls(self, website: str) -> list[str]:
        """Find news article URLs via sitemap or common paths."""
        urls = self._try_sitemap(website)
        if urls:
            return urls

        urls = self._try_common_paths(website)
        return urls

    def _try_sitemap(self, website: str) -> list[str]:
        """Parse sitemap.xml for news/press URLs."""
        sitemap_candidates = [
            f"{website}/sitemap.xml",
            f"{website}/sitemap_index.xml",
        ]

        for sitemap_url in sitemap_candidates:
            try:
                resp = self._get(sitemap_url, timeout=15)
                if resp is None or resp.status_code != 200:
                    continue
                return self._parse_sitemap(resp.text, website)
            except Exception as e:
                logger.debug(f"Sitemap fetch failed for {sitemap_url}: {e}")

        return []

    def _parse_sitemap(self, xml_text: str, website: str) -> list[str]:
        """Extract news-related URLs from sitemap XML."""
        try:
            # Handle XML namespace
            xml_text = re.sub(r'\sxmlns="[^"]+"', "", xml_text, count=1)
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return []

        urls: list[str] = []
        keywords = COMPANY_NEWS_SITEMAP_KEYWORDS

        # Check for sitemap index (links to other sitemaps)
        for sitemap_elem in root.findall(".//sitemap/loc"):
            loc = (sitemap_elem.text or "").strip()
            if any(kw in loc.lower() for kw in keywords):
                try:
                    resp = self._get(loc, timeout=15)
                    if resp and resp.status_code == 200:
                        urls.extend(self._parse_sitemap(resp.text, website))
                except Exception:
                    pass

        # Regular URL entries
        for url_elem in root.findall(".//url/loc"):
            loc = (url_elem.text or "").strip()
            if any(kw in loc.lower() for kw in keywords):
                urls.append(loc)

        # Sort by URL (often chronological for news)
        urls.sort(reverse=True)
        return urls[:COMPANY_NEWS_MAX_ARTICLES * 2]  # pre-filter generously

    def _try_common_paths(self, website: str) -> list[str]:
        """Try common news paths and extract article links."""
        for path in COMPANY_NEWS_COMMON_PATHS:
            index_url = f"{website}{path}"
            try:
                resp = self._get(index_url, timeout=15)
                if resp and resp.status_code == 200:
                    links = self._extract_article_links(
                        resp.text, index_url, website, depth=0,
                    )
                    if links:
                        logger.debug(
                            f"Found {len(links)} article links at {index_url}"
                        )
                        return links
            except Exception as e:
                logger.debug(f"Common path {index_url} failed: {e}")
            time.sleep(COMPANY_NEWS_RATE_LIMIT)

        return []

    def _extract_article_links(
        self, html: str, page_url: str, website: str, depth: int,
    ) -> list[str]:
        """Extract article-like links from an HTML page."""
        if depth > COMPANY_NEWS_MAX_DEPTH:
            return []

        # Simple regex link extraction (avoid heavy HTML parser dependency)
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        base_domain = urlparse(website).netloc

        links: list[str] = []
        for match in href_pattern.finditer(html):
            href = match.group(1)
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)

            # Only same-domain links
            if parsed.netloc != base_domain:
                continue

            # Filter for likely article URLs (contain date or news keywords)
            path_lower = parsed.path.lower()
            has_keyword = any(kw in path_lower for kw in COMPANY_NEWS_SITEMAP_KEYWORDS)
            has_date = bool(re.search(r"\d{4}", path_lower))

            if has_keyword or has_date:
                # Avoid index/category pages (too short path segments)
                segments = [s for s in parsed.path.split("/") if s]
                if len(segments) >= 2:
                    links.append(full_url)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)

        return unique[:COMPANY_NEWS_MAX_ARTICLES]

    # ---- Article fetching ----

    def _fetch_article(self, url: str) -> DatedArticle | None:
        """Fetch an article URL and convert to DatedArticle."""
        markdown = self._url_to_markdown(url)
        if not markdown or len(markdown.strip()) < 50:
            return None

        title = self._extract_title(markdown)
        pub_date = self._extract_date(markdown, url)

        if not title:
            return None

        return DatedArticle(title=title, published_at=pub_date)

    def _url_to_markdown(self, url: str) -> str | None:
        """Convert URL to markdown using service chain."""
        for service_template in COMPANY_NEWS_MARKDOWN_SERVICES:
            service_url = service_template.format(url=url)
            try:
                resp = self._get(service_url, timeout=30)
                if resp and resp.status_code == 200:
                    text = resp.text.strip()
                    if len(text) > 50:
                        return text
            except Exception as e:
                logger.debug(f"Markdown service failed for {url}: {e}")

        return None

    def _extract_title(self, markdown: str) -> str | None:
        """Extract title from markdown (first H1 or first non-empty line)."""
        for line in markdown.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()

        # Fallback: first non-empty line
        for line in markdown.split("\n"):
            line = line.strip()
            if line and len(line) > 10 and not line.startswith("http"):
                return line[:200]

        return None

    def _extract_date(self, markdown: str, url: str) -> datetime | None:
        """Extract publication date from markdown content or URL."""
        # Try URL first (most reliable)
        url_date = self._date_from_url(url)
        if url_date:
            return url_date

        # Try content (first 500 chars — date usually near top)
        header = markdown[:500]
        return self._date_from_text(header)

    def _date_from_url(self, url: str) -> datetime | None:
        """Extract date from URL path (e.g., /2025/03/15/article-title)."""
        m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None

    def _date_from_text(self, text: str) -> datetime | None:
        """Extract date from text using common patterns."""
        for pattern in _DATE_PATTERNS:
            m = pattern.search(text)
            if not m:
                continue
            groups = m.groups()
            try:
                if groups[0].isdigit():
                    # ISO pattern: YYYY-MM-DD
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                else:
                    # US pattern: Month DD, YYYY
                    month = _MONTH_MAP.get(groups[0].lower())
                    if month:
                        return datetime(int(groups[2]), month, int(groups[1]))
            except (ValueError, TypeError):
                continue

        return None

    # ---- HTTP helpers ----

    def _get(self, url: str, timeout: int = 15) -> requests.Response | None:
        """GET with standard headers and proxy."""
        headers = {"User-Agent": FAKE_USER_AGENT}
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
        try:
            resp = requests.get(
                url, headers=headers, timeout=timeout, proxies=proxies,
                allow_redirects=True,
            )
            return resp
        except requests.RequestException as e:
            logger.debug(f"HTTP GET failed for {url}: {e}")
            return None

    # ---- Cache ----

    def _cache_dir(self) -> Path:
        d = CACHE_DIR / "company_news"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _cache_key(self, ticker: str) -> str:
        return hashlib.md5(ticker.upper().encode()).hexdigest()

    def _read_cache(self, ticker: str) -> CompanyProfile | None:
        cache_file = self._cache_dir() / f"{self._cache_key(ticker)}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text())
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at > COMPANY_NEWS_CACHE_TTL_HOURS * 3600:
                return None

            articles = []
            for a in data.get("dated_articles", []):
                pub = None
                if a.get("published_at"):
                    try:
                        pub = datetime.fromisoformat(a["published_at"])
                    except (ValueError, TypeError):
                        pass
                articles.append(DatedArticle(title=a["title"], published_at=pub))

            return CompanyProfile(
                ticker=data["ticker"],
                name=data.get("name", ""),
                news_titles=data.get("news_titles", []),
                dated_articles=articles,
                data_sources=data.get("data_sources", []),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def _write_cache(self, ticker: str, profile: CompanyProfile) -> None:
        cache_file = self._cache_dir() / f"{self._cache_key(ticker)}.json"
        data = {
            "ticker": profile.ticker,
            "name": profile.name,
            "news_titles": profile.news_titles,
            "dated_articles": [
                {
                    "title": a.title,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                }
                for a in profile.dated_articles
            ],
            "data_sources": profile.data_sources,
            "_cached_at": time.time(),
        }
        try:
            cache_file.write_text(json.dumps(data, default=str))
        except OSError:
            pass
