# Tests for Aggregator (RSS fetching, 24-hour filter, fault tolerance)
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from daily_news_podcast.aggregator import Aggregator
from daily_news_podcast.models import Source


def _make_time_struct(dt: datetime) -> time.struct_time:
    """Convert a datetime to a time.struct_time as feedparser would return."""
    return time.struct_time((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, -1))


def _make_entry(title: str, url: str, published_at: datetime, summary: str = "") -> dict:
    """Build a minimal feedparser entry dict."""
    return {
        "title": title,
        "link": url,
        "published_parsed": _make_time_struct(published_at),
        "summary": summary,
    }


def _make_feed(entries: list) -> MagicMock:
    """Build a minimal feedparser feed mock."""
    feed = MagicMock()
    feed.entries = entries
    return feed


class TestAggregatorFetch:
    def setup_method(self):
        self.aggregator = Aggregator()
        self.since = datetime(2024, 1, 15, 12, 0, 0)
        self.source = Source(url="http://example.com/feed.rss", name="Example")

    # ------------------------------------------------------------------
    # Articles within 24 hours are included
    # ------------------------------------------------------------------
    def test_articles_within_24h_are_included(self):
        recent_time = self.since + timedelta(hours=1)
        entry = _make_entry("Recent Article", "http://example.com/1", recent_time, "Summary text")

        with patch("feedparser.parse", return_value=_make_feed([entry])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 1
        assert articles[0].title == "Recent Article"
        assert articles[0].url == "http://example.com/1"
        assert articles[0].summary == "Summary text"
        assert articles[0].source_name == "Example"
        assert articles[0].published_at == recent_time

    def test_article_exactly_at_since_is_included(self):
        entry = _make_entry("Exact Time Article", "http://example.com/exact", self.since)

        with patch("feedparser.parse", return_value=_make_feed([entry])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 1

    # ------------------------------------------------------------------
    # Articles older than 24 hours are excluded
    # ------------------------------------------------------------------
    def test_articles_older_than_since_are_excluded(self):
        old_time = self.since - timedelta(hours=1)
        entry = _make_entry("Old Article", "http://example.com/old", old_time)

        with patch("feedparser.parse", return_value=_make_feed([entry])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 0

    def test_mix_of_old_and_recent_articles(self):
        recent_time = self.since + timedelta(hours=2)
        old_time = self.since - timedelta(hours=2)

        entries = [
            _make_entry("Recent", "http://example.com/recent", recent_time),
            _make_entry("Old", "http://example.com/old", old_time),
        ]

        with patch("feedparser.parse", return_value=_make_feed(entries)):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 1
        assert articles[0].title == "Recent"

    # ------------------------------------------------------------------
    # Network error / parse failure is skipped without raising
    # ------------------------------------------------------------------
    def test_source_with_network_error_is_skipped(self):
        with patch("feedparser.parse", side_effect=Exception("Connection refused")):
            # Should not raise
            articles = self.aggregator.fetch([self.source], self.since)

        assert articles == []

    def test_failing_source_does_not_prevent_other_sources(self):
        good_source = Source(url="http://good.com/feed.rss", name="Good")
        bad_source = Source(url="http://bad.com/feed.rss", name="Bad")

        recent_time = self.since + timedelta(hours=1)
        good_entry = _make_entry("Good Article", "http://good.com/1", recent_time)
        good_feed = _make_feed([good_entry])

        def parse_side_effect(url):
            if url == bad_source.url:
                raise Exception("Network error")
            return good_feed

        with patch("feedparser.parse", side_effect=parse_side_effect):
            articles = self.aggregator.fetch([bad_source, good_source], self.since)

        assert len(articles) == 1
        assert articles[0].title == "Good Article"

    # ------------------------------------------------------------------
    # Duplicate URLs are deduplicated (keep first occurrence)
    # ------------------------------------------------------------------
    def test_duplicate_urls_are_deduplicated(self):
        recent_time = self.since + timedelta(hours=1)
        entry1 = _make_entry("Article A", "http://example.com/same-url", recent_time, "First")
        entry2 = _make_entry("Article B", "http://example.com/same-url", recent_time, "Second")

        with patch("feedparser.parse", return_value=_make_feed([entry1, entry2])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 1
        assert articles[0].title == "Article A"  # first occurrence kept

    def test_duplicate_urls_across_sources_are_deduplicated(self):
        source2 = Source(url="http://other.com/feed.rss", name="Other")
        recent_time = self.since + timedelta(hours=1)

        entry = _make_entry("Shared Article", "http://shared.com/article", recent_time)
        feed = _make_feed([entry])

        with patch("feedparser.parse", return_value=feed):
            articles = self.aggregator.fetch([self.source, source2], self.since)

        assert len(articles) == 1

    def test_unique_urls_are_all_returned(self):
        recent_time = self.since + timedelta(hours=1)
        entries = [
            _make_entry("Article 1", "http://example.com/1", recent_time),
            _make_entry("Article 2", "http://example.com/2", recent_time),
            _make_entry("Article 3", "http://example.com/3", recent_time),
        ]

        with patch("feedparser.parse", return_value=_make_feed(entries)):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 3

    # ------------------------------------------------------------------
    # Entries without published_parsed fall back to updated_parsed
    # ------------------------------------------------------------------
    def test_entry_with_updated_parsed_is_used_when_no_published_parsed(self):
        recent_time = self.since + timedelta(hours=1)
        entry = {
            "title": "Updated Article",
            "link": "http://example.com/updated",
            "updated_parsed": _make_time_struct(recent_time),
            "summary": "Some summary",
        }

        with patch("feedparser.parse", return_value=_make_feed([entry])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 1
        assert articles[0].title == "Updated Article"

    def test_entry_with_no_time_fields_is_skipped(self):
        entry = {
            "title": "No Time Article",
            "link": "http://example.com/notime",
            "summary": "Some summary",
        }

        with patch("feedparser.parse", return_value=_make_feed([entry])):
            articles = self.aggregator.fetch([self.source], self.since)

        assert len(articles) == 0

    # ------------------------------------------------------------------
    # Empty sources list returns empty list
    # ------------------------------------------------------------------
    def test_empty_sources_returns_empty_list(self):
        articles = self.aggregator.fetch([], self.since)
        assert articles == []
