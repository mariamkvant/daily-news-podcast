from datetime import date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import get_current_user
from ..schemas import EpisodeResponse
from ..tasks import generate_episode_task

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


@router.get("/today", response_model=EpisodeResponse)
def get_today(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return today's episode. If it doesn't exist yet, kick off generation."""
    today = date.today()
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.user_id == current_user.id, models.Episode.date == today)
        .first()
    )

    if episode is None:
        # Create a placeholder and queue generation
        episode = models.Episode(
            user_id=current_user.id,
            date=today,
            audio_url="",
            status="pending",
        )
        db.add(episode)
        db.commit()
        db.refresh(episode)
        generate_episode_task.delay(current_user.id)

    elif episode.status == "failed":
        # Allow retry
        episode.status = "pending"
        db.commit()
        generate_episode_task.delay(current_user.id)

    return episode


@router.post("/generate", status_code=202)
def generate_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Force-regenerate today's episode."""
    today = date.today()
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.user_id == current_user.id, models.Episode.date == today)
        .first()
    )
    if episode and episode.status == "generating":
        return {"detail": "Already generating"}

    generate_episode_task.delay(current_user.id)
    return {"detail": "Generation started"}


@router.get("/", response_model=list[EpisodeResponse])
def list_episodes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Episode)
        .filter(models.Episode.user_id == current_user.id)
        .order_by(models.Episode.date.desc())
        .limit(30)
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
