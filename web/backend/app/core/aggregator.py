import logging
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source_name: str
    published_at: datetime
    relevance_score: float = 0.0


def _fetch_one(name: str, url: str, since: datetime) -> list[Article]:
    """Fetch one RSS feed with a hard 8-second timeout using httpx."""
    articles = []
    try:
        import httpx
        response = httpx.get(url, timeout=8, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        feed = feedparser.parse(response.text)
        for entry in feed.entries:
            ts = entry.get("published_parsed") or entry.get("updated_parsed")
            if ts is None:
                continue
            published_at = datetime(*ts[:6])
            if published_at < since:
                continue
            link = entry.get("link", "")
            if not link:
                continue
            summary = entry.get("summary", "") or entry.get("description", "")
            articles.append(Article(
                title=entry.get("title", ""),
                summary=summary,
                url=link,
                source_name=name,
                published_at=published_at,
            ))
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
    return articles


def fetch_articles(
    sources: list[tuple[str, str]],
    since: datetime,
) -> list[Article]:
    """Fetch all RSS sources in parallel with per-feed timeouts."""
    all_articles: list[Article] = []
    seen_urls: set[str] = set()

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_one, name, url, since): (name, url)
                   for name, url in sources}
        for future in as_completed(futures, timeout=30):
            try:
                for article in future.result():
                    if article.url not in seen_urls:
                        seen_urls.add(article.url)
                        all_articles.append(article)
            except Exception as e:
                logger.warning("Feed fetch error: %s", e)

    return all_articles
