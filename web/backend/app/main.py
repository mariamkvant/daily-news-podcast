import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine
from . import models
from .routes import auth, users, episodes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    models.Base.metadata.create_all(bind=engine)
    # Ensure local audio dir exists (dev fallback)
    Path("/tmp/audio").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Daily News Podcast API", version="1.0.0", lifespan=lifespan)

# CORS — allow the frontend origin
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(episodes.router)

# Serve local audio files in dev (when no S3 configured)
if not os.environ.get("AWS_BUCKET_NAME"):
    app.mount("/audio", StaticFiles(directory="/tmp/audio"), name="audio")


@app.get("/health")
def health():
    return {"status": "ok"}
