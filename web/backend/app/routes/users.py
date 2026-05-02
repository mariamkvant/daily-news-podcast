from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import get_current_user
from ..schemas import UserResponse, PreferencesUpdate, CatalogResponse
from ..core.catalog import AVAILABLE_TOPICS, AVAILABLE_KEYWORDS, ALL_SOURCES

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/me/preferences", response_model=UserResponse)
def update_preferences(
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user.topics = body.topics
    current_user.keywords = body.keywords
    current_user.enabled_sources = body.enabled_sources
    current_user.max_duration_sec = body.max_duration_sec
    current_user.generation_hour = body.generation_hour
    current_user.generation_minute = body.generation_minute
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog():
    return CatalogResponse(
        topics=AVAILABLE_TOPICS,
        keywords=AVAILABLE_KEYWORDS,
        sources=[
            {"name": name, "url": url, "topics": topics}
            for name, url, topics in ALL_SOURCES
        ],
    )
