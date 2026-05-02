"""ConfigStore: persists and loads user configuration (AppConfig) to/from JSON."""

import json
import logging
from pathlib import Path

from .models import AppConfig, FilterConfig, SchedulerConfig, Source

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic catalog — predefined topics users can toggle on/off
# ---------------------------------------------------------------------------

AVAILABLE_TOPICS: list[str] = [
    "world",
    "politics",
    "technology",
    "business",
    "science",
    "health",
    "environment",
    "sports",
    "entertainment",
    "finance",
    "ai",
    "cybersecurity",
    "space",
    "climate",
    "education",
]

DEFAULT_TOPICS: list[str] = ["world", "technology", "business", "science"]

# ---------------------------------------------------------------------------
# Keyword catalog — predefined keywords users can toggle on/off
# ---------------------------------------------------------------------------

AVAILABLE_KEYWORDS: list[str] = [
    "breaking",
    "election",
    "war",
    "economy",
    "inflation",
    "recession",
    "stock market",
    "artificial intelligence",
    "machine learning",
    "cryptocurrency",
    "bitcoin",
    "climate change",
    "renewable energy",
    "covid",
    "pandemic",
    "ukraine",
    "china",
    "united states",
    "europe",
    "middle east",
    "nuclear",
    "trade",
    "sanctions",
    "merger",
    "startup",
    "ipo",
    "layoffs",
    "nasa",
    "spacex",
    "cancer",
    "vaccine",
]

DEFAULT_KEYWORDS: list[str] = []

# ---------------------------------------------------------------------------
# Full source library — grouped by primary topic
# ---------------------------------------------------------------------------

# Each entry: (name, url, topics)
# topics is used to suggest sources when the user picks topics (future use),
# and to label sources in the UI.
_ALL_SOURCES: list[tuple[str, str, list[str]]] = [
    # --- World / General ---
    ("BBC News",            "http://feeds.bbci.co.uk/news/rss.xml",                          ["world"]),
    ("Reuters Top News",    "https://feeds.reuters.com/reuters/topNews",                     ["world"]),
    ("AP News",             "https://feeds.apnews.com/rss/apf-topnews",                      ["world"]),
    ("Al Jazeera",          "https://www.aljazeera.com/xml/rss/all.xml",                     ["world"]),
    ("The Guardian World",  "https://www.theguardian.com/world/rss",                         ["world"]),
    ("NY Times",            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",     ["world"]),
    ("Sky News World",      "https://feeds.skynews.com/feeds/rss/world.xml",                 ["world"]),
    ("Deutsche Welle",      "https://rss.dw.com/rdf/rss-en-all",                             ["world"]),
    ("France 24",           "https://www.france24.com/en/rss",                               ["world"]),
    ("NPR News",            "https://feeds.npr.org/1001/rss.xml",                            ["world"]),
    ("CBC News",            "https://www.cbc.ca/cmlink/rss-topstories",                      ["world"]),
    ("ABC News",            "https://feeds.abcnews.com/abcnews/topstories",                  ["world"]),

    # --- Politics ---
    ("Politico",            "https://www.politico.com/rss/politicopicks.xml",                ["politics"]),
    ("The Hill",            "https://thehill.com/feed/",                                     ["politics"]),
    ("BBC Politics",        "http://feeds.bbci.co.uk/news/politics/rss.xml",                 ["politics"]),
    ("Guardian Politics",   "https://www.theguardian.com/politics/rss",                      ["politics"]),

    # --- Technology ---
    ("TechCrunch",          "https://techcrunch.com/feed/",                                  ["technology"]),
    ("The Verge",           "https://www.theverge.com/rss/index.xml",                        ["technology"]),
    ("Wired",               "https://www.wired.com/feed/rss",                                ["technology"]),
    ("Ars Technica",        "https://feeds.arstechnica.com/arstechnica/index",               ["technology"]),
    ("MIT Tech Review",     "https://www.technologyreview.com/feed/",                        ["technology", "ai", "science"]),
    ("The Hacker News",     "https://feeds.feedburner.com/TheHackersNews",                   ["technology", "cybersecurity"]),
    ("ZDNet",               "https://www.zdnet.com/news/rss.xml",                            ["technology"]),

    # --- AI ---
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/",                     ["ai", "technology"]),
    ("DeepMind Blog",       "https://deepmind.google/blog/rss.xml",                          ["ai"]),

    # --- Business / Finance ---
    ("Financial Times",     "https://www.ft.com/rss/home",                                   ["business", "finance"]),
    ("Bloomberg Markets",   "https://feeds.bloomberg.com/markets/news.rss",                  ["business", "finance"]),
    ("WSJ World News",      "https://feeds.a.dj.com/rss/RSSWorldNews.xml",                   ["business", "world"]),
    ("Forbes",              "https://www.forbes.com/real-time/feed2/",                       ["business", "finance"]),
    ("The Economist",       "https://www.economist.com/finance-and-economics/rss.xml",       ["finance", "business"]),
    ("CNBC Top News",       "https://www.cnbc.com/id/100003114/device/rss/rss.html",         ["business", "finance"]),

    # --- Science ---
    ("Nature News",         "https://www.nature.com/nature.rss",                             ["science"]),
    ("Science Daily",       "https://www.sciencedaily.com/rss/all.xml",                      ["science"]),
    ("New Scientist",       "https://www.newscientist.com/feed/home/",                       ["science"]),
    ("NASA News",           "https://www.nasa.gov/rss/dyn/breaking_news.rss",                ["science", "space"]),

    # --- Health ---
    ("WHO News",            "https://www.who.int/rss-feeds/news-english.xml",                ["health"]),
    ("Medical News Today",  "https://www.medicalnewstoday.com/rss/news.xml",                 ["health"]),
    ("NHS News",            "https://www.nhs.uk/news/rss.aspx",                              ["health"]),

    # --- Environment / Climate ---
    ("Guardian Environment","https://www.theguardian.com/environment/rss",                   ["environment", "climate"]),
    ("Carbon Brief",        "https://www.carbonbrief.org/feed",                              ["environment", "climate"]),
    ("Inside Climate News", "https://insideclimatenews.org/feed/",                           ["environment", "climate"]),

    # --- Sports ---
    ("BBC Sport",           "http://feeds.bbci.co.uk/sport/rss.xml",                         ["sports"]),
    ("ESPN",                "https://www.espn.com/espn/rss/news",                            ["sports"]),
    ("Sky Sports",          "https://www.skysports.com/rss/12040",                           ["sports"]),

    # --- Entertainment ---
    ("Variety",             "https://variety.com/feed/",                                     ["entertainment"]),
    ("Hollywood Reporter",  "https://www.hollywoodreporter.com/feed/",                       ["entertainment"]),
    ("Rolling Stone",       "https://www.rollingstone.com/feed/",                            ["entertainment"]),

    # --- Cybersecurity ---
    ("Krebs on Security",   "https://krebsonsecurity.com/feed/",                             ["cybersecurity"]),
    ("Dark Reading",        "https://www.darkreading.com/rss.xml",                           ["cybersecurity"]),

    # --- Space ---
    ("Space.com",           "https://www.space.com/feeds/all",                               ["space", "science"]),
    ("SpaceNews",           "https://spacenews.com/feed/",                                   ["space"]),
]

# Build the default active sources (the original 6 that were always on)
_DEFAULT_ENABLED_NAMES = {
    "BBC News", "Reuters Top News", "NY Times", "Sky News World",
    "TechCrunch", "The Hacker News",
}


def _all_sources_as_models() -> list[Source]:
    return [
        Source(url=url, name=name, enabled=(name in _DEFAULT_ENABLED_NAMES))
        for name, url, _ in _ALL_SOURCES
    ]


def _default_config() -> AppConfig:
    return AppConfig(
        sources=_all_sources_as_models(),
        filter=FilterConfig(
            topics=list(DEFAULT_TOPICS),
            keywords=list(DEFAULT_KEYWORDS),
            relevance_threshold=0.05,
        ),
        scheduler=SchedulerConfig(generation_hour=7, generation_minute=0),
        max_duration_seconds=600,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path.home() / ".daily-news-podcast"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _source_to_dict(s: Source) -> dict:
    return {"url": s.url, "name": s.name, "enabled": s.enabled}


def _source_from_dict(d: dict) -> Source:
    return Source(url=d["url"], name=d["name"], enabled=d.get("enabled", True))


def _filter_config_to_dict(fc: FilterConfig) -> dict:
    return {
        "topics": fc.topics,
        "keywords": fc.keywords,
        "relevance_threshold": fc.relevance_threshold,
    }


def _filter_config_from_dict(d: dict) -> FilterConfig:
    return FilterConfig(
        topics=d.get("topics", list(DEFAULT_TOPICS)),
        keywords=d.get("keywords", []),
        relevance_threshold=d.get("relevance_threshold", 0.05),
    )


def _scheduler_config_to_dict(sc: SchedulerConfig) -> dict:
    return {"generation_hour": sc.generation_hour, "generation_minute": sc.generation_minute}


def _scheduler_config_from_dict(d: dict) -> SchedulerConfig:
    return SchedulerConfig(
        generation_hour=d.get("generation_hour", 7),
        generation_minute=d.get("generation_minute", 0),
    )


def _app_config_to_dict(config: AppConfig) -> dict:
    return {
        "sources": [_source_to_dict(s) for s in config.sources],
        "filter": _filter_config_to_dict(config.filter),
        "scheduler": _scheduler_config_to_dict(config.scheduler),
        "max_duration_seconds": config.max_duration_seconds,
    }


def _app_config_from_dict(d: dict) -> AppConfig:
    saved_sources = {s["name"]: s for s in d.get("sources", [])}

    sources = []
    for name, url, _ in _ALL_SOURCES:
        if name in saved_sources:
            sources.append(_source_from_dict(saved_sources[name]))
        else:
            sources.append(Source(url=url, name=name, enabled=False))

    return AppConfig(
        sources=sources,
        filter=_filter_config_from_dict(d.get("filter", {})),
        scheduler=_scheduler_config_from_dict(d.get("scheduler", {})),
        max_duration_seconds=d.get("max_duration_seconds", 600),
    )


# ---------------------------------------------------------------------------
# ConfigStore
# ---------------------------------------------------------------------------

class ConfigStore:
    def __init__(self, config_file: Path = _CONFIG_FILE) -> None:
        self._config_file = config_file

    def load(self) -> AppConfig:
        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _app_config_from_dict(data)
        except FileNotFoundError:
            logger.debug("Config file not found; using defaults.")
            return _default_config()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse config: %s; using defaults.", exc)
            return _default_config()

    def save(self, config: AppConfig) -> None:
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(_app_config_to_dict(config), f, indent=2)
        logger.debug("Config saved to %s.", self._config_file)
