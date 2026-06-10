"""
Flet UI component for displaying application log output in real-time.

Pulls formatted log records from :class:`app.core.logger.LogViewHandler`
(populated by :func:`app.core.logger.setup_logging`) and renders them in a
scrollable :class:`ft.ListView`.
"""

from __future__ import annotations

import flet as ft
from typing import Optional

from app.core.logger import get_view_handler, LogViewHandler


class LogView(ft.Column):
    """A scrollable, auto-updating log terminal.

    Call :meth:`refresh` periodically (e.g. via a :class:`ft.Timer` or a page
    event loop) to keep the display synchronised with new log records.

    Usage::

        log_view = LogView()
        page.add(log_view)

        # In a periodic callback:
        log_view.refresh()
    """

    MAX_VISIBLE_LINES: int = 500

    def __init__(self) -> None:
        super().__init__()
        self._log_listview: ft.ListView = ft.ListView(
            expand=True,
            spacing=2,
            auto_scroll=True,
        )
        self._all_lines: list[str] = []
        self._view_handler: Optional[LogViewHandler] = None

        self._build_inner()

    def _build_inner(self) -> None:
        """Build the log display column."""
        header = ft.Row(
            controls=[
                ft.Text("Log Output", size=16, weight=ft.FontWeight.BOLD, expand=True),
                ft.ElevatedButton("Clear Log", on_click=self._on_clear),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.controls = [
            header,
            ft.Container(
                content=self._log_listview,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=5,
                padding=5,
                expand=True,
                bgcolor=ft.Colors.BLACK,
            ),
        ]
        self.spacing = 5
        self.expand = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Pull the latest log records from :class:`LogViewHandler` and
        update the displayed list."""
        if self._view_handler is None:
            self._view_handler = get_view_handler()

        if self._view_handler is None:
            return  # logging not yet initialised

        formatted: list[str] = self._view_handler.get_formatted_records()

        # Avoid unnecessary UI updates if nothing changed
        if formatted == self._all_lines:
            return

        self._all_lines = formatted

        # Keep within the visible cap
        display_lines = self._all_lines[-self.MAX_VISIBLE_LINES :]

        # Build Text controls — one per log line
        self._log_listview.controls.clear()
        for line in display_lines:
            self._log_listview.controls.append(
                ft.Text(
                    value=line,
                    selectable=True,
                    size=11,
                    font_family="monospace",
                    color=ft.Colors.GREEN_200,
                )
            )

        # Auto-scroll to latest entry
        self._log_listview.auto_scroll = True
        self.update()

    def clear(self) -> None:
        """Clear both the displayed log and the underlying :class:`LogViewHandler`
        buffer."""
        if self._view_handler is None:
            self._view_handler = get_view_handler()
        if self._view_handler is not None:
            self._view_handler.clear()

        self._all_lines.clear()
        self._log_listview.controls.clear()
        self.update()

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_clear(self, e: ft.ControlEvent) -> None:
        """Handle 'Clear Log' button press."""
        self.clear()
