# Compiler: assembles audio segments into a single daily episode MP3.
import logging
from datetime import date, datetime
from pathlib import Path

from daily_news_podcast.models import Article, Episode, Segment
from daily_news_podcast.tts_engine import _configure_pydub_ffmpeg

logger = logging.getLogger(__name__)

_configure_pydub_ffmpeg()


class Compiler:
    def compile(
        self,
        segments: list[Segment],
        date: date,
        tts_engine,
        audio_dir: Path,
        max_duration_seconds: int = 600,
    ) -> Episode:
        """
        Assemble segments into an Episode.
        Prepend intro segment.
        Enforce max_duration_seconds total duration limit.
        """
        audio_dir = Path(audio_dir)
        audio_dir.mkdir(parents=True, exist_ok=True)

        max_duration_ms = max_duration_seconds * 1000

        # Generate intro segment
        intro_text = f"Daily News Podcast for {date}. {len(segments)} stories today."
        intro_article = Article(
            title=intro_text,
            summary="",
            url="intro",
            source_name="intro",
            published_at=datetime.now(),
        )
        intro_seg: Segment | None = None
        try:
            intro_seg = tts_engine.generate_segment(intro_article, audio_dir)
        except Exception as e:
            logger.warning("Intro generation failed: %s. Using silent intro.", e)
            intro_seg = None

        total_duration_ms = 0
        if intro_seg is not None:
            total_duration_ms += intro_seg.duration_ms

        # Select segments within the duration budget
        selected_segments: list[Segment] = []
        for seg in segments:
            if total_duration_ms + seg.duration_ms > max_duration_ms:
                break
            selected_segments.append(seg)
            total_duration_ms += seg.duration_ms

        # Concatenate audio files using pydub
        episode_audio_path = audio_dir / f"episode_{date.isoformat()}.mp3"
        try:
            from pydub import AudioSegment as PydubSegment

            combined = PydubSegment.empty()
            segs_to_combine = []
            if intro_seg is not None:
                segs_to_combine.append(intro_seg)
            segs_to_combine.extend(selected_segments)

            for seg in segs_to_combine:
                combined += PydubSegment.from_mp3(seg.audio_path)

            combined.export(str(episode_audio_path), format="mp3")
        except Exception as e:
            logger.error("Audio concatenation failed: %s", e)
            # Still return the episode metadata even if audio export fails

        return Episode(
            date=date,
            segments=selected_segments,
            total_duration_ms=total_duration_ms,
            audio_path=str(episode_audio_path),
            created_at=datetime.now(),
        )
