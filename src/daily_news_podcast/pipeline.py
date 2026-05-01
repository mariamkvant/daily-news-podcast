# Pipeline: wires Aggregator -> Filter -> TTSEngine -> Compiler -> EpisodeStore.
import logging
from datetime import datetime, timedelta, date
from pathlib import Path

from .aggregator import Aggregator
from .compiler import Compiler
from .config_store import ConfigStore
from .episode_store import EpisodeStore
from .filter import Filter
from .models import Episode
from .tts_engine import TTSEngine

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


class Pipeline:
    def __init__(
        self,
        aggregator: Aggregator,
        filter: Filter,
        tts_engine: TTSEngine,
        compiler: Compiler,
        episode_store: EpisodeStore,
        config_store: ConfigStore,
        audio_dir: Path,
    ):
        self.aggregator = aggregator
        self.filter = filter
        self.tts_engine = tts_engine
        self.compiler = compiler
        self.episode_store = episode_store
        self.config_store = config_store
        self.audio_dir = audio_dir

    def run(self) -> Episode:
        """
        Run the full pipeline: fetch -> filter -> TTS -> compile -> save.
        Raises PipelineError if 0 segments are produced.
        """
        # 1. Load config
        config = self.config_store.load()

        # 2. Fetch articles from the last 24 hours
        since = datetime.now() - timedelta(hours=24)
        articles = self.aggregator.fetch(config.sources, since=since)
        logger.info("Fetched %d articles from %d sources.", len(articles), len(config.sources))

        # 3. Filter articles by relevance
        filtered_articles = self.filter.score_and_select(articles, config.filter)
        logger.info("Filtered to %d relevant articles.", len(filtered_articles))

        # 4. Generate TTS segments (skip None results)
        segments = []
        for article in filtered_articles:
            segment = self.tts_engine.generate_segment(article, self.audio_dir)
            if segment is not None:
                segments.append(segment)
        logger.info("Generated %d audio segments.", len(segments))

        # 5. Compile segments into an episode
        episode = self.compiler.compile(segments, date.today(), self.tts_engine, self.audio_dir)

        # 6. Raise if no segments were produced
        if len(episode.segments) == 0:
            raise PipelineError("No segments could be generated")

        # 7. Save the episode
        self.episode_store.save(episode)
        logger.info("Episode saved: %s", episode.audio_path)

        # 8. Return the episode
        return episode
