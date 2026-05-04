import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import hash_password, verify_password, create_access_token
from ..schemas import RegisterRequest, LoginRequest, TokenResponse
from ..core.catalog import DEFAULT_TOPICS, DEFAULT_ENABLED_SOURCES
from ..email import send_verification_email, send_welcome_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        if len(body.password) > 72:
            raise HTTPException(status_code=400, detail="Password must be 72 characters or fewer")
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        # Ensure tables exist
        from ..database import engine
        from .. import models as m
        m.Base.metadata.create_all(bind=engine)

        if db.query(models.User).filter(models.User.email == body.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        verify_token = secrets.token_urlsafe(32)

        user = models.User(
            email=body.email,
            name=body.name,
            hashed_pw=hash_password(body.password),
            topics=list(DEFAULT_TOPICS),
            keywords=[],
            enabled_sources=list(DEFAULT_ENABLED_SOURCES),
            max_duration_sec=600,
            is_verified=False,
            verify_token=verify_token,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Send verification email (non-blocking — failure doesn't break registration)
        send_verification_email(body.email, body.name, verify_token)

        logger.info("Registered new user: %s", body.email)
        return TokenResponse(access_token=create_access_token(user.id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify email address via token from email link."""
    user = db.query(models.User).filter(models.User.verify_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.is_verified = True
    user.verify_token = None
    db.commit()

    send_welcome_email(user.email, user.name)
    logger.info("Email verified for user: %s", user.email)

    # Return a token so the frontend can log them in directly
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == body.email).first()
        if not user or not verify_password(body.password, user.hashed_pw):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_verified:
            # If RESEND is not configured, auto-verify
            import os
            if not os.environ.get("RESEND_API_KEY"):
                user.is_verified = True
                db.commit()
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Please verify your email before logging in. Check your inbox."
                )
        return TokenResponse(access_token=create_access_token(user.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/resend-verification")
def resend_verification(email: str, db: Session = Depends(get_db)):
    """Resend verification email."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or user.is_verified:
        # Don't reveal whether email exists
        return {"detail": "If that email exists and is unverified, we've sent a new link."}

    token = secrets.token_urlsafe(32)
    user.verify_token = token
    db.commit()
    send_verification_email(user.email, user.name, token)
    return {"detail": "Verification email sent."}
