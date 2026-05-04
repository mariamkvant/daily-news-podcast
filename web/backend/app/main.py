import os
import sys
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
    logger.info("Starting up Daily News Podcast API...")
    logger.info("DATABASE_URL set: %s", bool(os.environ.get("DATABASE_URL")))
    logger.info("REDIS_URL set: %s", bool(os.environ.get("REDIS_URL")))
    logger.info("PORT: %s", os.environ.get("PORT", "8000"))
    try:
        from .database import engine
        from . import models
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error("Database init failed: %s", e)
        raise
    Path("/tmp/audio").mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Shutting down.")


app = FastAPI(title="Daily News Podcast API", version="1.0.0", lifespan=lifespan)

# CORS
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from .routes import auth, users, episodes
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(episodes.router)

# Serve local audio files in dev
if not os.environ.get("AWS_BUCKET_NAME"):
    app.mount("/audio", StaticFiles(directory="/tmp/audio"), name="audio")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"status": "ok", "service": "Daily News Podcast API"}
