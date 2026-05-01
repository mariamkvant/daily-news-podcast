"""ConfigStore: persists and loads user configuration (AppConfig) to/from JSON."""

import json
import logging
import os
from pathlib import Path

from .models import AppConfig, FilterConfig, SchedulerConfig, Source

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".daily-news-podcast"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _source_to_dict(source: Source) -> dict:
    return {"url": source.url, "name": source.name}


def _source_from_dict(d: dict) -> Source:
    return Source(url=d["url"], name=d["name"])


def _filter_config_to_dict(fc: FilterConfig) -> dict:
    return {
        "topics": fc.topics,
        "keywords": fc.keywords,
        "relevance_threshold": fc.relevance_threshold,
    }


def _filter_config_from_dict(d: dict) -> FilterConfig:
    return FilterConfig(
        topics=d.get("topics", []),
        keywords=d.get("keywords", []),
        relevance_threshold=d.get("relevance_threshold", 0.05),
    )


def _scheduler_config_to_dict(sc: SchedulerConfig) -> dict:
    return {
        "generation_hour": sc.generation_hour,
        "generation_minute": sc.generation_minute,
    }


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
    }


def _app_config_from_dict(d: dict) -> AppConfig:
    return AppConfig(
        sources=[_source_from_dict(s) for s in d.get("sources", [])],
        filter=_filter_config_from_dict(d.get("filter", {})),
        scheduler=_scheduler_config_from_dict(d.get("scheduler", {})),
    )


class ConfigStore:
    """Persists and loads AppConfig to/from ~/.daily-news-podcast/config.json."""

    def __init__(self, config_file: Path = _CONFIG_FILE) -> None:
        self._config_file = config_file

    def load(self) -> AppConfig:
        """Read config.json and deserialize to AppConfig.

        Returns a default AppConfig() on missing file or JSON parse error.
        """
        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _app_config_from_dict(data)
        except FileNotFoundError:
            logger.debug("Config file not found at %s; using defaults.", self._config_file)
            return AppConfig()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse config file %s: %s; using defaults.", self._config_file, exc)
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        """Serialize AppConfig to JSON and write to config.json.

        Creates the directory if it does not exist.
        """
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        data = _app_config_to_dict(config)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Config saved to %s.", self._config_file)
