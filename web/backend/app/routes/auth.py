from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from ..database import get_db
from .. import models
from ..auth import hash_password, verify_password, create_access_token
from ..schemas import RegisterRequest, LoginRequest, TokenResponse
from ..core.catalog import DEFAULT_TOPICS, DEFAULT_ENABLED_SOURCES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        if db.query(models.User).filter(models.User.email == body.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = models.User(
            email=body.email,
            name=body.name,
            hashed_pw=hash_password(body.password),
            topics=list(DEFAULT_TOPICS),
            keywords=[],
            enabled_sources=list(DEFAULT_ENABLED_SOURCES),
            max_duration_sec=600,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Registered new user: %s", body.email)
        return TokenResponse(access_token=create_access_token(user.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == body.email).first()
        if not user or not verify_password(body.password, user.hashed_pw):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return TokenResponse(access_token=create_access_token(user.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
