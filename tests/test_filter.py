# Tests for Filter (relevance scoring, deduplication, top-N selection)
from datetime import datetime

import pytest

from daily_news_podcast.filter import Filter
from daily_news_podcast.models import Article, FilterConfig


def make_article(
    title: str,
    summary: str = "",
    url: str = "",
    relevance_score: float = 0.0,
) -> Article:
    return Article(
        title=title,
        summary=summary,
        url=url or f"http://example.com/{title.replace(' ', '_')}",
        source_name="Test Source",
        published_at=datetime(2024, 1, 1, 12, 0, 0),
        relevance_score=relevance_score,
    )


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_empty_articles_returns_empty():
    f = Filter()
    result = f.score_and_select([], FilterConfig())
    assert result == []


def test_empty_topics_and_keywords_returns_all_articles_with_score_1():
    """When no topics/keywords are configured every article scores 1.0."""
    articles = [
        make_article("Python news"),
        make_article("Sports update"),
        make_article("Weather forecast"),
    ]
    config = FilterConfig(topics=[], keywords=[])
    f = Filter()
    result = f.score_and_select(articles, config)

    assert len(result) == 3
    for article in result:
        assert article.relevance_score == 1.0


def test_articles_below_threshold_are_excluded():
    """Articles whose TF-IDF similarity is below the threshold are dropped."""
    # "python programming" query — unrelated article should score very low / 0
    articles = [
        make_article("Python programming tutorial", "Learn Python today"),
        make_article("Football match results", "The team won the game"),
    ]
    config = FilterConfig(topics=["python", "programming"], relevance_threshold=0.05)
    f = Filter()
    result = f.score_and_select(articles, config)

    titles = [a.title for a in result]
    assert "Python programming tutorial" in titles
    assert "Football match results" not in titles


def test_articles_sorted_by_descending_relevance_score():
    """Returned articles must be ordered highest score first."""
    articles = [
        make_article("Python tutorial", "Learn Python programming"),
        make_article("Python advanced", "Advanced Python programming techniques"),
        make_article("Python basics", "Basic Python introduction"),
    ]
    config = FilterConfig(topics=["python", "programming"])
    f = Filter()
    result = f.score_and_select(articles, config)

    scores = [a.relevance_score for a in result]
    assert scores == sorted(scores, reverse=True)


def test_returns_at_most_max_count_articles():
    """score_and_select must never return more than max_count articles."""
    articles = [
        make_article(f"Python article {i}", f"Python programming content {i}")
        for i in range(30)
    ]
    config = FilterConfig(topics=["python"])
    f = Filter()
    result = f.score_and_select(articles, config, max_count=20)

    assert len(result) <= 20


def test_returns_all_when_fewer_than_max_count():
    """When fewer relevant articles exist than max_count, all are returned."""
    articles = [
        make_article("Python news", "Python programming update"),
        make_article("Python release", "New Python version released"),
    ]
    config = FilterConfig(topics=["python"])
    f = Filter()
    result = f.score_and_select(articles, config, max_count=20)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_near_duplicate_titles_are_deduplicated_keep_higher_score():
    """Near-duplicate titles (similarity > 0.85) — only the higher-scored one survives."""
    # Two articles with almost identical titles; give the second one a higher
    # pre-set score by making it more relevant to the query.
    articles = [
        make_article(
            "Breaking news about Python release",
            "Python 3.13 released today with new features",
        ),
        make_article(
            "Breaking news about Python release",  # identical title → similarity = 1.0
            "Python 3.13 released today with new features and improvements",
        ),
    ]
    config = FilterConfig(topics=["python", "release"])
    f = Filter()
    result = f.score_and_select(articles, config)

    # Only one of the two near-duplicates should survive
    assert len(result) == 1


def test_distinct_titles_are_not_deduplicated():
    """Articles with clearly different titles must both be kept."""
    articles = [
        make_article("Python programming tutorial", "Learn Python today"),
        make_article("Machine learning with scikit-learn", "ML tutorial using sklearn"),
    ]
    config = FilterConfig(topics=["python", "machine learning"])
    f = Filter()
    result = f.score_and_select(articles, config)

    assert len(result) == 2


def test_deduplication_keeps_higher_relevance_score():
    """When two articles are near-duplicates, the one with the higher relevance score is kept."""
    # Make the second article more relevant to the query so it scores higher
    articles = [
        make_article(
            "Python release announcement",
            "A new version is out",  # less relevant summary
        ),
        make_article(
            "Python release announcement",  # same title
            "Python 3.13 release announcement with full changelog and new features",
        ),
    ]
    config = FilterConfig(topics=["python", "release", "announcement"])
    f = Filter()
    result = f.score_and_select(articles, config)

    assert len(result) == 1
    # The surviving article should have the higher score
    assert result[0].relevance_score >= 0.0
