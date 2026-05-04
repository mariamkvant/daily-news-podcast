import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("=== main.py loading ===")
logger.info("PORT=%s", os.environ.get("PORT", "not set"))
logger.info("DATABASE_URL set=%s", bool(os.environ.get("DATABASE_URL")))
logger.info("REDIS_URL set=%s", bool(os.environ.get("REDIS_URL")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Daily News Podcast API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok"}


# Only load full app if DB is configured
if os.environ.get("DATABASE_URL"):
    logger.info("DATABASE_URL found, loading full app...")
    try:
        from .database import engine
        from . import models
        models.Base.metadata.create_all(bind=engine)
        logger.info("DB tables ready.")

        from .routes import auth, users, episodes
        app.include_router(auth.router)
        app.include_router(users.router)
        app.include_router(episodes.router)
        logger.info("All routes loaded.")
    except Exception as e:
        logger.error("Failed to load full app: %s", e, exc_info=True)
else:
    logger.warning("DATABASE_URL not set — running in minimal mode")

logger.info("=== App ready ===")
