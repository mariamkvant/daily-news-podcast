"""Celery tasks: generate a podcast episode for a user."""
import logging
import os
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path

from celery import Celery

from .core.aggregator import fetch_articles
from .core.filter import score_and_select
from .core.tts_engine import generate_segment
from .core.compiler import compile_episode
from .core.catalog import ALL_SOURCES
from .storage import upload_audio

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("podcast", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_expires = 3600


@celery_app.task(bind=True, max_retries=2)
def generate_episode_task(self, user_id: int):
    """Generate today's episode for a user and update the DB."""
    from .database import SessionLocal
    from . import models

    db = SessionLocal()
    episode_row = None
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            logger.error("User %d not found", user_id)
            return

        # Find or create today's episode row
        today = date.today()
        episode_row = (
            db.query(models.Episode)
            .filter(models.Episode.user_id == user_id, models.Episode.date == today)
            .first()
        )
        if episode_row is None:
            episode_row = models.Episode(user_id=user_id, date=today, audio_url="", status="generating")
            db.add(episode_row)
        else:
            episode_row.status = "generating"
        db.commit()
        db.refresh(episode_row)

        # Build source list from user preferences
        enabled = set(user.enabled_sources or [])
        sources = [(name, url) for name, url, _ in ALL_SOURCES if name in enabled]
        if not sources:
            sources = [(name, url) for name, url, _ in ALL_SOURCES[:6]]

        # Fetch & filter articles
        since = datetime.now() - timedelta(hours=24)
        articles = fetch_articles(sources, since)
        filtered = score_and_select(
            articles,
            topics=user.topics or [],
            keywords=user.keywords or [],
        )

        # Generate TTS segments
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir)
            segments = []
            for article in filtered:
                seg = generate_segment(article, audio_dir)
                if seg:
                    segments.append(seg)

            if not segments:
                episode_row.status = "failed"
                db.commit()
                return

            # Compile episode
            episode = compile_episode(
                segments, today, audio_dir,
                max_duration_seconds=user.max_duration_sec or 600,
            )

            # Upload episode audio
            ep_key = f"users/{user_id}/episodes/{today.isoformat()}.mp3"
            ep_url = upload_audio(episode.audio_path, ep_key)

            # Upload segment audio files and save to DB
            episode_row.audio_url = ep_url
            episode_row.total_duration_ms = episode.total_duration_ms
            episode_row.summary = episode.summary
            episode_row.status = "ready"

            # Clear old segments
            db.query(models.Segment).filter(models.Segment.episode_id == episode_row.id).delete()

            for pos, seg in enumerate(episode.segments):
                seg_key = f"users/{user_id}/segments/{today.isoformat()}_{pos}.mp3"
                seg_url = upload_audio(seg.audio_path, seg_key)
                db.add(models.Segment(
                    episode_id=episode_row.id,
                    position=pos,
                    article_url=seg.article_url,
                    audio_url=seg_url,
                    duration_ms=seg.duration_ms,
                    title=seg.title,
                    source_name=seg.source_name,
                    summary=seg.summary,
                    spoken_text=seg.spoken_text,
                ))

            db.commit()
            logger.info("Episode generated for user %d: %s", user_id, ep_url)

    except Exception as exc:
        logger.exception("Episode generation failed for user %d: %s", user_id, exc)
        if episode_row:
            episode_row.status = "failed"
            db.commit()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
