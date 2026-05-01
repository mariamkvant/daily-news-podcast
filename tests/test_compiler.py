# Tests for Compiler (duration limit, segment ordering, intro prepending)
import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from daily_news_podcast.compiler import Compiler
from daily_news_podcast.models import Article, Episode, Segment


def make_segment(url: str, duration_ms: int) -> Segment:
    return Segment(article_url=url, audio_path=f"/fake/{url}.mp3", duration_ms=duration_ms)


def make_tts_engine(intro_duration_ms: int = 3000) -> MagicMock:
    """Return a mock TTSEngine whose generate_segment returns a fake intro Segment."""
    engine = MagicMock()
    intro_seg = Segment(
        article_url="intro",
        audio_path="/fake/intro.mp3",
        duration_ms=intro_duration_ms,
    )
    engine.generate_segment.return_value = intro_seg
    return engine


def run_compile(segments, tts_engine=None, max_duration_seconds=600, intro_duration_ms=3000):
    """Helper: run Compiler.compile() with pydub fully mocked."""
    if tts_engine is None:
        tts_engine = make_tts_engine(intro_duration_ms)

    compiler = Compiler()

    with patch("daily_news_podcast.compiler.Path.mkdir"), \
         patch("daily_news_podcast.compiler.datetime") as mock_dt, \
         patch("daily_news_podcast.compiler.PydubSegment" if False else "pydub.AudioSegment") as _pydub:
        mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 0)

        # Patch pydub inside the compiler module
        with patch("daily_news_podcast.compiler.__builtins__", wraps=__builtins__):
            pass

        # Use importlib-level patch for pydub
        with patch.dict("sys.modules", {"pydub": MagicMock()}):
            import sys
            pydub_mock = sys.modules["pydub"]
            pydub_segment_cls = MagicMock()
            pydub_segment_cls.empty.return_value = MagicMock()
            pydub_segment_cls.from_mp3.return_value = MagicMock()
            pydub_mock.AudioSegment = pydub_segment_cls

            episode = compiler.compile(
                segments=segments,
                date=date(2024, 1, 15),
                tts_engine=tts_engine,
                audio_dir=Path("/fake/audio"),
                max_duration_seconds=max_duration_seconds,
            )
    return episode


class TestCompilerDurationLimit:
    """Episode total_duration_ms must never exceed max_duration_seconds * 1000."""

    def test_total_duration_within_10_minutes(self):
        # 20 segments of 60 seconds each = 1200 seconds total, well over 10 min
        segments = [make_segment(f"url{i}", 60_000) for i in range(20)]
        episode = run_compile(segments)
        assert episode.total_duration_ms <= 600_000

    def test_total_duration_exactly_at_boundary(self):
        # intro = 3000 ms; fill up to exactly 600_000 ms
        # 597_000 ms remaining after intro; 3 segments of 199_000 ms = 597_000 ms
        segments = [make_segment(f"url{i}", 199_000) for i in range(3)]
        episode = run_compile(segments, intro_duration_ms=3_000)
        assert episode.total_duration_ms <= 600_000

    def test_stops_at_boundary(self):
        # intro = 3000 ms; one segment of 597_000 ms fits exactly; second should be excluded
        seg1 = make_segment("url1", 597_000)
        seg2 = make_segment("url2", 1_000)
        episode = run_compile([seg1, seg2], intro_duration_ms=3_000)
        # seg1 fits (3000 + 597000 = 600000), seg2 would push over
        assert len(episode.segments) == 1
        assert episode.segments[0].article_url == "url1"
        assert episode.total_duration_ms == 600_000

    def test_segment_that_would_exceed_limit_is_excluded(self):
        # intro = 10_000 ms; one big segment that alone exceeds the limit
        big_seg = make_segment("big", 595_000)
        episode = run_compile([big_seg], intro_duration_ms=10_000)
        # 10_000 + 595_000 = 605_000 > 600_000 → big_seg should be excluded
        assert len(episode.segments) == 0
        assert episode.total_duration_ms == 10_000


class TestCompilerSegmentOrdering:
    """Segments must be included in the order provided."""

    def test_segments_in_provided_order(self):
        segments = [make_segment(f"url{i}", 10_000) for i in range(5)]
        episode = run_compile(segments)
        for i, seg in enumerate(episode.segments):
            assert seg.article_url == f"url{i}"

    def test_partial_selection_preserves_order(self):
        # intro = 3000 ms; each segment = 200_000 ms; only 2 fit (3000 + 200000 + 200000 = 403000)
        segments = [make_segment(f"url{i}", 200_000) for i in range(5)]
        episode = run_compile(segments, intro_duration_ms=3_000)
        # 3000 + 200000 = 203000; + 200000 = 403000; + 200000 = 603000 > 600000 → 2 segments
        assert len(episode.segments) == 2
        assert episode.segments[0].article_url == "url0"
        assert episode.segments[1].article_url == "url1"


class TestCompilerIntroNotInSegments:
    """The intro segment must NOT appear in episode.segments."""

    def test_intro_not_in_episode_segments(self):
        segments = [make_segment("url1", 10_000)]
        episode = run_compile(segments)
        for seg in episode.segments:
            assert seg.article_url != "intro"

    def test_intro_duration_counted_in_total(self):
        # intro = 5000 ms; one segment = 10_000 ms
        segments = [make_segment("url1", 10_000)]
        episode = run_compile(segments, intro_duration_ms=5_000)
        assert episode.total_duration_ms == 15_000


class TestCompilerEmptySegments:
    """Compilation with empty segments list should produce an episode with only the intro."""

    def test_empty_segments_returns_episode(self):
        episode = run_compile([])
        assert isinstance(episode, Episode)
        assert episode.segments == []

    def test_empty_segments_total_duration_is_intro_only(self):
        episode = run_compile([], intro_duration_ms=4_000)
        assert episode.total_duration_ms == 4_000

    def test_empty_segments_audio_path_set(self):
        episode = run_compile([])
        assert "episode_2024-01-15.mp3" in episode.audio_path


class TestCompilerIntroFailure:
    """If intro generation fails, compilation should continue without raising."""

    def test_intro_failure_does_not_raise(self):
        engine = MagicMock()
        engine.generate_segment.side_effect = Exception("TTS unavailable")
        segments = [make_segment("url1", 10_000)]

        compiler = Compiler()
        with patch.dict("sys.modules", {"pydub": MagicMock()}):
            import sys
            pydub_mock = sys.modules["pydub"]
            pydub_segment_cls = MagicMock()
            pydub_segment_cls.empty.return_value = MagicMock()
            pydub_segment_cls.from_mp3.return_value = MagicMock()
            pydub_mock.AudioSegment = pydub_segment_cls

            episode = compiler.compile(
                segments=segments,
                date=date(2024, 1, 15),
                tts_engine=engine,
                audio_dir=Path("/fake/audio"),
            )

        assert isinstance(episode, Episode)
        # With no intro, only the segment duration counts
        assert episode.total_duration_ms == 10_000

    def test_intro_failure_segments_still_included(self):
        engine = MagicMock()
        engine.generate_segment.return_value = None  # None means intro failed silently
        segments = [make_segment("url1", 10_000), make_segment("url2", 20_000)]

        compiler = Compiler()
        with patch.dict("sys.modules", {"pydub": MagicMock()}):
            import sys
            pydub_mock = sys.modules["pydub"]
            pydub_segment_cls = MagicMock()
            pydub_segment_cls.empty.return_value = MagicMock()
            pydub_segment_cls.from_mp3.return_value = MagicMock()
            pydub_mock.AudioSegment = pydub_segment_cls

            episode = compiler.compile(
                segments=segments,
                date=date(2024, 1, 15),
                tts_engine=engine,
                audio_dir=Path("/fake/audio"),
            )

        assert len(episode.segments) == 2


class TestCompilerEpisodeMetadata:
    """Episode metadata fields are set correctly."""

    def test_episode_date_matches_input(self):
        episode = run_compile([])
        assert episode.date == date(2024, 1, 15)

    def test_episode_audio_path_contains_date(self):
        episode = run_compile([])
        assert "2024-01-15" in episode.audio_path

    def test_episode_created_at_is_datetime(self):
        episode = run_compile([])
        assert isinstance(episode.created_at, datetime)
