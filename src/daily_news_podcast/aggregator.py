# Aggregator: fetches articles from RSS sources filtered to the last 24 hours.
import logging
from datetime import datetime

import feedparser

from .models import Article, Source

logger = logging.getLogger(__name__)


class Aggregator:
    def fetch(self, sources: list[Source], since: datetime) -> list[Article]:
        """
        Fetch articles from all sources published after `since`.
        Skips unreachable sources, logs failures, and continues.
        Returns a flat list of Article objects.
        """
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for source in sources:
            if not source.enabled:
                continue
            try:
                feed = feedparser.parse(source.url)

                for entry in feed.entries:
                    # Determine the publication time
                    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
                    if time_struct is None:
                        continue

                    published_at = datetime(*time_struct[:6])

                    if published_at < since:
                        continue

                    url = entry.get("link", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    summary = entry.get("summary", "") or entry.get("description", "")

                    articles.append(
                        Article(
                            title=entry.get("title", ""),
                            summary=summary,
                            url=url,
                            source_name=source.name,
                            published_at=published_at,
                        )
                    )

            except Exception as exc:
                logger.warning("Failed to fetch feed from %s: %s", source.url, exc)
                continue

        return articles
