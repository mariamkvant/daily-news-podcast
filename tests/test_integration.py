"""Integration tests for the daily-news-podcast pipeline and scheduler.

Task 13.1 — Full pipeline integration test with mocked TTS
Task 13.2 — Scheduler trigger integration test
"""
import email.utils
import http.server
import io
import tempfile
import threading
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from daily_news_podcast.aggregator import Aggregator
from daily_news_podcast.compiler import Compiler
from daily_news_podcast.config_store import ConfigStore
from daily_news_podcast.episode_store import EpisodeStore
from daily_news_podcast.filter import Filter
from daily_news_podcast.models import (
    AppConfig,
    Episode,
    FilterConfig,
    SchedulerConfig,
    Segment,
    Source,
)
from daily_news_podcast.pipeline import Pipeline
from daily_news_podcast.scheduler import Scheduler
from daily_news_podcast.tts_engine import TTSEngine


# ---------------------------------------------------------------------------
# Helpers — local RSS HTTP server
# ---------------------------------------------------------------------------

def _build_rss_xml() -> bytes:
    """Return sample RSS XML with two articles dated within the last 24 hours."""
    recent_date = email.utils.formatdate(time.time())
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>http://example.com</link>
    <description>Test RSS Feed</description>
    <item>
      <title>Python 3.13 Released</title>
      <link>http://example.com/python-313</link>
      <description>Python 3.13 has been released with new features.</description>
      <pubDate>{recent_date}</pubDate>
    </item>
    <item>
      <title>AI News Today</title>
      <link>http://example.com/ai-news</link>
      <description>Latest developments in artificial intelligence.</description>
      <pubDate>{recent_date}</pubDate>
    </item>
  </channel>
</rss>"""
    return xml.encode("utf-8")


class _RSSHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that serves the sample RSS XML on any GET request."""

    rss_content: bytes = b""  # set before starting the server

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(self.rss_content)))
        self.end_headers()
        self.wfile.write(self.rss_content)

    def log_message(self, *args, **kwargs):  # suppress request logs in test output
        pass


def _start_rss_server(rss_bytes: bytes):
    """Start a local HTTP server in a daemon thread. Returns (server, url)."""
    _RSSHandler.rss_content = rss_bytes
    server = http.server.HTTPServer(("127.0.0.1", 0), _RSSHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/feed"


# ---------------------------------------------------------------------------
# Task 13.1 — Full pipeline integration test with mocked TTS
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    """Integration test: real Aggregator, Filter, Compiler, EpisodeStore, ConfigStore.

    gTTS and pydub are mocked so no network calls or audio I/O occur.
    """

    def test_pipeline_run_returns_valid_episode(self, tmp_path):
        """
        Run Pipeline.run() end-to-end with a local RSS server and mocked TTS.

        Asserts:
        - Returned Episode has total_duration_ms <= 600_000
        - Episode has at least one segment
        - Episode has a non-empty audio_path
        """
        # --- Set up local RSS server ---
        rss_bytes = _build_rss_xml()
        server, feed_url = _start_rss_server(rss_bytes)
        try:
            # --- Directories ---
            audio_dir = tmp_path / "audio"
            audio_dir.mkdir()
            config_dir = tmp_path / "config"
            config_dir.mkdir()
            db_file = tmp_path / "episodes.db"

            # --- ConfigStore pointing at a temp config file ---
            config_file = config_dir / "config.json"
            config_store = ConfigStore(config_file=config_file)
            # Write a config that points at our local RSS server
            app_config = AppConfig(
                sources=[Source(url=feed_url, name="Test Feed")],
                filter=FilterConfig(
                    topics=["python", "ai"],
                    keywords=["released", "news"],
                    relevance_threshold=0.0,  # accept all articles
                ),
                scheduler=SchedulerConfig(),
            )
            config_store.save(app_config)

            # --- EpisodeStore using a temp DB ---
            episode_store = EpisodeStore(db_file=db_file)

            # --- Real components ---
            aggregator = Aggregator()
            filter_ = Filter()
            compiler = Compiler()

            # --- Mock gTTS to write a minimal silent MP3 ---
            # A valid (but silent) MP3 frame header: 5000 ms at 128 kbps ≈ 80 000 bytes.
            # We use a tiny stub that writes a fixed-size bytes object so pydub can
            # measure a duration.  We mock pydub.AudioSegment as well so no ffmpeg
            # subprocess is spawned.
            FIXED_DURATION_MS = 5_000

            def fake_gtts_save(path):
                """Write a placeholder file so the path exists on disk."""
                Path(path).write_bytes(b"\xff\xfb" + b"\x00" * 1024)

            mock_gtts_instance = MagicMock()
            mock_gtts_instance.save.side_effect = fake_gtts_save

            # pydub AudioSegment mock: from_mp3 returns a segment with fixed duration,
            # empty() returns an empty segment, concatenation and export are no-ops.
            def make_mock_audio_segment(duration_ms=FIXED_DURATION_MS):
                seg = MagicMock()
                seg.duration_seconds = duration_ms / 1000.0
                seg.__add__ = lambda self, other: make_mock_audio_segment(
                    self.duration_seconds * 1000 + other.duration_seconds * 1000
                )
                seg.export = MagicMock()
                return seg

            mock_audio_segment_cls = MagicMock()
            mock_audio_segment_cls.from_mp3.side_effect = (
                lambda path: make_mock_audio_segment(FIXED_DURATION_MS)
            )
            mock_audio_segment_cls.empty.return_value = make_mock_audio_segment(0)

            tts_engine = TTSEngine()

            # gTTS and AudioSegment are imported inside the function body in tts_engine.py
            # and compiler.py, so we patch them at their source module (pydub.AudioSegment).
            with patch("gtts.gTTS") as mock_gtts_cls, \
                 patch("pydub.AudioSegment", mock_audio_segment_cls):

                mock_gtts_cls.return_value = mock_gtts_instance

                pipeline = Pipeline(
                    aggregator=aggregator,
                    filter=filter_,
                    tts_engine=tts_engine,
                    compiler=compiler,
                    episode_store=episode_store,
                    config_store=config_store,
                    audio_dir=audio_dir,
                )

                episode = pipeline.run()

            # --- Assertions ---
            assert isinstance(episode, Episode), "pipeline.run() must return an Episode"
            assert episode.total_duration_ms <= 600_000, (
                f"Episode duration {episode.total_duration_ms} ms exceeds 10-minute limit"
            )
            assert len(episode.segments) >= 1, (
                "Episode must contain at least one segment"
            )
            assert episode.audio_path, "Episode must have a non-empty audio_path"

        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# Task 13.2 — Scheduler trigger integration test
# ---------------------------------------------------------------------------

class TestSchedulerTriggerIntegration:
    """Integration test: Scheduler fires the pipeline via a near-future DateTrigger."""

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_scheduler_triggers_pipeline_and_calls_on_success(self):
        """
        Start a Scheduler with a DateTrigger set 3 seconds in the future.
        Assert that the on_success callback is called within 8 seconds.
        """
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.date import DateTrigger

        # --- Mock pipeline that returns a fake episode ---
        fake_episode = Episode(
            date=date.today(),
            segments=[
                Segment(
                    article_url="http://example.com/1",
                    audio_path="/fake/audio/seg1.mp3",
                    duration_ms=30_000,
                )
            ],
            total_duration_ms=30_000,
            audio_path="/fake/audio/episode.mp3",
            created_at=datetime.now(),
        )

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = fake_episode

        # --- Threading event to synchronise the callback ---
        callback_event = threading.Event()
        received_episodes = []

        def on_success(episode):
            received_episodes.append(episode)
            callback_event.set()

        # --- Build Scheduler and wire up the callback ---
        scheduler = Scheduler()
        scheduler.on_success = on_success

        # Use a SchedulerConfig with dummy values; we override the trigger below.
        config = SchedulerConfig(generation_hour=0, generation_minute=0)

        # Patch BackgroundScheduler so we can inject a DateTrigger instead of CronTrigger.
        run_date = datetime.now() + timedelta(seconds=3)
        date_trigger = DateTrigger(run_date=run_date)

        # We start the real APScheduler but replace the CronTrigger with a DateTrigger
        # so the job fires in ~3 seconds rather than waiting until midnight.
        with patch("daily_news_podcast.scheduler.CronTrigger", return_value=date_trigger):
            scheduler.start(config, mock_pipeline)

        try:
            # Wait up to 8 seconds for the callback to fire.
            fired = callback_event.wait(timeout=8)

            assert fired, (
                "Scheduler did not trigger the pipeline within 8 seconds"
            )
            assert len(received_episodes) >= 1, (
                "on_success callback was not called with an episode"
            )
            assert received_episodes[0] is fake_episode, (
                "on_success callback received the wrong episode"
            )
            mock_pipeline.run.assert_called_once()

        finally:
            scheduler.stop()
