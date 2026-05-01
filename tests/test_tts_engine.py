# Tests for TTSEngine (truncation, segment generation, fallback, fault tolerance)
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from daily_news_podcast.models import Article
from daily_news_podcast.tts_engine import TTSEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article(title="Test Title", summary="Test summary.", url="http://example.com/1"):
    return Article(
        title=title,
        summary=summary,
        url=url,
        source_name="Test Source",
        published_at=datetime(2024, 1, 1, 12, 0, 0),
    )


# ---------------------------------------------------------------------------
# _truncate_to_sentence_boundary tests
# ---------------------------------------------------------------------------

class TestTruncateToSentenceBoundary:
    def setup_method(self):
        self.engine = TTSEngine()

    def test_text_shorter_than_limit_is_unchanged(self):
        """Text with fewer words than max_words is returned as-is."""
        text = "This is a short sentence."
        result = self.engine._truncate_to_sentence_boundary(text, max_words=75)
        assert result == text

    def test_text_exactly_max_words_is_unchanged(self):
        """Text with exactly max_words words is returned as-is."""
        words = ["word"] * 74 + ["end."]  # 75 words, last ends with '.'
        text = " ".join(words)
        result = self.engine._truncate_to_sentence_boundary(text, max_words=75)
        assert result == text

    def test_truncates_at_sentence_boundary_within_limit(self):
        """Text longer than limit is truncated at the last sentence boundary within max_words."""
        # Build text: 10 words ending with '.', then 70 more words
        first_sentence = "First sentence ends here now with exactly ten words."  # 10 words
        extra_words = " ".join(["extra"] * 70)
        text = first_sentence + " " + extra_words
        result = self.engine._truncate_to_sentence_boundary(text, max_words=75)
        # Should end at the sentence boundary word
        assert result.endswith(".")
        assert len(result.split()) <= 75

    def test_truncates_at_last_sentence_boundary_within_limit(self):
        """When multiple sentence boundaries exist within limit, uses the last one."""
        # Two sentences within the first 75 words, then overflow
        sentence1 = "First sentence. "   # 2 words
        sentence2 = "Second sentence. "  # 2 words
        # Fill up to just under 75 words with a third sentence boundary
        filler = " ".join(["word"] * 10) + ". "  # 11 words
        overflow = " ".join(["overflow"] * 80)
        text = sentence1 + sentence2 + filler + overflow
        result = self.engine._truncate_to_sentence_boundary(text, max_words=75)
        assert result.endswith(".")
        assert len(result.split()) <= 75

    def test_falls_back_to_word_boundary_when_no_sentence_boundary(self):
        """When no sentence boundary exists within max_words, truncates at word boundary."""
        # 100 words, none ending with sentence punctuation within first 75
        words = ["word"] * 99 + ["end"]
        text = " ".join(words)
        result = self.engine._truncate_to_sentence_boundary(text, max_words=75)
        assert len(result.split()) == 75
        assert not result.endswith(".")
        assert not result.endswith("!")
        assert not result.endswith("?")


# ---------------------------------------------------------------------------
# generate_segment tests
# ---------------------------------------------------------------------------

class TestGenerateSegment:
    def setup_method(self):
        self.engine = TTSEngine()

    def test_falls_back_to_pyttsx3_when_gtts_raises(self, mocker, tmp_path):
        """When gTTS raises, pyttsx3 is used and a Segment is returned."""
        # Mock gTTS to raise
        mock_gtts_cls = mocker.patch("gtts.gTTS")
        mock_gtts_cls.side_effect = Exception("network error")

        # Mock pyttsx3
        mock_pyttsx3 = mocker.patch("pyttsx3.init")
        mock_engine = MagicMock()
        mock_pyttsx3.return_value = mock_engine

        # Mock pydub AudioSegment
        mock_audio_segment_cls = mocker.patch("pydub.AudioSegment.from_mp3")
        mock_audio = MagicMock()
        mock_audio.duration_seconds = 15.5
        mock_audio_segment_cls.return_value = mock_audio

        article = make_article()
        segment = self.engine.generate_segment(article, tmp_path)

        assert segment is not None
        assert segment.article_url == article.url
        assert segment.duration_ms == 15500
        mock_engine.save_to_file.assert_called_once()
        mock_engine.runAndWait.assert_called_once()

    def test_returns_none_when_both_tts_engines_fail(self, mocker, tmp_path):
        """When both gTTS and pyttsx3 raise, generate_segment returns None."""
        mock_gtts_cls = mocker.patch("gtts.gTTS")
        mock_gtts_cls.side_effect = Exception("network error")

        mock_pyttsx3 = mocker.patch("pyttsx3.init")
        mock_pyttsx3.side_effect = Exception("pyttsx3 init failed")

        article = make_article()
        segment = self.engine.generate_segment(article, tmp_path)

        assert segment is None

    def test_returns_none_when_pydub_fails(self, mocker, tmp_path):
        """When pydub fails to read the audio file, generate_segment returns None."""
        # gTTS succeeds (no-op save)
        mock_gtts_cls = mocker.patch("gtts.gTTS")
        mock_gtts_instance = MagicMock()
        mock_gtts_cls.return_value = mock_gtts_instance

        # pydub raises
        mocker.patch("pydub.AudioSegment.from_mp3", side_effect=Exception("pydub error"))

        article = make_article()
        segment = self.engine.generate_segment(article, tmp_path)

        assert segment is None

    def test_gtts_success_returns_segment(self, mocker, tmp_path):
        """When gTTS succeeds, a Segment with correct fields is returned."""
        mock_gtts_cls = mocker.patch("gtts.gTTS")
        mock_gtts_instance = MagicMock()
        mock_gtts_cls.return_value = mock_gtts_instance

        mock_audio = MagicMock()
        mock_audio.duration_seconds = 20.0
        mocker.patch("pydub.AudioSegment.from_mp3", return_value=mock_audio)

        article = make_article(url="http://example.com/article-42")
        segment = self.engine.generate_segment(article, tmp_path)

        assert segment is not None
        assert segment.article_url == article.url
        assert segment.duration_ms == 20000
        assert segment.audio_path.endswith(".mp3")
        assert f"segment_{abs(hash(article.url))}" in segment.audio_path

    def test_audio_dir_is_created_if_missing(self, mocker, tmp_path):
        """generate_segment creates audio_dir if it does not exist."""
        mock_gtts_cls = mocker.patch("gtts.gTTS")
        mock_gtts_instance = MagicMock()
        mock_gtts_cls.return_value = mock_gtts_instance

        mock_audio = MagicMock()
        mock_audio.duration_seconds = 5.0
        mocker.patch("pydub.AudioSegment.from_mp3", return_value=mock_audio)

        new_dir = tmp_path / "nested" / "audio"
        assert not new_dir.exists()

        article = make_article()
        self.engine.generate_segment(article, new_dir)

        assert new_dir.exists()
