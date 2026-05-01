# UI: tkinter configuration panel and playback controls.
"""
ui.py — tkinter UI for Daily News Podcast.

Contains:
  - ConfigPanel  : LabelFrames for sources, filter settings, and schedule.
  - PlaybackPanel: LabelFrame with status, progress, and playback buttons.
  - App          : Root Tk window that wires everything together.
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from .models import AppConfig, FilterConfig, SchedulerConfig, Source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: modal dialog for adding / editing a Source
# ---------------------------------------------------------------------------

class _SourceDialog(tk.Toplevel):
    """Modal dialog for entering or editing a Source (name + URL)."""

    def __init__(self, parent: tk.Widget, title: str = "Source", source: Source | None = None) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()  # make modal

        self.result: Source | None = None

        # --- Name ---
        ttk.Label(self, text="Name:").grid(row=0, column=0, padx=10, pady=(12, 4), sticky="w")
        self._name_var = tk.StringVar(value=source.name if source else "")
        self._name_entry = ttk.Entry(self, textvariable=self._name_var, width=40)
        self._name_entry.grid(row=0, column=1, padx=(0, 10), pady=(12, 4))

        # --- URL ---
        ttk.Label(self, text="URL:").grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self._url_var = tk.StringVar(value=source.url if source else "")
        self._url_entry = ttk.Entry(self, textvariable=self._url_var, width=40)
        self._url_entry.grid(row=1, column=1, padx=(0, 10), pady=4)

        # --- Buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(8, 12))
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self._name_entry.focus_set()
        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self.destroy())

        # Centre over parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

        self.wait_window(self)

    def _on_ok(self) -> None:
        name = self._name_var.get().strip()
        url = self._url_var.get().strip()
        if not name or not url:
            messagebox.showwarning("Validation", "Both Name and URL are required.", parent=self)
            return
        self.result = Source(url=url, name=name)
        self.destroy()


# ---------------------------------------------------------------------------
# ConfigPanel
# ---------------------------------------------------------------------------

class ConfigPanel(ttk.Frame):
    """Left panel: news sources, filter settings, schedule, and save button."""

    def __init__(self, parent: tk.Widget, config_store, on_config_saved=None) -> None:
        super().__init__(parent, padding=8)
        self._config_store = config_store
        self._on_config_saved = on_config_saved

        # Load current config
        self._config: AppConfig = config_store.load()

        self._build_sources_frame()
        self._build_filter_frame()
        self._build_schedule_frame()
        self._build_save_row()

        # Populate widgets from loaded config
        self._populate_from_config()

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _build_sources_frame(self) -> None:
        sources_lf = ttk.LabelFrame(self, text="News Sources", padding=6)
        sources_lf.pack(fill="both", expand=False, pady=(0, 8))

        # Listbox + scrollbar
        list_frame = ttk.Frame(sources_lf)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._sources_listbox = tk.Listbox(
            list_frame,
            height=6,
            yscrollcommand=scrollbar.set,
            selectmode="single",
            activestyle="dotbox",
        )
        scrollbar.config(command=self._sources_listbox.yview)
        self._sources_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        btn_frame = ttk.Frame(sources_lf)
        btn_frame.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frame, text="Add Source", command=self._add_source).pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="Edit Source", command=self._edit_source).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Remove Source", command=self._remove_source).pack(side="left", padx=4)

        # Onboarding label (shown when list is empty)
        self._onboarding_label = ttk.Label(
            sources_lf,
            text="ℹ No sources configured — add one or save to restore defaults",
            foreground="gray",
        )
        self._onboarding_label.pack(pady=(4, 0))

    def _build_filter_frame(self) -> None:
        filter_lf = ttk.LabelFrame(self, text="Filter Settings", padding=6)
        filter_lf.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(filter_lf, text="Topics (one per line):").pack(anchor="w")
        self._topics_text = tk.Text(filter_lf, height=4, width=40, wrap="word")
        self._topics_text.pack(fill="both", expand=True, pady=(2, 8))

        ttk.Label(filter_lf, text="Keywords (one per line):").pack(anchor="w")
        self._keywords_text = tk.Text(filter_lf, height=4, width=40, wrap="word")
        self._keywords_text.pack(fill="both", expand=True, pady=(2, 0))

    def _build_schedule_frame(self) -> None:
        schedule_lf = ttk.LabelFrame(self, text="Schedule", padding=6)
        schedule_lf.pack(fill="x", pady=(0, 8))

        ttk.Label(schedule_lf, text="Daily generation time:").pack(side="left", padx=(0, 8))

        self._hour_var = tk.IntVar(value=7)
        self._minute_var = tk.IntVar(value=0)

        ttk.Label(schedule_lf, text="Hour:").pack(side="left")
        self._hour_spinbox = ttk.Spinbox(
            schedule_lf, from_=0, to=23, textvariable=self._hour_var, width=4
        )
        self._hour_spinbox.pack(side="left", padx=(2, 8))

        ttk.Label(schedule_lf, text="Minute:").pack(side="left")
        self._minute_spinbox = ttk.Spinbox(
            schedule_lf, from_=0, to=59, textvariable=self._minute_var, width=4
        )
        self._minute_spinbox.pack(side="left", padx=(2, 0))

    def _build_save_row(self) -> None:
        ttk.Button(self, text="Save Configuration", command=self._save).pack(pady=(4, 0))

    # ------------------------------------------------------------------
    # Populate / refresh
    # ------------------------------------------------------------------

    def _populate_from_config(self) -> None:
        """Fill all widgets from self._config."""
        # Sources listbox
        self._sources_listbox.delete(0, tk.END)
        for source in self._config.sources:
            self._sources_listbox.insert(tk.END, f"{source.name} — {source.url}")
        self._refresh_onboarding()

        # Topics
        self._topics_text.delete("1.0", tk.END)
        self._topics_text.insert("1.0", "\n".join(self._config.filter.topics))

        # Keywords
        self._keywords_text.delete("1.0", tk.END)
        self._keywords_text.insert("1.0", "\n".join(self._config.filter.keywords))

        # Schedule
        self._hour_var.set(self._config.scheduler.generation_hour)
        self._minute_var.set(self._config.scheduler.generation_minute)

    def _refresh_onboarding(self) -> None:
        if self._sources_listbox.size() == 0:
            self._onboarding_label.pack(pady=(4, 0))
        else:
            self._onboarding_label.pack_forget()

    # ------------------------------------------------------------------
    # Source CRUD
    # ------------------------------------------------------------------

    def _add_source(self) -> None:
        dialog = _SourceDialog(self, title="Add Source")
        if dialog.result is not None:
            self._config.sources.append(dialog.result)
            self._sources_listbox.insert(tk.END, f"{dialog.result.name} — {dialog.result.url}")
            self._refresh_onboarding()

    def _edit_source(self) -> None:
        selection = self._sources_listbox.curselection()
        if not selection:
            messagebox.showinfo("Edit Source", "Please select a source to edit.", parent=self)
            return
        idx = selection[0]
        existing = self._config.sources[idx]
        dialog = _SourceDialog(self, title="Edit Source", source=existing)
        if dialog.result is not None:
            self._config.sources[idx] = dialog.result
            self._sources_listbox.delete(idx)
            self._sources_listbox.insert(idx, f"{dialog.result.name} — {dialog.result.url}")
            self._sources_listbox.selection_set(idx)

    def _remove_source(self) -> None:
        selection = self._sources_listbox.curselection()
        if not selection:
            messagebox.showinfo("Remove Source", "Please select a source to remove.", parent=self)
            return
        idx = selection[0]
        self._config.sources.pop(idx)
        self._sources_listbox.delete(idx)
        self._refresh_onboarding()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _collect_config(self) -> AppConfig:
        """Read widget values back into an AppConfig."""
        topics = [
            line.strip()
            for line in self._topics_text.get("1.0", tk.END).splitlines()
            if line.strip()
        ]
        keywords = [
            line.strip()
            for line in self._keywords_text.get("1.0", tk.END).splitlines()
            if line.strip()
        ]
        try:
            hour = int(self._hour_var.get())
            minute = int(self._minute_var.get())
        except (ValueError, tk.TclError):
            hour, minute = 7, 0

        return AppConfig(
            sources=list(self._config.sources),
            filter=FilterConfig(topics=topics, keywords=keywords),
            scheduler=SchedulerConfig(generation_hour=hour, generation_minute=minute),
        )

    def _save(self) -> None:
        self._config = self._collect_config()
        # If user removed all sources, restore the built-in defaults
        if not self._config.sources:
            from .config_store import _default_config
            self._config.sources = list(_default_config().sources)
            self._sources_listbox.delete(0, tk.END)
            for source in self._config.sources:
                self._sources_listbox.insert(tk.END, f"{source.name} — {source.url}")
            self._refresh_onboarding()
        try:
            self._config_store.save(self._config)
            logger.info("Configuration saved.")
        except Exception as exc:
            logger.error("Failed to save configuration: %s", exc)
            messagebox.showerror("Save Error", f"Could not save configuration:\n{exc}", parent=self)
            return

        if self._on_config_saved is not None:
            try:
                self._on_config_saved()
            except Exception as exc:
                logger.error("on_config_saved callback raised: %s", exc)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_config(self) -> AppConfig:
        """Return the most recently saved AppConfig."""
        return self._config


# ---------------------------------------------------------------------------
# PlaybackPanel
# ---------------------------------------------------------------------------

class PlaybackPanel(ttk.Frame):
    """Right panel: status, progress, and playback controls."""

    def __init__(self, parent: tk.Widget, player, root: tk.Tk) -> None:
        super().__init__(parent, padding=8)
        self._player = player
        self._root = root

        self._build_ui()
        self._schedule_update()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        playback_lf = ttk.LabelFrame(self, text="Daily News Podcast", padding=10)
        playback_lf.pack(fill="both", expand=True)

        # Status label
        self._status_var = tk.StringVar(value="No episode available")
        self._status_label = ttk.Label(
            playback_lf, textvariable=self._status_var, font=("TkDefaultFont", 10, "bold")
        )
        self._status_label.pack(pady=(0, 6))

        # Progress label
        self._progress_var = tk.StringVar(value="")
        self._progress_label = ttk.Label(playback_lf, textvariable=self._progress_var)
        self._progress_label.pack(pady=(0, 12))

        # Playback buttons
        btn_frame = ttk.Frame(playback_lf)
        btn_frame.pack()

        self._replay_btn = ttk.Button(btn_frame, text="⏮ Replay", command=self._on_replay)
        self._replay_btn.pack(side="left", padx=4)

        self._stop_resume_btn = ttk.Button(btn_frame, text="⏸ Stop/Resume", command=self._on_stop_resume)
        self._stop_resume_btn.pack(side="left", padx=4)

        self._skip_btn = ttk.Button(btn_frame, text="⏭ Skip", command=self._on_skip)
        self._skip_btn.pack(side="left", padx=4)

        # Start with buttons disabled (no episode loaded)
        self._set_buttons_enabled(False)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_replay(self) -> None:
        try:
            self._player.replay()
        except Exception as exc:
            logger.error("Replay error: %s", exc)

    def _on_stop_resume(self) -> None:
        try:
            state = self._player.get_state()
            if state.is_playing:
                self._player.stop()
            else:
                self._player.play()
        except Exception as exc:
            logger.error("Stop/Resume error: %s", exc)

    def _on_skip(self) -> None:
        try:
            self._player.skip()
        except Exception as exc:
            logger.error("Skip error: %s", exc)

    # ------------------------------------------------------------------
    # Periodic update
    # ------------------------------------------------------------------

    def _schedule_update(self) -> None:
        self._update_progress()
        self._root.after(1000, self._schedule_update)

    def _update_progress(self) -> None:
        """Refresh the progress label from the player state."""
        try:
            state = self._player.get_state()
        except Exception:
            return

        if state.total_segments == 0:
            self._progress_var.set("")
            self._set_buttons_enabled(False)
            return

        self._set_buttons_enabled(True)

        elapsed_s = state.elapsed_episode_ms // 1000
        mm = elapsed_s // 60
        ss = elapsed_s % 60
        story_num = min(state.current_segment_index + 1, state.total_segments)
        self._progress_var.set(
            f"Story {story_num} of {state.total_segments} — {mm:02d}:{ss:02d} elapsed"
        )

        if state.episode_ended:
            self._set_buttons_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status(self, message: str) -> None:
        """Update the status label text (thread-safe via after_idle)."""
        self._root.after_idle(lambda: self._status_var.set(message))

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._replay_btn.config(state=state)
        self._stop_resume_btn.config(state=state)
        self._skip_btn.config(state=state)


# ---------------------------------------------------------------------------
# App — root Tk window
# ---------------------------------------------------------------------------

class App(tk.Tk):
    """Main application window."""

    def __init__(self, config_store, episode_store, pipeline, scheduler, player) -> None:
        super().__init__()
        self.title("Daily News Podcast")
        self.resizable(True, True)

        self._config_store = config_store
        self._episode_store = episode_store
        self._pipeline = pipeline
        self._scheduler = scheduler
        self._player = player

        # Build panels
        self._playback_panel = PlaybackPanel(self, player=player, root=self)
        self._config_panel = ConfigPanel(
            self,
            config_store=config_store,
            on_config_saved=self._on_config_saved,
        )

        # Layout: config on left, playback on right
        self._config_panel.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        self._playback_panel.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        # Wire scheduler callbacks
        scheduler.on_success = self._on_pipeline_success
        scheduler.on_failure = self._on_pipeline_failure

        # Load latest episode on startup
        self._load_latest_episode()

    # ------------------------------------------------------------------
    # Scheduler callbacks
    # ------------------------------------------------------------------

    def _on_pipeline_success(self, episode) -> None:
        """Called by the scheduler background thread on pipeline success."""
        self._player.load(episode)
        self.after_idle(lambda: self._playback_panel.set_status("New episode available!"))

    def _on_pipeline_failure(self, error_msg: str) -> None:
        """Called by the scheduler background thread on pipeline failure."""
        self.after_idle(lambda: self._playback_panel.set_status(f"Error: {error_msg}"))

    # ------------------------------------------------------------------
    # Config saved callback
    # ------------------------------------------------------------------

    def _on_config_saved(self) -> None:
        """Restart the scheduler with the updated config."""
        config = self._config_panel.get_config()
        try:
            self._scheduler.stop()
            self._scheduler.start(config.scheduler, self._pipeline)
            logger.info("Scheduler restarted with new config.")
        except Exception as exc:
            logger.error("Failed to restart scheduler: %s", exc)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _load_latest_episode(self) -> None:
        """Load the most recent episode from the store and hand it to the player."""
        try:
            episode = self._episode_store.load_latest()
            if episode is not None:
                self._player.load(episode)
                self._playback_panel.set_status("New episode available!")
                logger.info("Loaded latest episode from store: %s", episode.audio_path)
        except Exception as exc:
            logger.error("Failed to load latest episode: %s", exc)
