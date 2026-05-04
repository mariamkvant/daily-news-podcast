import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — DATABASE_URL set: %s", bool(os.environ.get("DATABASE_URL")))
    from .database import engine
    from . import models
    models.Base.metadata.create_all(bind=engine)
    Path("/tmp/audio").mkdir(parents=True, exist_ok=True)
    logger.info("Startup complete.")
    yield


app = FastAPI(title="Daily News Podcast API", version="1.0.0", lifespan=lifespan)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
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
    app.mount("/audio", StaticFiles(directory="/tmp/audio"), name="audio")


@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    """Debug endpoint — check DB connectivity and table existence."""
    try:
        from .database import engine
        from sqlalchemy import text, inspect
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return {"db": "connected", "tables": tables}
    except Exception as e:
        return {"db": "error", "detail": str(e)}
