import logging
from dataclasses import dataclass
from datetime import datetime

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


def fetch_articles(
    sources: list[tuple[str, str]],  # [(name, url), ...]
    since: datetime,
) -> list[Article]:
    articles: list[Article] = []
    seen_urls: set[str] = set()

    for name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                ts = entry.get("published_parsed") or entry.get("updated_parsed")
                if ts is None:
                    continue
                published_at = datetime(*ts[:6])
                if published_at < since:
                    continue
                link = entry.get("link", "")
                if link in seen_urls:
                    continue
                seen_urls.add(link)
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
