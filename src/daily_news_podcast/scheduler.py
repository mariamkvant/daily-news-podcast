# Scheduler: triggers the daily pipeline via APScheduler cron job.
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .models import SchedulerConfig

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._scheduler = None
        self.on_success = None  # callback(episode: Episode) -> None
        self.on_failure = None  # callback(error_msg: str) -> None

    def start(self, config: SchedulerConfig, pipeline) -> None:
        """Start APScheduler with a daily cron trigger."""
        self._scheduler = BackgroundScheduler()

        trigger = CronTrigger(
            hour=config.generation_hour,
            minute=config.generation_minute,
        )

        def _run_pipeline():
            try:
                episode = pipeline.run()
                logger.info("Pipeline completed successfully: %s", episode.audio_path)
                if self.on_success is not None:
                    self.on_success(episode)
            except Exception as error:
                logger.error("Pipeline failed: %s", error)
                if self.on_failure is not None:
                    self.on_failure(str(error))

        self._scheduler.add_job(_run_pipeline, trigger)
        self._scheduler.start()
        logger.info(
            "Scheduler started. Pipeline will run daily at %02d:%02d.",
            config.generation_hour,
            config.generation_minute,
        )

    def stop(self) -> None:
        """Shut down the scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Scheduler stopped.")
