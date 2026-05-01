# Tests for Pipeline.run() and Scheduler.start()
import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from daily_news_podcast.pipeline import Pipeline, PipelineError
from daily_news_podcast.scheduler import Scheduler
from daily_news_podcast.models import (
    AppConfig,
    Article,
    Episode,
    FilterConfig,
    SchedulerConfig,
    Segment,
    Source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article(url: str = "http://example.com/1") -> Article:
    return Article(
        title="Test Article",
        summary="This is a test summary.",
        url=url,
        source_name="Test Source",
        published_at=datetime(2024, 1, 15, 8, 0, 0),
        relevance_score=0.9,
    )


def make_segment(url: str = "http://example.com/1", duration_ms: int = 30_000) -> Segment:
    return Segment(
        article_url=url,
        audio_path=f"/fake/audio/{abs(hash(url))}.mp3",
        duration_ms=duration_ms,
    )


def make_episode(segments=None) -> Episode:
    if segments is None:
        segments = [make_segment()]
    return Episode(
        date=date(2024, 1, 15),
        segments=segments,
        total_duration_ms=sum(s.duration_ms for s in segments),
        audio_path="/fake/audio/episode_2024-01-15.mp3",
        created_at=datetime(2024, 1, 15, 8, 0, 0),
    )


def make_pipeline(
    articles=None,
    filtered_articles=None,
    segment=None,
    episode=None,
    config=None,
):
    """Build a Pipeline with all components mocked."""
    if articles is None:
        articles = [make_article()]
    if filtered_articles is None:
        filtered_articles = list(articles)
    if segment is None:
        segment = make_segment()
    if episode is None:
        episode = make_episode([segment])
    if config is None:
        config = AppConfig(
            sources=[Source(url="http://feeds.example.com/rss", name="Example")],
            filter=FilterConfig(),
            scheduler=SchedulerConfig(),
        )

    aggregator = MagicMock()
    aggregator.fetch.return_value = articles

    filter_ = MagicMock()
    filter_.score_and_select.return_value = filtered_articles

    tts_engine = MagicMock()
    tts_engine.generate_segment.return_value = segment

    compiler = MagicMock()
    compiler.compile.return_value = episode

    episode_store = MagicMock()
    config_store = MagicMock()
    config_store.load.return_value = config

    pipeline = Pipeline(
        aggregator=aggregator,
        filter=filter_,
        tts_engine=tts_engine,
        compiler=compiler,
        episode_store=episode_store,
        config_store=config_store,
        audio_dir=Path("/fake/audio"),
    )
    return pipeline, {
        "aggregator": aggregator,
        "filter": filter_,
        "tts_engine": tts_engine,
        "compiler": compiler,
        "episode_store": episode_store,
        "config_store": config_store,
    }


# ---------------------------------------------------------------------------
# Pipeline.run() — happy path
# ---------------------------------------------------------------------------

class TestPipelineRunSuccess:
    def test_returns_episode(self):
        pipeline, _ = make_pipeline()
        result = pipeline.run()
        assert isinstance(result, Episode)

    def test_returns_correct_episode(self):
        expected = make_episode()
        pipeline, _ = make_pipeline(episode=expected)
        result = pipeline.run()
        assert result is expected

    def test_calls_config_store_load(self):
        pipeline, mocks = make_pipeline()
        pipeline.run()
        mocks["config_store"].load.assert_called_once()

    def test_calls_aggregator_fetch_with_sources(self):
        config = AppConfig(
            sources=[Source(url="http://feeds.example.com/rss", name="Example")],
            filter=FilterConfig(),
            scheduler=SchedulerConfig(),
        )
        pipeline, mocks = make_pipeline(config=config)
        pipeline.run()
        call_args = mocks["aggregator"].fetch.call_args
        assert call_args[0][0] == config.sources or call_args[1].get("sources") == config.sources or call_args[0][0] == config.sources

    def test_calls_filter_score_and_select(self):
        pipeline, mocks = make_pipeline()
        pipeline.run()
        mocks["filter"].score_and_select.assert_called_once()

    def test_calls_tts_engine_for_each_article(self):
        articles = [make_article(f"http://example.com/{i}") for i in range(3)]
        pipeline, mocks = make_pipeline(
            articles=articles,
            filtered_articles=articles,
            episode=make_episode([make_segment(a.url) for a in articles]),
        )
        pipeline.run()
        assert mocks["tts_engine"].generate_segment.call_count == 3

    def test_calls_compiler_compile(self):
        pipeline, mocks = make_pipeline()
        pipeline.run()
        mocks["compiler"].compile.assert_called_once()

    def test_calls_episode_store_save_on_success(self):
        episode = make_episode()
        pipeline, mocks = make_pipeline(episode=episode)
        pipeline.run()
        mocks["episode_store"].save.assert_called_once_with(episode)

    def test_none_segments_are_skipped(self):
        """TTS returning None for some articles should not include them in segments."""
        articles = [make_article(f"http://example.com/{i}") for i in range(3)]
        good_segment = make_segment("http://example.com/0")
        episode = make_episode([good_segment])

        pipeline, mocks = make_pipeline(
            articles=articles,
            filtered_articles=articles,
            episode=episode,
        )
        # First call returns a segment, subsequent calls return None
        mocks["tts_engine"].generate_segment.side_effect = [
            good_segment, None, None
        ]
        result = pipeline.run()
        assert isinstance(result, Episode)
        # Compiler should have been called with only the one non-None segment
        compile_call_args = mocks["compiler"].compile.call_args
        passed_segments = compile_call_args[0][0]
        assert len(passed_segments) == 1
        assert passed_segments[0] is good_segment


# ---------------------------------------------------------------------------
# Pipeline.run() — PipelineError when 0 segments
# ---------------------------------------------------------------------------

class TestPipelineRunNoSegments:
    def test_raises_pipeline_error_when_zero_segments(self):
        empty_episode = make_episode(segments=[])
        pipeline, _ = make_pipeline(episode=empty_episode)
        with pytest.raises(PipelineError, match="No segments could be generated"):
            pipeline.run()

    def test_does_not_save_when_zero_segments(self):
        empty_episode = make_episode(segments=[])
        pipeline, mocks = make_pipeline(episode=empty_episode)
        with pytest.raises(PipelineError):
            pipeline.run()
        mocks["episode_store"].save.assert_not_called()

    def test_raises_pipeline_error_when_all_tts_fail(self):
        articles = [make_article(f"http://example.com/{i}") for i in range(3)]
        empty_episode = make_episode(segments=[])
        pipeline, mocks = make_pipeline(
            articles=articles,
            filtered_articles=articles,
            episode=empty_episode,
        )
        mocks["tts_engine"].generate_segment.return_value = None
        with pytest.raises(PipelineError):
            pipeline.run()


# ---------------------------------------------------------------------------
# Scheduler.start() — cron job registration
# ---------------------------------------------------------------------------

class TestSchedulerStart:
    def test_registers_cron_job_with_correct_hour_and_minute(self):
        """Scheduler.start() should add a job with the configured hour and minute."""
        scheduler = Scheduler()
        config = SchedulerConfig(generation_hour=6, generation_minute=30)
        pipeline = MagicMock()
        pipeline.run.return_value = make_episode()

        with patch("daily_news_podcast.scheduler.BackgroundScheduler") as mock_bg_cls, \
             patch("daily_news_podcast.scheduler.CronTrigger") as mock_cron_cls:

            mock_bg_instance = MagicMock()
            mock_bg_cls.return_value = mock_bg_instance
            mock_cron_instance = MagicMock()
            mock_cron_cls.return_value = mock_cron_instance

            scheduler.start(config, pipeline)

            # CronTrigger should be created with the correct hour and minute
            mock_cron_cls.assert_called_once_with(hour=6, minute=30)
            # A job should be added to the scheduler
            mock_bg_instance.add_job.assert_called_once()
            # The scheduler should be started
            mock_bg_instance.start.assert_called_once()

    def test_registers_default_hour_and_minute(self):
        """Default SchedulerConfig uses hour=7, minute=0."""
        scheduler = Scheduler()
        config = SchedulerConfig()  # defaults: hour=7, minute=0
        pipeline = MagicMock()

        with patch("daily_news_podcast.scheduler.BackgroundScheduler") as mock_bg_cls, \
             patch("daily_news_podcast.scheduler.CronTrigger") as mock_cron_cls:

            mock_bg_cls.return_value = MagicMock()
            mock_cron_cls.return_value = MagicMock()

            scheduler.start(config, pipeline)

            mock_cron_cls.assert_called_once_with(hour=7, minute=0)

    def test_stop_shuts_down_scheduler(self):
        """Scheduler.stop() should call shutdown on the underlying scheduler."""
        scheduler = Scheduler()
        config = SchedulerConfig(generation_hour=7, generation_minute=0)
        pipeline = MagicMock()

        with patch("daily_news_podcast.scheduler.BackgroundScheduler") as mock_bg_cls, \
             patch("daily_news_podcast.scheduler.CronTrigger"):

            mock_bg_instance = MagicMock()
            mock_bg_cls.return_value = mock_bg_instance

            scheduler.start(config, pipeline)
            scheduler.stop()

            mock_bg_instance.shutdown.assert_called_once_with(wait=False)

    def test_on_success_callback_called_when_pipeline_succeeds(self):
        """on_success callback should be invoked with the episode on success."""
        scheduler = Scheduler()
        config = SchedulerConfig(generation_hour=7, generation_minute=0)
        episode = make_episode()
        pipeline = MagicMock()
        pipeline.run.return_value = episode

        success_callback = MagicMock()
        scheduler.on_success = success_callback

        with patch("daily_news_podcast.scheduler.BackgroundScheduler") as mock_bg_cls, \
             patch("daily_news_podcast.scheduler.CronTrigger"):

            mock_bg_instance = MagicMock()
            mock_bg_cls.return_value = mock_bg_instance

            scheduler.start(config, pipeline)

            # Extract the job function that was registered and call it directly
            job_func = mock_bg_instance.add_job.call_args[0][0]
            job_func()

            success_callback.assert_called_once_with(episode)

    def test_on_failure_callback_called_when_pipeline_fails(self):
        """on_failure callback should be invoked with the error message on failure."""
        from daily_news_podcast.pipeline import PipelineError

        scheduler = Scheduler()
        config = SchedulerConfig(generation_hour=7, generation_minute=0)
        pipeline = MagicMock()
        pipeline.run.side_effect = PipelineError("No segments could be generated")

        failure_callback = MagicMock()
        scheduler.on_failure = failure_callback

        with patch("daily_news_podcast.scheduler.BackgroundScheduler") as mock_bg_cls, \
             patch("daily_news_podcast.scheduler.CronTrigger"):

            mock_bg_instance = MagicMock()
            mock_bg_cls.return_value = mock_bg_instance

            scheduler.start(config, pipeline)

            job_func = mock_bg_instance.add_job.call_args[0][0]
            job_func()

            failure_callback.assert_called_once_with("No segments could be generated")
