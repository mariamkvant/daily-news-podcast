# Player: streams episode audio and handles stop/replay/skip controls via pygame.

import threading
import time

import pygame

from .models import Episode, PlayerState


class Player:
    """Audio player for podcast episodes using pygame.mixer."""

    def __init__(self) -> None:
        self._episode: Episode | None = None
        self._current_segment_index: int = 0
        self._position_ms: int = 0
        self._is_playing: bool = False
        self._episode_ended: bool = False
        self._lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, episode: Episode) -> None:
        """Store episode and reset all playback state."""
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        with self._lock:
            self._episode = episode
            self._current_segment_index = 0
            self._position_ms = 0
            self._is_playing = False
            self._episode_ended = False

    def play(self) -> None:
        """Load the current segment and start playback from the saved position."""
        with self._lock:
            if self._episode is None or self._episode_ended:
                return
            segment = self._episode.segments[self._current_segment_index]
            pygame.mixer.music.load(segment.audio_path)
            pygame.mixer.music.play(start=self._position_ms / 1000.0)
            self._is_playing = True

        self._start_poll_thread()

    def stop(self) -> None:
        """Pause playback and save the current position."""
        with self._lock:
            if not self._is_playing:
                return
            pos = pygame.mixer.music.get_pos()
            if pos >= 0:
                self._position_ms += pos
            pygame.mixer.music.pause()
            self._is_playing = False

    def replay(self) -> None:
        """Reset position to 0 and replay the current segment."""
        with self._lock:
            if self._episode is None:
                return
            self._position_ms = 0
            segment = self._episode.segments[self._current_segment_index]
            pygame.mixer.music.load(segment.audio_path)
            pygame.mixer.music.play(start=0)
            self._is_playing = True

        self._start_poll_thread()

    def skip(self) -> None:
        """Skip to the next segment; set episode_ended if past the last segment."""
        with self._lock:
            if self._episode is None:
                return
            pygame.mixer.music.stop()
            self._is_playing = False
            self._position_ms = 0
            self._current_segment_index += 1
            if self._current_segment_index >= len(self._episode.segments):
                self._episode_ended = True
                return
            should_play = True

        if should_play:
            self.play()

    def jump_to(self, index: int) -> None:
        """Jump directly to a specific segment by index and start playing."""
        with self._lock:
            if self._episode is None:
                return
            if index < 0 or index >= len(self._episode.segments):
                return
            pygame.mixer.music.stop()
            self._current_segment_index = index
            self._position_ms = 0
            self._episode_ended = False
            should_play = True

        if should_play:
            self.play()

    def get_state(self) -> PlayerState:
        """Return a snapshot of the current player state."""
        with self._lock:
            total_segments = len(self._episode.segments) if self._episode else 0
            # Sum durations of all completed segments
            elapsed = 0
            if self._episode:
                for i in range(self._current_segment_index):
                    elapsed += self._episode.segments[i].duration_ms
            elapsed += self._position_ms
            return PlayerState(
                is_playing=self._is_playing,
                current_segment_index=self._current_segment_index,
                total_segments=total_segments,
                elapsed_episode_ms=elapsed,
                episode_ended=self._episode_ended,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_poll_thread(self) -> None:
        """Start a background daemon thread that tracks position and detects segment end."""
        thread = threading.Thread(target=self._poll_playback, daemon=True)
        self._poll_thread = thread
        thread.start()

    def _poll_playback(self) -> None:
        """Poll pygame.mixer every 200 ms; advance to next segment on natural end."""
        while True:
            time.sleep(0.2)
            with self._lock:
                if not self._is_playing:
                    return
                pos = pygame.mixer.music.get_pos()
                if pos == -1:
                    # Natural end of current segment — advance
                    if self._episode is None:
                        return
                    self._position_ms = 0
                    self._current_segment_index += 1
                    if self._current_segment_index >= len(self._episode.segments):
                        self._episode_ended = True
                        self._is_playing = False
                        return
                    # Load and play the next segment
                    segment = self._episode.segments[self._current_segment_index]
                    pygame.mixer.music.load(segment.audio_path)
                    pygame.mixer.music.play(start=0)
                else:
                    self._position_ms = pos
