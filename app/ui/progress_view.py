"""
Progress View UI component for KDP Translator.

Displays translation progress including an overall progress bar,
per-language progress bars, a list of agent statuses, and queue statistics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import flet as ft

logger = logging.getLogger(__name__)

# Colours used to distinguish per-language progress bars
_LANGUAGE_COLORS: List[str] = [
    ft.Colors.BLUE,
    ft.Colors.GREEN,
    ft.Colors.ORANGE,
    ft.Colors.PURPLE,
    ft.Colors.TEAL,
    ft.Colors.PINK,
    ft.Colors.INDIGO,
    ft.Colors.CYAN,
]


class ProgressView(ft.Column):
    """Flet component showing translation progress.

    Displays:
    - An overall progress bar with a percentage label.
    - Per-language progress bars (added dynamically per language).
    - A scrollable agent-status list.
    - Queue statistics (total / completed / failed / pending).

    Usage::

        progress_view = ProgressView()
        page.add(progress_view)

        # Update progress as translation runs
        progress_view.update_overall(5, 10)
        progress_view.update_language("de", 3, 5)
        progress_view.update_agents(agent_pool.get_agents_status())
        progress_view.update_queue_stats(scheduler.get_queue_stats())
    """

    def __init__(self) -> None:
        super().__init__()
        self._overall_bar: Optional[ft.ProgressBar] = None
        self._overall_text: Optional[ft.Text] = None
        self._language_bars: Dict[str, ft.ProgressBar] = {}
        self._language_texts: Dict[str, ft.Text] = {}
        self._agent_status_column: Optional[ft.Column] = None
        self._queue_stats_text: Optional[ft.Text] = None

        # Refs
        self._overall_bar_ref = ft.Ref[ft.ProgressBar]()
        self._overall_text_ref = ft.Ref[ft.Text]()
        self._language_container_ref = ft.Ref[ft.Column]()
        self._agent_column_ref = ft.Ref[ft.Column]()
        self._queue_stats_ref = ft.Ref[ft.Text]()
        self._reset_btn_ref = ft.Ref[ft.ElevatedButton]()

        self._build_inner()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_inner(self) -> None:
        """Construct the control tree."""
        self._overall_bar = ft.ProgressBar(
            ref=self._overall_bar_ref,
            value=0.0,
            width=400,
            color=ft.Colors.BLUE,
            bgcolor=ft.Colors.GREY_300,
        )
        self._overall_text = ft.Text(
            ref=self._overall_text_ref,
            value="0 / 0 (0%)",
            size=13,
        )

        self._queue_stats_text = ft.Text(
            ref=self._queue_stats_ref,
            value="Queue: \u2014",
            size=12,
            italic=True,
        )

        self._agent_status_column = ft.Column(
            ref=self._agent_column_ref,
            controls=[
                ft.Text("Agents: \u2014", size=12, italic=True),
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            height=200,
        )

        language_container = ft.Column(
            ref=self._language_container_ref,
            controls=[],
            spacing=4,
        )

        overall_section = ft.Column(
            controls=[
                ft.Text("Overall Progress", size=14, weight=ft.FontWeight.BOLD),
                self._overall_bar,
                self._overall_text,
                ft.Divider(height=1, color=ft.Colors.GREY_300),
            ],
            spacing=4,
        )

        language_section = ft.Column(
            controls=[
                ft.Text("Per-Language Progress", size=14, weight=ft.FontWeight.BOLD),
                language_container,
                ft.Divider(height=1, color=ft.Colors.GREY_300),
            ],
            spacing=4,
        )

        agents_section = ft.Column(
            controls=[
                ft.Text("Agent Status", size=14, weight=ft.FontWeight.BOLD),
                self._agent_status_column,
                ft.Divider(height=1, color=ft.Colors.GREY_300),
            ],
            spacing=4,
        )

        queue_section = ft.Column(
            controls=[
                ft.Text("Queue Stats", size=14, weight=ft.FontWeight.BOLD),
                self._queue_stats_text,
            ],
            spacing=4,
        )

        content_column = ft.Column(
            controls=[
                overall_section,
                language_section,
                agents_section,
                queue_section,
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            ref=self._reset_btn_ref,
                            text="Reset Progress",
                            on_click=self._on_reset,
                            visible=False,  # Hidden until progress is shown
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
            width=500,
        )

        self.controls = [ft.Container(content=content_column, padding=8)]

    # ------------------------------------------------------------------
    # Public update methods
    # ------------------------------------------------------------------

    def update_overall(self, completed: int, total: int) -> None:
        """Update the overall progress bar and percentage text.

        Parameters
        ----------
        completed:
            Number of chunks translated.
        total:
            Total number of chunks.
        """
        if self._overall_bar is None or self._overall_text is None:
            return

        fraction = completed / total if total > 0 else 0.0
        percent = round(fraction * 100)

        self._overall_bar.value = fraction
        self._overall_text.value = f"{completed} / {total} ({percent}%)"

        self._overall_bar.update()
        self._overall_text.update()

        # Show reset button once progress exists
        if self._reset_btn_ref.current is not None:
            self._reset_btn_ref.current.visible = True
            self._reset_btn_ref.current.update()

    def update_language(self, language: str, completed: int, total: int) -> None:
        """Update or create a per-language progress bar.

        If no bar exists for *language*, one is created on first call.

        Parameters
        ----------
        language:
            Language code (e.g. ``"de"``, ``"fr"``).
        completed:
            Number of chunks translated for this language.
        total:
            Total number of chunks for this language.
        """
        fraction = completed / total if total > 0 else 0.0
        percent = round(fraction * 100)

        if language in self._language_bars:
            # Update existing bar
            bar = self._language_bars[language]
            bar.value = fraction
            bar.update()

            text = self._language_texts[language]
            text.value = f"{language.upper()}: {completed} / {total} ({percent}%)"
            text.update()
        else:
            # Create new language progress row
            color_idx = len(self._language_bars) % len(_LANGUAGE_COLORS)
            bar = ft.ProgressBar(
                value=fraction,
                width=400,
                color=_LANGUAGE_COLORS[color_idx],
                bgcolor=ft.Colors.GREY_300,
            )
            text = ft.Text(
                value=f"{language.upper()}: {completed} / {total} ({percent}%)",
                size=12,
            )

            self._language_bars[language] = bar
            self._language_texts[language] = text

            # Add to the language container
            if (
                self._language_container_ref is not None
                and self._language_container_ref.current is not None
            ):
                self._language_container_ref.current.controls.append(
                    ft.Column(
                        controls=[text, bar],
                        spacing=2,
                    )
                )
                self._language_container_ref.current.update()

    def update_agents(self, agents_status: List[Dict[str, Any]]) -> None:
        """Update the agent status list.

        Parameters
        ----------
        agents_status:
            List of agent status dicts as returned by
            :meth:`AgentPool.get_agents_status`.
        """
        if self._agent_status_column is None:
            return

        if not agents_status:
            self._agent_status_column.controls = [
                ft.Text("Agents: \u2014", size=12, italic=True),
            ]
            self._agent_status_column.update()
            return

        rows: List[ft.Control] = []
        for agent in agents_status:
            agent_id = agent.get("agent_id", "?")
            status = agent.get("status", "unknown")
            lang = agent.get("current_language") or ""
            chapter = agent.get("current_chapter") or ""
            chunk = agent.get("current_chunk") or ""
            progress = agent.get("progress", 0.0)
            completed = agent.get("chunks_completed", 0)
            failed = agent.get("chunks_failed", 0)
            error = agent.get("last_error")

            # Build a status icon / colour
            status_icon = {
                "idle": "\u26aa",
                "working": "\ud83d\udd04",
                "retry": "\u26a0\ufe0f",
                "error": "\u274c",
                "completed": "\u2705",
            }.get(status, "\u2753")

            parts = [f"{status_icon} {agent_id}: {status}"]
            if lang:
                parts.append(f"[{lang}]")
            if chapter:
                parts.append(f"Ch:{chapter}")
            if chunk:
                parts.append(f"Chk:{chunk}")
            parts.append(f"({round(progress * 100)}%)")
            parts.append(f"\u2713{completed} \u2717{failed}")
            if error:
                parts.append(f"ERR:{error[:50]}")

            rows.append(
                ft.Text(
                    value=" ".join(parts),
                    size=11,
                    font_family="monospace",
                )
            )

        self._agent_status_column.controls = rows
        self._agent_status_column.update()

    def update_queue_stats(self, stats: Dict[str, int]) -> None:
        """Update the queue statistics text.

        Parameters
        ----------
        stats:
            Dict with keys ``total``, ``completed``, ``failed``, ``pending``
            (as returned by :meth:`TranslationScheduler.get_queue_stats`).
        """
        if self._queue_stats_text is None:
            return

        total = stats.get("total", 0)
        completed = stats.get("completed", 0)
        failed = stats.get("failed", 0)
        pending = stats.get("pending", 0)

        self._queue_stats_text.value = (
            f"Queue: {total} total \u00b7 {completed} completed \u00b7 "
            f"{failed} failed \u00b7 {pending} pending"
        )
        self._queue_stats_text.update()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all progress indicators to their initial (empty) state."""
        # Overall
        if self._overall_bar is not None:
            self._overall_bar.value = 0.0
            self._overall_bar.update()
        if self._overall_text is not None:
            self._overall_text.value = "0 / 0 (0%)"
            self._overall_text.update()

        # Per-language
        self._language_bars.clear()
        self._language_texts.clear()
        if (
            self._language_container_ref is not None
            and self._language_container_ref.current is not None
        ):
            self._language_container_ref.current.controls.clear()
            self._language_container_ref.current.update()

        # Agents
        if self._agent_status_column is not None:
            self._agent_status_column.controls = [
                ft.Text("Agents: \u2014", size=12, italic=True),
            ]
            self._agent_status_column.update()

        # Queue stats
        if self._queue_stats_text is not None:
            self._queue_stats_text.value = "Queue: \u2014"
            self._queue_stats_text.update()

        # Hide reset button
        if self._reset_btn_ref.current is not None:
            self._reset_btn_ref.current.visible = False
            self._reset_btn_ref.current.update()

        logger.info("ProgressView reset")

    def _on_reset(self, e: ft.ControlEvent) -> None:
        """Handle the reset button click."""
        self.reset()

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or hide the entire progress view."""
        self.visible = visible
        self.update()
