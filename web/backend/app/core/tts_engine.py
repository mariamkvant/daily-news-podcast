"""
TTS Engine — converts article text to MP3 audio.

Priority:
  1. ElevenLabs (if ELEVENLABS_API_KEY is set) — high quality, fast (~1-2s)
  2. gTTS (Google TTS) — free, decent quality (~3-5s)
"""
import logging
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .aggregator import Article

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
# Default voice: "Rachel" — clear, professional news anchor voice
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2")  # fastest model


@dataclass
class Segment:
    article_url: str
    audio_path: str
    duration_ms: int
    title: str = ""
    source_name: str = ""
    spoken_text: str = ""
    summary: str = ""


def _truncate(text: str, max_words: int = 40) -> str:
    """Truncate to ~40 words for fast TTS (~2s per segment instead of ~5s)."""
    words = text.split()
    if len(words) <= max_words:
        return text
    last = -1
    for i in range(max_words):
        if words[i].endswith((".", "!", "?")):
            last = i
    return " ".join(words[: last + 1] if last >= 0 else words[:max_words])


def _tts_elevenlabs(text: str, audio_path: Path) -> bool:
    """Generate audio using ElevenLabs API. Returns True on success."""
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        audio = client.generate(
            text=text,
            voice=ELEVENLABS_VOICE_ID,
            model=ELEVENLABS_MODEL,
        )
        with open(str(audio_path), "wb") as f:
            for chunk in audio:
                f.write(chunk)
        return True
    except Exception as e:
        logger.warning("ElevenLabs TTS failed: %s", e)
        return False


def _tts_gtts(text: str, audio_path: Path) -> bool:
    """Generate audio using gTTS with a 15s timeout. Returns True on success."""
    result = [False]
    error = [None]

    def _run():
        try:
            from gtts import gTTS
            gTTS(text=text, lang="en").save(str(audio_path))
            result[0] = True
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=15)

    if not result[0]:
        logger.warning("gTTS failed or timed out: %s", error[0])
        return False
    return True


def generate_segment(article: Article, audio_dir: Path) -> Segment | None:
    """Convert article to MP3. Uses ElevenLabs if available, falls back to gTTS."""
    full_text = article.title + ". " + _truncate(article.summary)
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"segment_{abs(hash(article.url))}.mp3"
    audio_path = audio_dir / filename

    # Try ElevenLabs first (better quality + faster)
    success = False
    if ELEVENLABS_API_KEY:
        success = _tts_elevenlabs(full_text, audio_path)
        if success:
            logger.debug("ElevenLabs TTS ok for %s", article.url)

    # Fall back to gTTS
    if not success:
        success = _tts_gtts(full_text, audio_path)
        if not success:
            logger.error("All TTS methods failed for %s", article.url)
            return None

    # Measure duration via ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        duration_ms = int(float(result.stdout.strip()) * 1000)
    except Exception as e:
        logger.warning("ffprobe failed: %s — estimating duration", e)
        duration_ms = len(full_text.split()) * 400

    return Segment(
        article_url=article.url,
        audio_path=str(audio_path),
        duration_ms=duration_ms,
        title=article.title,
        source_name=article.source_name,
        spoken_text=full_text,
        summary=article.summary,
    )
