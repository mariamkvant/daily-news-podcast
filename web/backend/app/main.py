import os
import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Daily News Podcast API", version="1.0.0")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://dailypodcast.live",
    "https://www.dailypodcast.live",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routes import auth, users, episodes
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(episodes.router)

if not os.environ.get("AWS_BUCKET_NAME"):
    Path("/tmp/audio").mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory="/tmp/audio"), name="audio")


@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    try:
        from .database import engine
        from sqlalchemy import text, inspect
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        tables = inspect(engine).get_table_names()
        return {"db": "connected", "tables": tables}
    except Exception as e:
        return {"db": "error", "detail": str(e)}


@app.post("/run-migrations")
def run_migrations():
    """Force-run DB migrations immediately."""
    try:
        from .database import engine
        from . import models
        from sqlalchemy import text
        models.Base.metadata.create_all(bind=engine)
        results = []
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token_expires TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP",
            "UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL OR is_verified = FALSE",
        ]
        with engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    results.append({"sql": sql[:60], "status": "ok"})
                except Exception as e:
                    results.append({"sql": sql[:60], "status": str(e)})
            conn.commit()
        return {"status": "done", "results": results}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/test-generation")
def test_generation():
    """Test the generation pipeline step by step."""
    import tempfile
    from datetime import datetime, timedelta
    from pathlib import Path
    results = {}
    try:
        from .core.aggregator import fetch_articles
        from .core.catalog import ALL_SOURCES
        since = datetime.now() - timedelta(hours=24)
        sources = [(name, url) for name, url, _ in ALL_SOURCES[:3]]
        articles = fetch_articles(sources, since)
        results["articles_fetched"] = len(articles)
        from .core.filter import score_and_select
        filtered = score_and_select(articles, topics=["world", "technology"], keywords=[])
        results["articles_filtered"] = len(filtered)
        if not filtered:
            return {"status": "no_articles", **results}
        with tempfile.TemporaryDirectory() as tmpdir:
            from .core.tts_engine import generate_segment
            seg = generate_segment(filtered[0], Path(tmpdir))
            results["tts_ok"] = seg is not None
            if seg:
                results["segment_duration_ms"] = seg.duration_ms
                results["audio_path_exists"] = Path(seg.audio_path).exists()
                from .storage import upload_audio
                url = upload_audio(seg.audio_path, f"test/test_segment.mp3")
                results["upload_url"] = url
        return {"status": "ok", **results}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "trace": traceback.format_exc(), **results}


@app.get("/reset-stuck")
@app.post("/reset-stuck-episodes")
def reset_stuck_episodes():
    """Reset stuck pending/generating episodes to failed so they regenerate on next visit."""
    try:
        from .database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(
                "UPDATE episodes SET status='failed' "
                "WHERE status IN ('pending','generating') "
                "RETURNING id, user_id, status"
            ))
            rows = [dict(r._mapping) for r in result]
            conn.commit()
        return {"reset": len(rows), "episodes": rows}
    except Exception as e:
        return {"error": str(e)}
    """Reset stuck pending/generating episodes to failed so they regenerate on next visit."""
    try:
        from .database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(
                "UPDATE episodes SET status='failed' "
                "WHERE status IN ('pending','generating') "
                "RETURNING id, user_id, status"
            ))
            rows = [dict(r._mapping) for r in result]
            conn.commit()
        return {"reset": len(rows), "episodes": rows}
    except Exception as e:
        return {"error": str(e)}


def _init_db():
    """Run DB table creation and migrations in a background thread."""
    import time
    for attempt in range(10):
        try:
            from .database import engine
            from . import models
            from sqlalchemy import text

            # Create any missing tables
            models.Base.metadata.create_all(bind=engine)

            # Run column migrations for existing tables
            with engine.connect() as conn:
                migrations = [
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token VARCHAR(255)",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token_expires TIMESTAMP",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255)",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP",
                    # Set existing users as verified so they can still log in
                    "UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL OR is_verified = FALSE",
                ]
                for sql in migrations:
                    try:
                        conn.execute(text(sql))
                    except Exception as e:
                        logger.warning("Migration skipped: %s", e)
                conn.commit()

            logger.info("DB ready (attempt %d).", attempt + 1)
            return
        except Exception as e:
            logger.warning("DB init attempt %d failed: %s", attempt + 1, e)
            time.sleep(3)
    logger.error("DB init failed after 10 attempts.")


# Start DB init in background — doesn't block startup or healthcheck
threading.Thread(target=_init_db, daemon=True).start()
logger.info("App started. DB init running in background.")
