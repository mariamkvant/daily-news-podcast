from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class Source:
    url: str          # RSS feed URL
    name: str         # Human-readable label
    enabled: bool = True  # Whether this source is active


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source_name: str
    published_at: datetime
    relevance_score: float = 0.0


@dataclass
class Segment:
    article_url: str   # Foreign key to Article
    audio_path: str    # Absolute path to MP3 file
    duration_ms: int   # Duration in milliseconds
    title: str = ""          # Article title (for transcript)
    source_name: str = ""    # Source feed name (for transcript)
    spoken_text: str = ""    # Full text that was converted to speech
    summary: str = ""        # Original article summary (for display)


@dataclass
class Episode:
    date: date
    segments: list[Segment]
    total_duration_ms: int
    audio_path: str    # Path to the compiled full-episode MP3
    created_at: datetime
    summary: str = ""  # Auto-generated overview of all stories


@dataclass
class FilterConfig:
    topics: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    relevance_threshold: float = 0.05


@dataclass
class SchedulerConfig:
    generation_hour: int = 7
    generation_minute: int = 0


@dataclass
class AppConfig:
    sources: list[Source] = field(default_factory=list)
    filter: FilterConfig = field(default_factory=FilterConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    max_duration_seconds: int = 600  # Target podcast length (60, 300, 600, 900, 1800, 3600)


@dataclass
class PlayerState:
    is_playing: bool
    current_segment_index: int
    total_segments: int
    elapsed_episode_ms: int
    episode_ended: bool
