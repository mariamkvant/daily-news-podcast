# UI: tkinter configuration panel and playback controls.
"""
ui.py — tkinter UI for Daily News Podcast.

Contains:
  - ConfigPanel  : LabelFrames for sources, filter settings, and schedule.
  - PlaybackPanel: LabelFrame with status, progress, and playback buttons.
  - App          : Root Tk window that wires everything together.
"""

import logging
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .config_store import AVAILABLE_KEYWORDS, AVAILABLE_TOPICS
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
# Helper: simple single-line text input dialog
# ---------------------------------------------------------------------------

class _TextInputDialog(tk.Toplevel):
    """Modal dialog for entering a single text value."""

    def __init__(self, parent: tk.Widget, title: str = "Input", prompt: str = "Value:") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: str | None = None

        ttk.Label(self, text=prompt).pack(padx=12, pady=(12, 4), anchor="w")
        self._var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self._var, width=36)
        entry.pack(padx=12, pady=(0, 8))
        entry.focus_set()

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window(self)

    def _on_ok(self) -> None:
        val = self._var.get().strip()
        if val:
            self.result = val
        self.destroy()


# ---------------------------------------------------------------------------
# ConfigPanel
# ---------------------------------------------------------------------------

class ConfigPanel(ttk.Frame):
    """Left panel: sources (with enable toggle), topic checkboxes, keyword checkboxes, schedule."""

    def __init__(self, parent: tk.Widget, config_store, on_config_saved=None) -> None:
        super().__init__(parent, padding=8)
        self._config_store = config_store
        self._on_config_saved = on_config_saved
        self._config: AppConfig = config_store.load()

        # Notebook: Sources | Topics | Keywords | Schedule
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True)

        self._sources_tab = ttk.Frame(self._notebook, padding=6)
        self._topics_tab  = ttk.Frame(self._notebook, padding=6)
        self._keywords_tab = ttk.Frame(self._notebook, padding=6)
        self._schedule_tab = ttk.Frame(self._notebook, padding=6)

        self._notebook.add(self._sources_tab,  text="Sources")
        self._notebook.add(self._topics_tab,   text="Topics")
        self._notebook.add(self._keywords_tab, text="Keywords")
        self._notebook.add(self._schedule_tab, text="Schedule")

        self._build_sources_tab()
        self._build_topics_tab()
        self._build_keywords_tab()
        self._build_schedule_tab()

        ttk.Button(self, text="Save Configuration", command=self._save).pack(pady=(8, 0))

        self._populate_from_config()

    # ------------------------------------------------------------------
    # Sources tab
    # ------------------------------------------------------------------

    def _build_sources_tab(self) -> None:
        tab = self._sources_tab

        # Toolbar: Select All / None + Add custom
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(toolbar, text="All",  width=5, command=self._sources_select_all).pack(side="left", padx=(0, 2))
        ttk.Button(toolbar, text="None", width=5, command=self._sources_select_none).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Custom", command=self._add_custom_source).pack(side="right")

        # Scrollable checkbox list
        container = ttk.Frame(tab)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._sources_inner = ttk.Frame(canvas)

        self._sources_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._sources_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1*(ev.delta//120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._source_vars: dict[str, tk.BooleanVar] = {}  # name -> BooleanVar
        self._source_custom: list[Source] = []            # user-added custom sources

    def _populate_sources(self) -> None:
        """Rebuild the sources checkbox list from self._config.sources."""
        for widget in self._sources_inner.winfo_children():
            widget.destroy()
        self._source_vars.clear()

        for source in self._config.sources:
            var = tk.BooleanVar(value=source.enabled)
            self._source_vars[source.name] = var
            row = ttk.Frame(self._sources_inner)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(row, variable=var, text=source.name, width=28).pack(side="left")

    def _sources_select_all(self) -> None:
        for var in self._source_vars.values():
            var.set(True)

    def _sources_select_none(self) -> None:
        for var in self._source_vars.values():
            var.set(False)

    def _add_custom_source(self) -> None:
        dialog = _SourceDialog(self, title="Add Custom Source")
        if dialog.result is not None:
            # Avoid duplicates by name
            existing_names = {s.name for s in self._config.sources}
            if dialog.result.name in existing_names:
                messagebox.showwarning("Duplicate", f"A source named '{dialog.result.name}' already exists.", parent=self)
                return
            self._config.sources.append(dialog.result)
            self._populate_sources()

    # ------------------------------------------------------------------
    # Topics tab
    # ------------------------------------------------------------------

    def _build_topics_tab(self) -> None:
        tab = self._topics_tab

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(toolbar, text="All",  width=5, command=self._topics_select_all).pack(side="left", padx=(0, 2))
        ttk.Button(toolbar, text="None", width=5, command=self._topics_select_none).pack(side="left", padx=2)

        ttk.Label(tab, text="Select topics to include in your podcast:", foreground="gray").pack(anchor="w", pady=(0, 4))

        # Two-column grid of checkboxes
        grid = ttk.Frame(tab)
        grid.pack(fill="both", expand=True)

        self._topic_vars: dict[str, tk.BooleanVar] = {}
        for i, topic in enumerate(AVAILABLE_TOPICS):
            var = tk.BooleanVar()
            self._topic_vars[topic] = var
            ttk.Checkbutton(grid, variable=var, text=topic.capitalize()).grid(
                row=i // 2, column=i % 2, sticky="w", padx=4, pady=2
            )

    def _topics_select_all(self) -> None:
        for var in self._topic_vars.values():
            var.set(True)

    def _topics_select_none(self) -> None:
        for var in self._topic_vars.values():
            var.set(False)

    # ------------------------------------------------------------------
    # Keywords tab
    # ------------------------------------------------------------------

    def _build_keywords_tab(self) -> None:
        tab = self._keywords_tab

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(toolbar, text="All",  width=5, command=self._keywords_select_all).pack(side="left", padx=(0, 2))
        ttk.Button(toolbar, text="None", width=5, command=self._keywords_select_none).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Custom", command=self._add_custom_keyword).pack(side="right")

        ttk.Label(tab, text="Select keywords to boost in relevance scoring:", foreground="gray").pack(anchor="w", pady=(0, 4))

        # Scrollable two-column grid
        container = ttk.Frame(tab)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._keywords_inner = ttk.Frame(canvas)
        self._keywords_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._keywords_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1*(ev.delta//120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._keyword_vars: dict[str, tk.BooleanVar] = {}
        self._custom_keywords: list[str] = []
        self._keywords_canvas = canvas

    def _populate_keywords(self) -> None:
        """Rebuild keyword checkboxes (preset + custom)."""
        for widget in self._keywords_inner.winfo_children():
            widget.destroy()

        all_keywords = list(AVAILABLE_KEYWORDS) + self._custom_keywords
        # Preserve existing var states
        existing = {k: v.get() for k, v in self._keyword_vars.items()}
        self._keyword_vars.clear()

        for i, kw in enumerate(all_keywords):
            var = tk.BooleanVar(value=existing.get(kw, False))
            self._keyword_vars[kw] = var
            ttk.Checkbutton(self._keywords_inner, variable=var, text=kw.capitalize()).grid(
                row=i // 2, column=i % 2, sticky="w", padx=4, pady=2
            )

    def _keywords_select_all(self) -> None:
        for var in self._keyword_vars.values():
            var.set(True)

    def _keywords_select_none(self) -> None:
        for var in self._keyword_vars.values():
            var.set(False)

    def _add_custom_keyword(self) -> None:
        dialog = _TextInputDialog(self, title="Add Keyword", prompt="Enter a keyword or phrase:")
        if dialog.result:
            kw = dialog.result.strip().lower()
            if kw and kw not in self._keyword_vars:
                self._custom_keywords.append(kw)
                self._populate_keywords()
                # Tick the new one
                if kw in self._keyword_vars:
                    self._keyword_vars[kw].set(True)

    # ------------------------------------------------------------------
    # Schedule tab
    # ------------------------------------------------------------------

    def _build_schedule_tab(self) -> None:
        tab = self._schedule_tab

        # --- Daily generation time ---
        ttk.Label(tab, text="Daily generation time:").pack(anchor="w", pady=(0, 8))

        time_row = ttk.Frame(tab)
        time_row.pack(anchor="w")

        self._hour_var = tk.IntVar(value=7)
        self._minute_var = tk.IntVar(value=0)

        ttk.Label(time_row, text="Hour:").pack(side="left")
        ttk.Spinbox(time_row, from_=0, to=23, textvariable=self._hour_var, width=5).pack(side="left", padx=(4, 12))
        ttk.Label(time_row, text="Minute:").pack(side="left")
        ttk.Spinbox(time_row, from_=0, to=59, textvariable=self._minute_var, width=5).pack(side="left", padx=4)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=12)

        # --- Podcast length ---
        ttk.Label(tab, text="Podcast length:").pack(anchor="w", pady=(0, 8))

        self._duration_options = [
            ("~1 minute  (quick headlines)",  60),
            ("~5 minutes  (brief overview)",  300),
            ("~10 minutes  (standard)",       600),
            ("~15 minutes  (extended)",       900),
            ("~30 minutes  (deep dive)",      1800),
            ("~60 minutes  (full edition)",   3600),
        ]
        self._duration_var = tk.IntVar(value=600)

        for label, seconds in self._duration_options:
            ttk.Radiobutton(
                tab,
                text=label,
                variable=self._duration_var,
                value=seconds,
            ).pack(anchor="w", pady=2)

    # ------------------------------------------------------------------
    # Populate from config
    # ------------------------------------------------------------------

    def _populate_from_config(self) -> None:
        # Sources
        self._populate_sources()

        # Topics
        active_topics = set(self._config.filter.topics)
        for topic, var in self._topic_vars.items():
            var.set(topic in active_topics)

        # Keywords — split into preset vs custom
        preset_set = set(AVAILABLE_KEYWORDS)
        active_keywords = set(self._config.filter.keywords)
        self._custom_keywords = [k for k in self._config.filter.keywords if k not in preset_set]
        self._populate_keywords()
        for kw, var in self._keyword_vars.items():
            var.set(kw in active_keywords)

        # Schedule
        self._hour_var.set(self._config.scheduler.generation_hour)
        self._minute_var.set(self._config.scheduler.generation_minute)
        self._duration_var.set(self._config.max_duration_seconds)

    # ------------------------------------------------------------------
    # Collect & save
    # ------------------------------------------------------------------

    def _collect_config(self) -> AppConfig:
        # Sources: update enabled flags
        source_enabled = {name: var.get() for name, var in self._source_vars.items()}
        for source in self._config.sources:
            source.enabled = source_enabled.get(source.name, source.enabled)

        topics = [t for t, v in self._topic_vars.items() if v.get()]
        keywords = [k for k, v in self._keyword_vars.items() if v.get()]

        try:
            hour = int(self._hour_var.get())
            minute = int(self._minute_var.get())
        except (ValueError, tk.TclError):
            hour, minute = 7, 0

        return AppConfig(
            sources=list(self._config.sources),
            filter=FilterConfig(topics=topics, keywords=keywords, relevance_threshold=0.05),
            scheduler=SchedulerConfig(generation_hour=hour, generation_minute=minute),
            max_duration_seconds=self._duration_var.get(),
        )

    def _save(self) -> None:
        self._config = self._collect_config()
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

    def get_config(self) -> AppConfig:
        return self._config


# ---------------------------------------------------------------------------
# PlaybackPanel
# ---------------------------------------------------------------------------

class PlaybackPanel(ttk.Frame):
    """Right panel: status, progress, story list, and playback controls."""

    def __init__(self, parent: tk.Widget, player, root: tk.Tk, on_generate=None) -> None:
        super().__init__(parent, padding=8)
        self._player = player
        self._root = root
        self._on_generate = on_generate
        self._episode = None          # current Episode object
        self._last_segment_index = -1 # track highlight changes

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
        ttk.Label(
            playback_lf, textvariable=self._status_var, font=("TkDefaultFont", 10, "bold")
        ).pack(pady=(0, 4))

        # Duration label  (e.g. "4 stories · 3m 42s total")
        self._duration_var = tk.StringVar(value="")
        ttk.Label(playback_lf, textvariable=self._duration_var, foreground="gray").pack(pady=(0, 8))

        # Story list
        stories_lf = ttk.LabelFrame(playback_lf, text="Stories — double-click to jump", padding=4)
        stories_lf.pack(fill="both", expand=True, pady=(0, 8))

        list_frame = ttk.Frame(stories_lf)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._story_listbox = tk.Listbox(
            list_frame,
            height=6,
            yscrollcommand=scrollbar.set,
            selectmode="single",
            activestyle="none",
            font=("TkDefaultFont", 9),
        )
        scrollbar.config(command=self._story_listbox.yview)
        self._story_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._story_listbox.bind("<Double-Button-1>", self._on_story_double_click)
        self._story_listbox.bind("<<ListboxSelect>>", self._on_story_select)

        # Story description box
        desc_lf = ttk.LabelFrame(playback_lf, text="Story Description", padding=6)
        desc_lf.pack(fill="x", pady=(0, 8))

        self._desc_text = tk.Text(
            desc_lf,
            height=4,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 9),
            relief="flat",
        )
        desc_sb = ttk.Scrollbar(desc_lf, orient="vertical", command=self._desc_text.yview)
        self._desc_text.configure(yscrollcommand=desc_sb.set)
        self._desc_text.pack(side="left", fill="both", expand=True)
        desc_sb.pack(side="right", fill="y")
        # Match background to the theme after the widget is realised
        self._root.after_idle(lambda: self._desc_text.configure(
            background=self._root.cget("background")
        ))

        # Progress label  (e.g. "Story 2 of 4 — 01:12 / 03:42")
        self._progress_var = tk.StringVar(value="")
        ttk.Label(playback_lf, textvariable=self._progress_var).pack(pady=(0, 8))

        # Playback buttons
        btn_frame = ttk.Frame(playback_lf)
        btn_frame.pack()

        self._replay_btn = ttk.Button(btn_frame, text="⏮ Replay", command=self._on_replay)
        self._replay_btn.pack(side="left", padx=4)

        self._stop_resume_btn = ttk.Button(btn_frame, text="⏸ Stop/Resume", command=self._on_stop_resume)
        self._stop_resume_btn.pack(side="left", padx=4)

        self._skip_btn = ttk.Button(btn_frame, text="⏭ Skip", command=self._on_skip)
        self._skip_btn.pack(side="left", padx=4)

        # Generate Now button
        self._generate_btn = ttk.Button(
            playback_lf, text="🔄 Generate Now", command=self._on_generate_now
        )
        self._generate_btn.pack(pady=(12, 0))

        # Tag for highlighting the current story
        self._story_listbox.configure(selectbackground="#0078d7", selectforeground="white")

        self._set_buttons_enabled(False)

    # ------------------------------------------------------------------
    # Story list population
    # ------------------------------------------------------------------

    def load_episode(self, episode) -> None:
        """Populate the story list from an Episode (call from main thread or after_idle)."""
        self._episode = episode
        self._last_segment_index = -1
        self._story_listbox.delete(0, tk.END)

        total_ms = episode.total_duration_ms
        total_s = total_ms // 1000
        mm = total_s // 60
        ss = total_s % 60
        n = len(episode.segments)
        self._duration_var.set(f"{n} {'story' if n == 1 else 'stories'} · {mm}m {ss:02d}s total")

        for i, seg in enumerate(episode.segments):
            seg_s = seg.duration_ms // 1000
            label = seg.title if seg.title else f"Story {i + 1}"
            source = f"  [{seg.source_name}]" if seg.source_name else ""
            self._story_listbox.insert(tk.END, f"{i + 1}. {label}{source}  ({seg_s}s)")

        self._highlight_story(0)

    def _highlight_story(self, index: int) -> None:
        """Select and scroll to the given story index in the listbox."""
        if self._episode is None or index >= len(self._episode.segments):
            return
        self._story_listbox.selection_clear(0, tk.END)
        self._story_listbox.selection_set(index)
        self._story_listbox.see(index)
        self._last_segment_index = index
        self._show_description(index)

    # ------------------------------------------------------------------
    # Description panel
    # ------------------------------------------------------------------

    def _show_description(self, index: int) -> None:
        """Populate the description box for the given segment index."""
        if self._episode is None or index >= len(self._episode.segments):
            return
        seg = self._episode.segments[index]

        # Build display text
        lines = []
        if seg.source_name:
            lines.append(f"Source: {seg.source_name}")
        dur_s = seg.duration_ms // 1000
        lines.append(f"Duration: {dur_s}s")
        if seg.article_url and seg.article_url not in ("intro",):
            lines.append(f"URL: {seg.article_url}")
        lines.append("")
        # Prefer full summary; fall back to spoken_text
        body = seg.summary.strip() if seg.summary.strip() else seg.spoken_text.strip()
        if body:
            lines.append(body)

        content = "\n".join(lines)
        self._desc_text.configure(state="normal")
        self._desc_text.delete("1.0", tk.END)
        self._desc_text.insert("1.0", content)
        self._desc_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Story click handlers
    # ------------------------------------------------------------------

    def _on_story_select(self, _event) -> None:
        """Single-click: show description without jumping playback."""
        sel = self._story_listbox.curselection()
        if sel:
            self._show_description(sel[0])

    def _on_story_double_click(self, _event) -> None:
        """Double-click: jump to story and start playing."""
        sel = self._story_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        try:
            self._player.jump_to(idx)
        except Exception as exc:
            logger.error("Jump error: %s", exc)

    # ------------------------------------------------------------------
    # Generate Now
    # ------------------------------------------------------------------

    def _on_generate_now(self) -> None:
        if self._on_generate is not None:
            self._on_generate()

    # ------------------------------------------------------------------
    # Playback button callbacks
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
        """Refresh progress label and story highlight from player state."""
        try:
            state = self._player.get_state()
        except Exception:
            return

        if state.total_segments == 0:
            self._progress_var.set("")
            self._set_buttons_enabled(False)
            return

        self._set_buttons_enabled(not state.episode_ended)

        # Elapsed / total
        elapsed_s = state.elapsed_episode_ms // 1000
        e_mm, e_ss = elapsed_s // 60, elapsed_s % 60

        total_ms = self._episode.total_duration_ms if self._episode else 0
        total_s = total_ms // 1000
        t_mm, t_ss = total_s // 60, total_s % 60

        story_num = min(state.current_segment_index + 1, state.total_segments)
        self._progress_var.set(
            f"Story {story_num} of {state.total_segments} — "
            f"{e_mm:02d}:{e_ss:02d} / {t_mm:02d}:{t_ss:02d}"
        )

        # Sync story list highlight
        if state.current_segment_index != self._last_segment_index:
            self._highlight_story(state.current_segment_index)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status(self, message: str) -> None:
        """Update the status label (thread-safe)."""
        self._root.after_idle(lambda: self._status_var.set(message))

    def set_generate_btn_enabled(self, enabled: bool) -> None:
        """Enable or disable the Generate Now button (thread-safe)."""
        state = "normal" if enabled else "disabled"
        self._root.after_idle(lambda: self._generate_btn.config(state=state))

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
        self._playback_panel = PlaybackPanel(
            self, player=player, root=self, on_generate=self._run_pipeline_now
        )
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

        # Ensure today's episode is available on startup
        self._ensure_todays_episode()

    # ------------------------------------------------------------------
    # Scheduler callbacks
    # ------------------------------------------------------------------

    def _on_pipeline_success(self, episode) -> None:
        """Called by the scheduler or generate thread on pipeline success."""
        self._player.load(episode)
        self.after_idle(lambda: self._playback_panel.load_episode(episode))
        self.after_idle(lambda: self._playback_panel.set_status("Today's episode ready — press Play ▶"))
        self._playback_panel.set_generate_btn_enabled(True)

    def _on_pipeline_failure(self, error_msg: str) -> None:
        """Called by the scheduler or generate thread on pipeline failure."""
        self.after_idle(lambda: self._playback_panel.set_status(f"Error: {error_msg}"))
        self._playback_panel.set_generate_btn_enabled(True)

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
    # Startup: ensure today's episode exists
    # ------------------------------------------------------------------

    def _ensure_todays_episode(self) -> None:
        """Load today's episode if it exists; otherwise auto-generate it."""
        try:
            episode = self._episode_store.load_latest()
            if episode is not None and episode.date == date.today():
                self._player.load(episode)
                self._playback_panel.load_episode(episode)
                self._playback_panel.set_status("Today's episode ready — press Play ▶")
                logger.info("Loaded today's episode from store: %s", episode.audio_path)
                return
        except Exception as exc:
            logger.error("Failed to load latest episode: %s", exc)

        # No episode for today — generate one automatically
        logger.info("No episode for today — generating automatically.")
        self._run_pipeline_now()

    # ------------------------------------------------------------------
    # Generate Now (runs pipeline in a background thread)
    # ------------------------------------------------------------------

    def _run_pipeline_now(self) -> None:
        """Kick off the pipeline in a background thread."""
        self._playback_panel.set_status("Generating today's episode…")
        self._playback_panel.set_generate_btn_enabled(False)

        def _worker():
            try:
                episode = self._pipeline.run()
                logger.info("Pipeline completed: %s", episode.audio_path)
                self._on_pipeline_success(episode)
            except Exception as exc:
                logger.error("Pipeline failed: %s", exc)
                self._on_pipeline_failure(str(exc))

        threading.Thread(target=_worker, daemon=True).start()
