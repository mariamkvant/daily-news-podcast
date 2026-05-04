from datetime import datetime, date
from sqlalchemy import (
    Boolean, Column, DateTime, Date, ForeignKey,
    Integer, String, Text, JSON, Float
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    name          = Column(String(100), nullable=False)
    hashed_pw     = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    is_active     = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    verify_token  = Column(String(255), nullable=True)
    verify_token_expires = Column(DateTime, nullable=True)
    reset_token   = Column(String(255), nullable=True)
    reset_token_expires  = Column(DateTime, nullable=True)

    # Preferences
    topics              = Column(JSON, default=list)   # ["world", "technology", ...]
    keywords            = Column(JSON, default=list)   # ["breaking", "ai", ...]
    enabled_sources     = Column(JSON, default=list)   # list of source names
    max_duration_sec    = Column(Integer, default=600) # podcast length
    generation_hour     = Column(Integer, default=7)
    generation_minute   = Column(Integer, default=0)

    episodes = relationship("Episode", back_populates="user", cascade="all, delete-orphan")


class Episode(Base):
    __tablename__ = "episodes"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    date             = Column(Date, nullable=False)
    audio_url        = Column(String(1024), nullable=False)  # S3/R2 URL
    total_duration_ms = Column(Integer, default=0)
    summary          = Column(Text, default="")
    created_at       = Column(DateTime, default=datetime.utcnow)
    status           = Column(String(20), default="pending")  # pending|generating|ready|failed

    user     = relationship("User", back_populates="episodes")
    segments = relationship("Segment", back_populates="episode", cascade="all, delete-orphan",
                            order_by="Segment.position")


class Segment(Base):
    __tablename__ = "segments"

    id          = Column(Integer, primary_key=True, index=True)
    episode_id  = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    position    = Column(Integer, nullable=False)
    article_url = Column(String(1024), default="")
    audio_url   = Column(String(1024), default="")   # S3/R2 URL
    duration_ms = Column(Integer, default=0)
    title       = Column(Text, default="")
    source_name = Column(String(255), default="")
    summary     = Column(Text, default="")
    spoken_text = Column(Text, default="")

    episode = relationship("Episode", back_populates="segments")
