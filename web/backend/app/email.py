"""Email service using Resend."""
import os
import logging

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Daily News Podcast <noreply@dailynewspodcast.app>")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


def send_verification_email(to_email: str, name: str, token: str) -> bool:
    """Send email verification link. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping verification email.")
        return False

    verify_url = f"{FRONTEND_URL}/verify?token={token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff; padding: 40px;">
      <div style="max-width: 480px; margin: 0 auto; background: #111; border-radius: 16px; padding: 40px; border: 1px solid #222;">
        <h1 style="color: #4f6ef7; margin-bottom: 8px;">🎙 Daily News Podcast</h1>
        <h2 style="color: #fff; font-weight: 600;">Verify your email</h2>
        <p style="color: #aaa; line-height: 1.6;">
          Hi {name}, thanks for signing up! Click the button below to verify your email address and start listening.
        </p>
        <a href="{verify_url}"
           style="display: inline-block; background: #4f6ef7; color: #fff; padding: 14px 28px;
                  border-radius: 10px; text-decoration: none; font-weight: 600; margin: 24px 0;">
          Verify my email
        </a>
        <p style="color: #555; font-size: 13px;">
          Or copy this link: <a href="{verify_url}" style="color: #4f6ef7;">{verify_url}</a>
        </p>
        <p style="color: #555; font-size: 12px; margin-top: 32px;">
          This link expires in 24 hours. If you didn't sign up, ignore this email.
        </p>
      </div>
    </body>
    </html>
    """

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to_email,
            "subject": "Verify your Daily News Podcast account",
            "html": html,
        })
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)
        return False


def send_welcome_email(to_email: str, name: str) -> None:
    """Send welcome email after verification."""
    if not RESEND_API_KEY:
        return

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff; padding: 40px;">
      <div style="max-width: 480px; margin: 0 auto; background: #111; border-radius: 16px; padding: 40px; border: 1px solid #222;">
        <h1 style="color: #4f6ef7;">🎙 Welcome to Daily News Podcast!</h1>
        <p style="color: #aaa; line-height: 1.6;">
          Hi {name}! Your account is verified and your first personalised episode is being generated right now.
        </p>
        <p style="color: #aaa; line-height: 1.6;">
          Every morning we'll fetch the most important stories matching your interests and turn them into an audio podcast — ready when you wake up.
        </p>
        <a href="{FRONTEND_URL}/home"
           style="display: inline-block; background: #4f6ef7; color: #fff; padding: 14px 28px;
                  border-radius: 10px; text-decoration: none; font-weight: 600; margin: 24px 0;">
          Start listening →
        </a>
      </div>
    </body>
    </html>
    """

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to_email,
            "subject": "Welcome to Daily News Podcast 🎙",
            "html": html,
        })
    except Exception as e:
        logger.error("Failed to send welcome email: %s", e)


def send_password_reset_email(to_email: str, name: str, token: str) -> None:
    """Send password reset link."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping password reset email.")
        return

    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff; padding: 40px;">
      <div style="max-width: 480px; margin: 0 auto; background: #111; border-radius: 16px; padding: 40px; border: 1px solid #222;">
        <h1 style="color: #4f6ef7; margin-bottom: 8px;">🎙 Daily News Podcast</h1>
        <h2 style="color: #fff; font-weight: 600;">Reset your password</h2>
        <p style="color: #aaa; line-height: 1.6;">
          Hi {name}, we received a request to reset your password. Click the button below to set a new one.
        </p>
        <a href="{reset_url}"
           style="display: inline-block; background: #4f6ef7; color: #fff; padding: 14px 28px;
                  border-radius: 10px; text-decoration: none; font-weight: 600; margin: 24px 0;">
          Reset password
        </a>
        <p style="color: #555; font-size: 12px; margin-top: 32px;">
          This link expires in 1 hour. If you didn't request a reset, ignore this email.
        </p>
      </div>
    </body>
    </html>
    """

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to_email,
            "subject": "Reset your Daily News Podcast password",
            "html": html,
        })
        logger.info("Password reset email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", to_email, e)
