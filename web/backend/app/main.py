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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


def _init_db():
    """Run DB table creation in a background thread so startup is instant."""
    import time
    for attempt in range(10):
        try:
            from .database import engine
            from . import models
            models.Base.metadata.create_all(bind=engine)
            logger.info("DB tables ready (attempt %d).", attempt + 1)
            return
        except Exception as e:
            logger.warning("DB init attempt %d failed: %s", attempt + 1, e)
            time.sleep(3)
    logger.error("DB init failed after 10 attempts.")


# Start DB init in background — doesn't block startup or healthcheck
threading.Thread(target=_init_db, daemon=True).start()
logger.info("App started. DB init running in background.")
