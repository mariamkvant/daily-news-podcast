"""Tests for ConfigStore (load/save round-trip, defaults, error handling)."""

import json
import os
from pathlib import Path

import pytest

from daily_news_podcast.config_store import ConfigStore, _default_config
from daily_news_podcast.models import AppConfig, FilterConfig, SchedulerConfig, Source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> AppConfig:
    return AppConfig(
        sources=[Source(url="https://example.com/rss", name="Example")],
        filter=FilterConfig(topics=["tech"], keywords=["AI"], relevance_threshold=0.1),
        scheduler=SchedulerConfig(generation_hour=8, generation_minute=30),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfigStoreLoad:
    def test_returns_default_when_file_absent(self, tmp_path):
        store = ConfigStore(config_file=tmp_path / "config.json")
        config = store.load()
        # Should return the built-in default config with pre-loaded sources
        assert config == _default_config()
        assert len(config.sources) > 0

    def test_returns_default_on_invalid_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("not valid json", encoding="utf-8")
        store = ConfigStore(config_file=cfg_file)
        config = store.load()
        # Should return the built-in default config with pre-loaded sources
        assert config == _default_config()
        assert len(config.sources) > 0

    def test_returns_default_on_empty_json_object(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("{}", encoding="utf-8")
        store = ConfigStore(config_file=cfg_file)
        config = store.load()
        # Empty dict should deserialize to defaults
        assert config == AppConfig()

    def test_loads_saved_config(self, tmp_path):
        store = ConfigStore(config_file=tmp_path / "config.json")
        original = _make_config()
        store.save(original)
        loaded = store.load()
        assert loaded == original


class TestConfigStoreSave:
    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "config.json"
        store = ConfigStore(config_file=nested)
        store.save(AppConfig())
        assert nested.exists()

    def test_file_is_valid_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = ConfigStore(config_file=cfg_file)
        store.save(_make_config())
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert "sources" in data
        assert "filter" in data
        assert "scheduler" in data

    def test_round_trip_preserves_all_fields(self, tmp_path):
        store = ConfigStore(config_file=tmp_path / "config.json")
        original = _make_config()
        store.save(original)
        loaded = store.load()
        assert loaded.sources == original.sources
        assert loaded.filter == original.filter
        assert loaded.scheduler == original.scheduler

    def test_overwrite_existing_config(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = ConfigStore(config_file=cfg_file)
        store.save(_make_config())
        new_config = AppConfig(
            sources=[Source(url="https://other.com/rss", name="Other")],
        )
        store.save(new_config)
        loaded = store.load()
        assert len(loaded.sources) == 1
        assert loaded.sources[0].url == "https://other.com/rss"

    def test_empty_sources_list(self, tmp_path):
        store = ConfigStore(config_file=tmp_path / "config.json")
        config = AppConfig(sources=[])
        store.save(config)
        loaded = store.load()
        assert loaded.sources == []

    def test_multiple_sources(self, tmp_path):
        store = ConfigStore(config_file=tmp_path / "config.json")
        config = AppConfig(
            sources=[
                Source(url="https://a.com/rss", name="A"),
                Source(url="https://b.com/rss", name="B"),
            ]
        )
        store.save(config)
        loaded = store.load()
        assert len(loaded.sources) == 2
        assert loaded.sources[0].url == "https://a.com/rss"
        assert loaded.sources[1].url == "https://b.com/rss"
