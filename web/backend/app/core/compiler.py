import logging
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .tts_engine import Segment

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    date: date
    segments: list[Segment]
    total_duration_ms: int
    audio_path: str
    created_at: datetime
    summary: str = ""


def compile_episode(
    segments: list[Segment],
    episode_date: date,
    audio_dir: Path,
    max_duration_seconds: int = 600,
) -> Episode:
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    max_ms = max_duration_seconds * 1000

    # Select segments within duration budget (no intro — saves 1 TTS call)
    total_ms = 0
    selected: list[Segment] = []
    for seg in segments:
        if total_ms + seg.duration_ms > max_ms:
            break
        selected.append(seg)
        total_ms += seg.duration_ms

    # Concatenate with ffmpeg
    episode_path = audio_dir / f"episode_{episode_date.isoformat()}.mp3"
    if selected:
        try:
            _concat_mp3([s.audio_path for s in selected], str(episode_path))
        except Exception as e:
            logger.error("ffmpeg concat failed: %s — using first segment as episode", e)
            # Fallback: just use the first segment as the episode
            import shutil
            shutil.copy2(selected[0].audio_path, str(episode_path))

    # Build episode summary
    titles = [s.title for s in selected]
    summary = "Today's episode covers: " + "; ".join(titles[:5])
    if len(titles) > 5:
        summary += f" and {len(titles) - 5} more stories."

    return Episode(
        date=episode_date,
        segments=selected,
        total_duration_ms=total_ms,
        audio_path=str(episode_path),
        created_at=datetime.now(),
        summary=summary,
    )


def _concat_mp3(input_paths: list[str], output_path: str) -> None:
    """Concatenate MP3 files using ffmpeg concat demuxer."""
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in input_paths:
            f.write(f"file '{p}'\n")
        list_file = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_file, "-c", "copy", output_path],
            capture_output=True, timeout=120, check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg concat failed: %s", e.stderr.decode())
        raise
    finally:
        os.unlink(list_file)
