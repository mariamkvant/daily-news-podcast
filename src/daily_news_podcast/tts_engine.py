# TTSEngine: converts article text to MP3 audio segments via gTTS / pyttsx3.
import logging
import os
from pathlib import Path

from daily_news_podcast.models import Article, Segment

logger = logging.getLogger(__name__)


def _configure_pydub_ffmpeg() -> None:
    """Point pydub at the ffmpeg/ffprobe binaries, searching winget install location if needed."""
    import pydub.utils as pydub_utils
    from pydub import AudioSegment

    winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    ffmpeg_bin: Path | None = None
    for candidate in winget_base.glob("Gyan.FFmpeg*/*/bin"):
        if (candidate / "ffmpeg.exe").exists():
            ffmpeg_bin = candidate
            break

    if ffmpeg_bin:
        ffmpeg_path = str(ffmpeg_bin / "ffmpeg.exe")
        ffprobe_path = str(ffmpeg_bin / "ffprobe.exe")
        # Set on the class directly (used by from_file/from_mp3)
        AudioSegment.converter = ffmpeg_path
        # Patch the utils lookup functions as well
        pydub_utils.get_encoder_name = lambda: ffmpeg_path
        pydub_utils.get_prober_name = lambda: ffprobe_path
        logger.info("Configured pydub to use ffmpeg at: %s", ffmpeg_path)
    else:
        logger.warning("ffmpeg not found in winget packages; pydub will rely on PATH.")


_configure_pydub_ffmpeg()


class TTSEngine:
    def _truncate_to_sentence_boundary(self, text: str, max_words: int = 75) -> str:
        """
        Truncate text to fit within max_words, ending at a sentence boundary (., !, ?).
        If no sentence boundary found within limit, truncate at word boundary.
        """
        words = text.split()
        if len(words) <= max_words:
            return text

        # Search for the last sentence boundary within the first max_words words
        last_boundary = -1
        for i in range(max_words):
            if words[i].endswith(('.', '!', '?')):
                last_boundary = i

        if last_boundary >= 0:
            return ' '.join(words[:last_boundary + 1])

        # No sentence boundary found — fall back to word boundary
        return ' '.join(words[:max_words])

    def generate_segment(self, article: Article, audio_dir: Path) -> 'Segment | None':
        """
        Convert article title + summary to an MP3 audio segment.
        Returns None and logs on failure.
        """
        full_text = article.title + ". " + self._truncate_to_sentence_boundary(article.summary)

        audio_dir.mkdir(parents=True, exist_ok=True)

        filename = f"segment_{abs(hash(article.url))}.mp3"
        audio_path = audio_dir / filename

        # Try gTTS first
        tts_succeeded = False
        try:
            from gtts import gTTS
            gTTS(text=full_text, lang='en').save(str(audio_path))
            tts_succeeded = True
        except Exception as e:
            logger.warning("gTTS failed for %s: %s. Falling back to pyttsx3.", article.url, e)

        # Fall back to pyttsx3 if gTTS failed
        if not tts_succeeded:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.save_to_file(full_text, str(audio_path))
                engine.runAndWait()
                tts_succeeded = True
            except Exception as e:
                logger.error("pyttsx3 also failed for %s: %s", article.url, e)
                return None

        # Measure duration via pydub
        try:
            from pydub import AudioSegment
            duration_ms = int(AudioSegment.from_mp3(str(audio_path)).duration_seconds * 1000)
        except Exception as e:
            logger.error("pydub failed to read audio for %s: %s", article.url, e)
            return None

        return Segment(
            article_url=article.url,
            audio_path=str(audio_path),
            duration_ms=duration_ms,
            title=article.title,
            source_name=article.source_name,
            spoken_text=full_text,
            summary=article.summary,
        )
