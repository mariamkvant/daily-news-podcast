import os
import secrets
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..schemas import RegisterRequest, LoginRequest, TokenResponse
from ..core.catalog import DEFAULT_TOPICS, DEFAULT_ENABLED_SOURCES
from ..email import send_verification_email, send_welcome_email, send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory rate limiting (resets on restart — good enough for Railway)
_login_attempts: dict[str, list[datetime]] = {}
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 300  # 5 minutes


def _check_rate_limit(key: str) -> None:
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=_WINDOW_SECONDS)
    attempts = [t for t in _login_attempts.get(key, []) if t > window_start]
    _login_attempts[key] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in 5 minutes.")
    _login_attempts[key] = attempts + [now]


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(f"register:{request.client.host}")
    try:
        if len(body.password) > 72:
            raise HTTPException(status_code=400, detail="Password must be 72 characters or fewer")
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

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
            verify_token_expires=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
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
    user = db.query(models.User).filter(models.User.verify_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    # Check expiry if set
    if user.verify_token_expires and datetime.utcnow() > user.verify_token_expires:
        raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
    user.is_verified = True
    user.verify_token = None
    user.verify_token_expires = None
    db.commit()
    send_welcome_email(user.email, user.name)
    logger.info("Email verified for user: %s", user.email)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(f"login:{request.client.host}")
    try:
        user = db.query(models.User).filter(models.User.email == body.email).first()
        if not user or not verify_password(body.password, user.hashed_pw):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_verified:
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
def resend_verification(email: str, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(f"resend:{request.client.host}")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or user.is_verified:
        return {"detail": "If that email exists and is unverified, we've sent a new link."}
    token = secrets.token_urlsafe(32)
    user.verify_token = token
    user.verify_token_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    send_verification_email(user.email, user.name, token)
    return {"detail": "Verification email sent."}


@router.post("/forgot-password")
def forgot_password(email: str, request: Request, db: Session = Depends(get_db)):
    """Send a password reset email."""
    _check_rate_limit(f"forgot:{request.client.host}")
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        send_password_reset_email(user.email, user.name, token)
    # Always return same response to avoid email enumeration
    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    """Reset password using token from email."""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(new_password) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 characters or fewer")

    user = db.query(models.User).filter(models.User.reset_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if user.reset_token_expires and datetime.utcnow() > user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    user.hashed_pw = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    logger.info("Password reset for user: %s", user.email)
    return {"detail": "Password reset successfully. You can now log in."}


@router.delete("/me")
def delete_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete the current user's account and all their data."""
    db.delete(current_user)
    db.commit()
    logger.info("Account deleted: %s", current_user.email)
    return {"detail": "Account deleted."}
