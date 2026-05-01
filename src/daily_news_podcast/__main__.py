# Application entry point: initialises all components and starts the tkinter main loop.
"""
__main__.py — Daily News Podcast application entry point.

Usage:
    python -m daily_news_podcast
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Set up logging
    # ------------------------------------------------------------------
    log_dir = Path.home() / ".daily-news-podcast"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    rotating_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    rotating_handler.setLevel(logging.INFO)
    rotating_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    # Also log to stderr so errors are visible when running interactively.
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    logging.basicConfig(level=logging.INFO, handlers=[rotating_handler, stream_handler])

    logger = logging.getLogger(__name__)
    logger.info("Daily News Podcast starting up.")

    # ------------------------------------------------------------------
    # 2. Initialise components
    # ------------------------------------------------------------------
    from .aggregator import Aggregator
    from .compiler import Compiler
    from .config_store import ConfigStore
    from .episode_store import EpisodeStore
    from .filter import Filter
    from .pipeline import Pipeline
    from .player import Player
    from .scheduler import Scheduler
    from .tts_engine import TTSEngine
    from .ui import App

    audio_dir = Path.home() / ".daily-news-podcast" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    config_store = ConfigStore()
    episode_store = EpisodeStore()
    aggregator = Aggregator()
    filter_ = Filter()
    tts_engine = TTSEngine()
    compiler = Compiler()
    pipeline = Pipeline(
        aggregator=aggregator,
        filter=filter_,
        tts_engine=tts_engine,
        compiler=compiler,
        episode_store=episode_store,
        config_store=config_store,
        audio_dir=audio_dir,
    )
    scheduler = Scheduler()
    player = Player()

    # ------------------------------------------------------------------
    # 3. Load config and start scheduler
    # ------------------------------------------------------------------
    config = config_store.load()
    try:
        scheduler.start(config.scheduler, pipeline)
    except Exception as exc:
        logger.error("Failed to start scheduler: %s", exc)

    # ------------------------------------------------------------------
    # 4. Launch the tkinter main loop
    # ------------------------------------------------------------------
    app = App(
        config_store=config_store,
        episode_store=episode_store,
        pipeline=pipeline,
        scheduler=scheduler,
        player=player,
    )

    try:
        app.mainloop()
    finally:
        # ------------------------------------------------------------------
        # 5. Clean up on exit
        # ------------------------------------------------------------------
        logger.info("Daily News Podcast shutting down.")
        scheduler.stop()


if __name__ == "__main__":
    main()
