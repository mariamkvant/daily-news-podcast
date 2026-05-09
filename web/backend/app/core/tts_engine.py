"""TTS Engine — converts article text to MP3 using gTTS via subprocess."""
import logging
import subprocess
import sys
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path

from .aggregator import Article

logger = logging.getLogger(__name__)


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
    words = text.split()
    if len(words) <= max_words:
        return text
    last = -1
    for i in range(max_words):
        if words[i].endswith((".", "!", "?")):
            last = i
    return " ".join(words[: last + 1] if last >= 0 else words[:max_words])


def generate_segment(article: Article, audio_dir: Path) -> Segment | None:
    full_text = article.title + ". " + _truncate(article.summary)
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"segment_{abs(hash(article.url))}.mp3"
    audio_path = audio_dir / filename

    # Run gTTS in a subprocess with a hard timeout
    # This guarantees the process is killed if it hangs
    script = f"""
import sys
from gtts import gTTS
gTTS(text={repr(full_text)}, lang='en').save({repr(str(audio_path))})
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            timeout=12,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("gTTS subprocess failed for %s: %s", article.url, result.stderr[:200])
            return None
    except subprocess.TimeoutExpired:
        logger.warning("gTTS timed out for %s", article.url)
        return None
    except Exception as e:
        logger.error("gTTS error for %s: %s", article.url, e)
        return None

    if not audio_path.exists():
        logger.error("gTTS produced no file for %s", article.url)
        return None

    # Measure duration via ffprobe
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        duration_ms = int(float(r.stdout.strip()) * 1000)
    except Exception:
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
