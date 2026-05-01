"""Tests for EpisodeStore (save/load round-trip, empty DB, audio cleanup)."""

import os
from datetime import date, datetime
from pathlib import Path

import pytest

from daily_news_podcast.episode_store import EpisodeStore
from daily_news_podcast.models import Episode, Segment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(article_url: str, audio_path: str, duration_ms: int = 5000) -> Segment:
    return Segment(article_url=article_url, audio_path=audio_path, duration_ms=duration_ms)


def _make_episode(
    tmp_path: Path,
    ep_date: date | None = None,
    num_segments: int = 2,
) -> tuple[Episode, list[Path]]:
    """Create a sample Episode with real (empty) audio files in tmp_path."""
    ep_date = ep_date or date(2024, 1, 15)
    audio_files: list[Path] = []

    segments = []
    for i in range(num_segments):
        seg_file = tmp_path / f"seg_{ep_date.isoformat()}_{i}.mp3"
        seg_file.write_bytes(b"")  # placeholder
        audio_files.append(seg_file)
        segments.append(_make_segment(
            article_url=f"https://example.com/article/{i}",
            audio_path=str(seg_file),
        ))

    ep_file = tmp_path / f"episode_{ep_date.isoformat()}.mp3"
    ep_file.write_bytes(b"")
    audio_files.append(ep_file)

    episode = Episode(
        date=ep_date,
        segments=segments,
        total_duration_ms=10000,
        audio_path=str(ep_file),
        created_at=datetime(2024, 1, 15, 7, 0, 0),
    )
    return episode, audio_files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEpisodeStoreLoadLatest:
    def test_returns_none_when_empty(self, tmp_path):
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        assert store.load_latest() is None

    def test_returns_saved_episode(self, tmp_path):
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        episode, _ = _make_episode(tmp_path)
        store.save(episode)
        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.date == episode.date
        assert loaded.total_duration_ms == episode.total_duration_ms
        assert loaded.audio_path == episode.audio_path
        assert loaded.created_at == episode.created_at

    def test_segments_round_trip(self, tmp_path):
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        episode, _ = _make_episode(tmp_path, num_segments=3)
        store.save(episode)
        loaded = store.load_latest()
        assert loaded is not None
        assert len(loaded.segments) == 3
        for orig, loaded_seg in zip(episode.segments, loaded.segments):
            assert loaded_seg.article_url == orig.article_url
            assert loaded_seg.audio_path == orig.audio_path
            assert loaded_seg.duration_ms == orig.duration_ms

    def test_returns_most_recent_episode(self, tmp_path):
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        ep1, _ = _make_episode(tmp_path, ep_date=date(2024, 1, 14))
        ep2, _ = _make_episode(tmp_path, ep_date=date(2024, 1, 15))
        store.save(ep1)
        store.save(ep2)
        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.date == date(2024, 1, 15)


class TestEpisodeStoreSave:
    def test_save_creates_db_file(self, tmp_path):
        db_file = tmp_path / "sub" / "episodes.db"
        store = EpisodeStore(db_file=db_file)
        episode, _ = _make_episode(tmp_path)
        store.save(episode)
        assert db_file.exists()

    def test_save_deletes_previous_episode_audio_files(self, tmp_path):
        store = EpisodeStore(db_file=tmp_path / "episodes.db")

        # Save first episode with real files
        ep1, ep1_files = _make_episode(tmp_path, ep_date=date(2024, 1, 14))
        store.save(ep1)

        # Verify files exist before saving second episode
        for f in ep1_files:
            assert f.exists(), f"Expected {f} to exist before second save"

        # Save second episode — should delete first episode's files
        ep2, ep2_files = _make_episode(tmp_path, ep_date=date(2024, 1, 15))
        store.save(ep2)

        for f in ep1_files:
            assert not f.exists(), f"Expected {f} to be deleted after second save"

        # Second episode's files should still exist
        for f in ep2_files:
            assert f.exists(), f"Expected {f} to still exist"

    def test_save_tolerates_missing_audio_files(self, tmp_path):
        """save() should not raise if previous audio files are already gone."""
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        ep1, ep1_files = _make_episode(tmp_path, ep_date=date(2024, 1, 14))
        store.save(ep1)

        # Delete files manually before saving second episode
        for f in ep1_files:
            f.unlink(missing_ok=True)

        ep2, _ = _make_episode(tmp_path, ep_date=date(2024, 1, 15))
        store.save(ep2)  # Should not raise

    def test_replace_episode_same_date(self, tmp_path):
        """Saving a second episode for the same date replaces the first."""
        store = EpisodeStore(db_file=tmp_path / "episodes.db")
        ep1, _ = _make_episode(tmp_path, ep_date=date(2024, 1, 15), num_segments=1)
        ep2, _ = _make_episode(tmp_path, ep_date=date(2024, 1, 15), num_segments=2)
        store.save(ep1)
        store.save(ep2)
        loaded = store.load_latest()
        assert loaded is not None
        assert len(loaded.segments) == 2
