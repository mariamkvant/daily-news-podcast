from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# User / Preferences
# ---------------------------------------------------------------------------

class PreferencesUpdate(BaseModel):
    topics: list[str] = []
    keywords: list[str] = []
    enabled_sources: list[str] = []
    max_duration_sec: int = 600
    generation_hour: int = 7
    generation_minute: int = 0


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    topics: list[str]
    keywords: list[str]
    enabled_sources: list[str]
    max_duration_sec: int
    generation_hour: int
    generation_minute: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------

class SegmentResponse(BaseModel):
    id: int
    position: int
    title: str
    source_name: str
    summary: str
    audio_url: str
    duration_ms: int
    article_url: str

    class Config:
        from_attributes = True


class EpisodeResponse(BaseModel):
    id: int
    date: date
    audio_url: str
    total_duration_ms: int
    summary: str
    status: str
    created_at: datetime
    segments: list[SegmentResponse] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class CatalogResponse(BaseModel):
    topics: list[str]
    keywords: list[str]
    sources: list[dict]
