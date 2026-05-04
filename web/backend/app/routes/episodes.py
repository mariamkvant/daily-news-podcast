import logging
import threading
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from .. import models
from ..auth import get_current_user
from ..schemas import EpisodeResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def _run_generation_in_thread(user_id: int) -> None:
    """Run episode generation directly in a background thread (no Celery needed)."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timedelta
    from pathlib import Path
    from ..core.aggregator import fetch_articles
    from ..core.filter import score_and_select
    from ..core.tts_engine import generate_segment
    from ..core.compiler import compile_episode
    from ..core.catalog import ALL_SOURCES
    from ..storage import upload_audio

    db = SessionLocal()
    episode_row = None
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return

        today = date.today()
        episode_row = db.query(models.Episode).filter(
            models.Episode.user_id == user_id,
            models.Episode.date == today,
        ).first()
        if episode_row is None:
            episode_row = models.Episode(user_id=user_id, date=today, audio_url="", status="generating")
            db.add(episode_row)
        else:
            episode_row.status = "generating"
        db.commit()
        db.refresh(episode_row)

        enabled = set(user.enabled_sources or [])
        sources = [(name, url) for name, url, _ in ALL_SOURCES if name in enabled]
        if not sources:
            sources = [(name, url) for name, url, _ in ALL_SOURCES[:6]]

        since = datetime.now() - timedelta(hours=24)
        articles = fetch_articles(sources, since)
        logger.info("User %d: fetched %d articles", user_id, len(articles))

        filtered = score_and_select(
            articles,
            topics=user.topics or [],
            keywords=user.keywords or [],
        )
        logger.info("User %d: filtered to %d articles", user_id, len(filtered))

        # Cap at 8 articles — enough for a good episode, fast enough to generate
        max_articles = min(len(filtered), 8)
        filtered = filtered[:max_articles]

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir)

            # Generate TTS segments in parallel (6 workers)
            # Use a lock to prevent race conditions on the temp directory
            segments_map: dict[int, object] = {}
            lock = threading.Lock()

            def _gen_segment(idx_article):
                idx, article = idx_article
                try:
                    seg = generate_segment(article, audio_dir)
                    if seg:
                        with lock:
                            segments_map[idx] = seg
                except Exception as e:
                    logger.warning("User %d: TTS failed for article %d: %s", user_id, idx, e)

            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(_gen_segment, enumerate(filtered)))

            # Restore original order
            segments = [segments_map[i] for i in sorted(segments_map.keys())]
            logger.info("User %d: generated %d/%d segments", user_id, len(segments), len(filtered))

            if not segments:
                episode_row.status = "failed"
                db.commit()
                logger.error("User %d: no segments generated", user_id)
                return

            episode = compile_episode(
                segments, today, audio_dir,
                max_duration_seconds=user.max_duration_sec or 600,
            )

            ep_key = f"users/{user_id}/episodes/{today.isoformat()}.mp3"
            ep_url = upload_audio(episode.audio_path, ep_key)

            episode_row.audio_url = ep_url
            episode_row.total_duration_ms = episode.total_duration_ms
            episode_row.summary = episode.summary
            episode_row.status = "ready"

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
            logger.info("User %d: episode ready at %s", user_id, ep_url)

    except Exception as exc:
        logger.exception("Episode generation failed for user %d at step unknown: %s", user_id, exc)
        if episode_row:
            try:
                episode_row.status = "failed"
                db.commit()
            except Exception:
                pass
    finally:
        db.close()


def _trigger_generation(user_id: int) -> None:
    """Always run generation in a background thread (no Celery worker deployed)."""
    t = threading.Thread(target=_run_generation_in_thread, args=(user_id,), daemon=True)
    t.start()
    logger.info("Started background generation thread for user %d", user_id)


@router.get("/today", response_model=EpisodeResponse)
def get_today(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = date.today()
    episode = db.query(models.Episode).filter(
        models.Episode.user_id == current_user.id,
        models.Episode.date == today,
    ).first()

    if episode is None:
        episode = models.Episode(
            user_id=current_user.id, date=today, audio_url="", status="pending",
        )
        db.add(episode)
        db.commit()
        db.refresh(episode)
        _trigger_generation(current_user.id)

    elif episode.status == "failed":
        episode.status = "pending"
        db.commit()
        _trigger_generation(current_user.id)

    elif episode.status == "pending":
        # Stuck pending — re-trigger
        _trigger_generation(current_user.id)

    return episode


@router.post("/generate", status_code=202)
def generate_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = date.today()
    episode = db.query(models.Episode).filter(
        models.Episode.user_id == current_user.id,
        models.Episode.date == today,
    ).first()
    if episode and episode.status == "generating":
        return {"detail": "Already generating"}

    if episode:
        episode.status = "pending"
        db.commit()

    _trigger_generation(current_user.id)
    return {"detail": "Generation started"}


@router.post("/cancel")
def cancel_generation(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel a stuck generating episode for the current user."""
    today = date.today()
    episode = db.query(models.Episode).filter(
        models.Episode.user_id == current_user.id,
        models.Episode.date == today,
    ).first()
    if episode and episode.status in ("generating", "pending"):
        episode.status = "failed"
        db.commit()
        return {"detail": "Cancelled"}
    return {"detail": "Nothing to cancel"}


@router.get("/", response_model=list[EpisodeResponse])
def list_episodes(
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Episode)
        .filter(models.Episode.user_id == current_user.id)
        .order_by(models.Episode.date.desc())
        .offset(offset).limit(min(limit, 100))
        .all()
    )


@router.get("/{episode_id}", response_model=EpisodeResponse)
def get_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    episode = db.query(models.Episode).filter(
        models.Episode.id == episode_id,
        models.Episode.user_id == current_user.id,
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode
