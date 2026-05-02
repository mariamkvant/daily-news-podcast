"""EpisodeStore: persists episode metadata and segment file paths in SQLite."""

import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import Episode, Segment

logger = logging.getLogger(__name__)

_DATA_DIR = Path.home() / ".daily-news-podcast"
_DB_FILE = _DATA_DIR / "episodes.db"

_CREATE_EPISODES_TABLE = """
CREATE TABLE IF NOT EXISTS episodes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL UNIQUE,
    audio_path        TEXT NOT NULL,
    total_duration_ms INTEGER NOT NULL,
    created_at        TEXT NOT NULL,
    summary           TEXT NOT NULL DEFAULT ''
);
"""

_CREATE_SEGMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS segments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id),
    position    INTEGER NOT NULL,
    article_url TEXT NOT NULL,
    audio_path  TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    spoken_text TEXT NOT NULL DEFAULT '',
    summary     TEXT NOT NULL DEFAULT ''
);
"""

# Migration: add columns that may be missing in older databases
_MIGRATIONS = [
    "ALTER TABLE episodes ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE segments ADD COLUMN title TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE segments ADD COLUMN source_name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE segments ADD COLUMN spoken_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE segments ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
]


class EpisodeStore:
    """Persists episode metadata and segment file paths in SQLite."""

    def __init__(self, db_file: Path = _DB_FILE) -> None:
        self._db_file = db_file
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_EPISODES_TABLE)
            conn.execute(_CREATE_SEGMENTS_TABLE)
            # Run migrations silently (ignore "duplicate column" errors)
            for sql in _MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def save(self, episode: Episode) -> None:
        """Insert or replace episode and its segments; clean up old audio files."""
        with self._connect() as conn:
            # Grab previous latest for cleanup
            row = conn.execute(
                "SELECT id, audio_path FROM episodes ORDER BY date DESC LIMIT 1"
            ).fetchone()
            previous_episode_id: int | None = None
            previous_audio_paths: list[str] = []
            if row is not None:
                previous_episode_id = row["id"]
                previous_audio_paths.append(row["audio_path"])
                seg_rows = conn.execute(
                    "SELECT audio_path FROM segments WHERE episode_id = ?",
                    (previous_episode_id,),
                ).fetchall()
                previous_audio_paths.extend(r["audio_path"] for r in seg_rows)

            date_str = episode.date.isoformat()
            created_at_str = episode.created_at.isoformat()

            # Remove existing row for this date (UNIQUE constraint)
            existing = conn.execute(
                "SELECT id FROM episodes WHERE date = ?", (date_str,)
            ).fetchone()
            if existing is not None:
                conn.execute("DELETE FROM segments WHERE episode_id = ?", (existing["id"],))
                conn.execute("DELETE FROM episodes WHERE id = ?", (existing["id"],))

            cursor = conn.execute(
                """
                INSERT INTO episodes (date, audio_path, total_duration_ms, created_at, summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date_str, episode.audio_path, episode.total_duration_ms,
                 created_at_str, episode.summary),
            )
            episode_id = cursor.lastrowid

            for position, seg in enumerate(episode.segments):
                conn.execute(
                    """
                    INSERT INTO segments
                        (episode_id, position, article_url, audio_path, duration_ms,
                         title, source_name, spoken_text, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (episode_id, position, seg.article_url, seg.audio_path, seg.duration_ms,
                     seg.title, seg.source_name, seg.spoken_text, seg.summary),
                )

            conn.commit()

        # Delete previous episode audio files
        if previous_episode_id is not None:
            for path_str in previous_audio_paths:
                try:
                    os.remove(path_str)
                    logger.debug("Deleted old audio file: %s", path_str)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.warning("Could not delete old audio file %s: %s", path_str, exc)

    def load_latest(self) -> Episode | None:
        """Return the most recent episode with all segment fields, or None."""
        with self._connect() as conn:
            ep_row = conn.execute(
                "SELECT * FROM episodes ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if ep_row is None:
                return None

            seg_rows = conn.execute(
                "SELECT * FROM segments WHERE episode_id = ? ORDER BY position ASC",
                (ep_row["id"],),
            ).fetchall()

        segments = [
            Segment(
                article_url=r["article_url"],
                audio_path=r["audio_path"],
                duration_ms=r["duration_ms"],
                title=r["title"],
                source_name=r["source_name"],
                spoken_text=r["spoken_text"],
                summary=r["summary"],
            )
            for r in seg_rows
        ]

        return Episode(
            date=date.fromisoformat(ep_row["date"]),
            segments=segments,
            total_duration_ms=ep_row["total_duration_ms"],
            audio_path=ep_row["audio_path"],
            created_at=datetime.fromisoformat(ep_row["created_at"]),
            summary=ep_row["summary"],
        )
