# Daily News Podcast

A Python desktop application that automatically aggregates news from multiple RSS feeds, filters and selects the most relevant articles, converts them to audio using text-to-speech, and delivers a daily podcast of up to 10 minutes.

## Features

- **News Aggregation** — fetches articles from multiple RSS feed sources published within the last 24 hours.
- **Relevance Filtering** — scores articles using TF-IDF cosine similarity against your configured topics and keywords; selects up to 20 articles per episode.
- **Text-to-Speech** — converts each article to a ~30-second audio segment using gTTS (with pyttsx3 as an offline fallback).
- **Episode Compilation** — assembles segments into a single MP3 episode (max 10 minutes) with a brief date/count intro.
- **Daily Scheduling** — automatically regenerates the episode once per day at a user-configured time via APScheduler.
- **Playback Controls** — stop, replay, and skip controls backed by pygame.mixer.
- **Configuration UI** — tkinter interface for managing sources, topics, keywords, and schedule time.

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) installed and on `PATH` (required by pydub for audio concatenation)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd daily-news-podcast

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Install the package in editable mode
pip install -e .
```

## Running

```bash
python -m daily_news_podcast
```

Or, after installation:

```bash
daily-news-podcast
```

## Running Tests

```bash
pytest
```

## Project Structure

```
daily-news-podcast/
├── src/
│   └── daily_news_podcast/
│       ├── __init__.py
│       ├── __main__.py       # Entry point
│       ├── models.py         # Data models (dataclasses)
│       ├── aggregator.py     # RSS feed fetching
│       ├── filter.py         # Relevance scoring and selection
│       ├── tts_engine.py     # Text-to-speech conversion
│       ├── compiler.py       # Episode assembly
│       ├── scheduler.py      # Daily scheduling
│       ├── player.py         # Audio playback
│       ├── config_store.py   # Configuration persistence
│       ├── episode_store.py  # Episode metadata persistence
│       ├── pipeline.py       # Full pipeline orchestration
│       └── ui.py             # tkinter UI
├── tests/
│   ├── test_models.py
│   ├── test_config_store.py
│   ├── test_aggregator.py
│   ├── test_filter.py
│   ├── test_tts_engine.py
│   ├── test_compiler.py
│   ├── test_player.py
│   └── test_properties.py   # Hypothesis property-based tests
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Configuration

User configuration is stored at `~/.daily-news-podcast/config.json`. It is created automatically with defaults on first run. You can edit sources, topics, keywords, and the daily generation schedule through the application's configuration panel.

## License

MIT
