# Tests for Player state machine (stop/resume/replay/skip transitions)
import threading
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from daily_news_podcast.models import Episode, PlayerState, Segment
from daily_news_podcast.player import Player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_segment(audio_path: str, duration_ms: int = 10_000) -> Segment:
    return Segment(article_url="http://example.com", audio_path=audio_path, duration_ms=duration_ms)


def make_episode(num_segments: int = 3, duration_ms: int = 10_000) -> Episode:
    segments = [make_segment(f"/audio/seg{i}.mp3", duration_ms) for i in range(num_segments)]
    return Episode(
        date=date.today(),
        segments=segments,
        total_duration_ms=num_segments * duration_ms,
        audio_path="/audio/episode.mp3",
        created_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_pygame():
    """Patch pygame.mixer entirely so no audio hardware is required."""
    with patch("daily_news_podcast.player.pygame") as mock_pg:
        mock_pg.mixer.get_init.return_value = True
        mock_pg.mixer.music = MagicMock()
        # Default: get_pos returns a positive value (playback in progress)
        mock_pg.mixer.music.get_pos.return_value = 5000
        yield mock_pg


@pytest.fixture()
def player(mock_pygame):
    return Player()


# ---------------------------------------------------------------------------
# load() tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_resets_segment_index(self, player):
        episode = make_episode(3)
        player.load(episode)
        assert player._current_segment_index == 0

    def test_load_resets_position_ms(self, player):
        episode = make_episode(3)
        player.load(episode)
        assert player._position_ms == 0

    def test_load_sets_is_playing_false(self, player):
        episode = make_episode(3)
        player.load(episode)
        assert player._is_playing is False

    def test_load_sets_episode_ended_false(self, player):
        episode = make_episode(3)
        player.load(episode)
        assert player._episode_ended is False

    def test_load_stores_episode(self, player):
        episode = make_episode(3)
        player.load(episode)
        assert player._episode is episode

    def test_load_initializes_pygame_mixer_when_not_initialized(self, mock_pygame):
        mock_pygame.mixer.get_init.return_value = False
        p = Player()
        episode = make_episode(1)
        p.load(episode)
        mock_pygame.mixer.init.assert_called_once()

    def test_load_does_not_reinitialize_mixer_when_already_initialized(self, mock_pygame, player):
        episode = make_episode(1)
        player.load(episode)
        mock_pygame.mixer.init.assert_not_called()


# ---------------------------------------------------------------------------
# stop() tests
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_sets_is_playing_false(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._is_playing = True
        mock_pygame.mixer.music.get_pos.return_value = 3000

        player.stop()

        assert player._is_playing is False

    def test_stop_calls_pause(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._is_playing = True
        mock_pygame.mixer.music.get_pos.return_value = 3000

        player.stop()

        mock_pygame.mixer.music.pause.assert_called_once()

    def test_stop_saves_position_from_get_pos(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._is_playing = True
        player._position_ms = 0
        mock_pygame.mixer.music.get_pos.return_value = 4500

        player.stop()

        # position_ms should be updated with the value from get_pos
        assert player._position_ms == 4500

    def test_stop_does_nothing_when_not_playing(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._is_playing = False

        player.stop()

        mock_pygame.mixer.music.pause.assert_not_called()


# ---------------------------------------------------------------------------
# replay() tests
# ---------------------------------------------------------------------------

class TestReplay:
    def test_replay_resets_position_to_zero(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._position_ms = 7000

        # Prevent the poll thread from interfering
        with patch.object(player, "_start_poll_thread"):
            player.replay()

        assert player._position_ms == 0

    def test_replay_sets_is_playing_true(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)

        with patch.object(player, "_start_poll_thread"):
            player.replay()

        assert player._is_playing is True

    def test_replay_calls_music_play_from_start(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)

        with patch.object(player, "_start_poll_thread"):
            player.replay()

        mock_pygame.mixer.music.play.assert_called_with(start=0)

    def test_replay_loads_current_segment(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)

        with patch.object(player, "_start_poll_thread"):
            player.replay()

        mock_pygame.mixer.music.load.assert_called_with(episode.segments[0].audio_path)


# ---------------------------------------------------------------------------
# skip() tests
# ---------------------------------------------------------------------------

class TestSkip:
    def test_skip_on_last_segment_sets_episode_ended(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._current_segment_index = 1  # already on last segment

        player.skip()

        assert player._episode_ended is True

    def test_skip_on_last_segment_sets_is_playing_false(self, player, mock_pygame):
        episode = make_episode(2)
        player.load(episode)
        player._current_segment_index = 1

        player.skip()

        assert player._is_playing is False

    def test_skip_on_non_last_segment_advances_index(self, player, mock_pygame):
        episode = make_episode(3)
        player.load(episode)
        player._current_segment_index = 0

        with patch.object(player, "play"):
            player.skip()

        assert player._current_segment_index == 1

    def test_skip_on_non_last_segment_calls_play(self, player, mock_pygame):
        episode = make_episode(3)
        player.load(episode)
        player._current_segment_index = 0

        with patch.object(player, "play") as mock_play:
            player.skip()

        mock_play.assert_called_once()

    def test_skip_on_non_last_segment_does_not_set_episode_ended(self, player, mock_pygame):
        episode = make_episode(3)
        player.load(episode)
        player._current_segment_index = 0

        with patch.object(player, "play"):
            player.skip()

        assert player._episode_ended is False

    def test_skip_single_segment_episode_ends(self, player, mock_pygame):
        episode = make_episode(1)
        player.load(episode)

        player.skip()

        assert player._episode_ended is True
        assert player._is_playing is False


# ---------------------------------------------------------------------------
# get_state() tests
# ---------------------------------------------------------------------------

class TestGetState:
    def test_get_state_returns_correct_segment_index(self, player):
        episode = make_episode(4)
        player.load(episode)
        player._current_segment_index = 2

        state = player.get_state()

        assert state.current_segment_index == 2

    def test_get_state_returns_correct_total_segments(self, player):
        episode = make_episode(5)
        player.load(episode)

        state = player.get_state()

        assert state.total_segments == 5

    def test_get_state_elapsed_episode_ms_on_first_segment(self, player):
        episode = make_episode(3, duration_ms=10_000)
        player.load(episode)
        player._position_ms = 3000

        state = player.get_state()

        # No completed segments, just current position
        assert state.elapsed_episode_ms == 3000

    def test_get_state_elapsed_episode_ms_sums_completed_segments(self, player):
        episode = make_episode(4, duration_ms=10_000)
        player.load(episode)
        player._current_segment_index = 2  # segments 0 and 1 are done
        player._position_ms = 4000

        state = player.get_state()

        # 2 completed segments × 10,000 ms + 4,000 ms current position
        assert state.elapsed_episode_ms == 24_000

    def test_get_state_reflects_is_playing(self, player):
        episode = make_episode(2)
        player.load(episode)
        player._is_playing = True

        state = player.get_state()

        assert state.is_playing is True

    def test_get_state_reflects_episode_ended(self, player):
        episode = make_episode(2)
        player.load(episode)
        player._episode_ended = True

        state = player.get_state()

        assert state.episode_ended is True

    def test_get_state_returns_player_state_instance(self, player):
        episode = make_episode(2)
        player.load(episode)

        state = player.get_state()

        assert isinstance(state, PlayerState)
