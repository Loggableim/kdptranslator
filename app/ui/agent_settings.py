"""
Flet UI component for configuring translation agent behaviour.

Provides dropdowns and radio-buttons that mirror the fields of
:class:`app.core.config.TranslationConfig`.
"""

from __future__ import annotations

import flet as ft
from typing import Callable, Optional

from app.core.config import TranslationConfig


class AgentSettings(ft.UserControl):
    """Form controls for translation-agent configuration.

    Parameters
    ----------
    on_config_changed:
        Optional callback invoked whenever any setting changes.  It receives
        the component instance as argument; call :meth:`get_config` to
        retrieve the current :class:`TranslationConfig`.
    """

    # ------------------------------------------------------------------
    # Option lists shared by all instances
    # ------------------------------------------------------------------
    AGENT_OPTIONS: list[tuple[str, int]] = [
        ("1", 1),
        ("2", 2),
        ("3", 3),
        ("4", 4),
        ("5", 5),
        ("6", 6),
        ("8", 8),
        ("10", 10),
        ("12", 12),
        ("16", 16),
    ]

    RETRY_OPTIONS: list[tuple[str, int]] = [
        ("1", 1),
        ("2", 2),
        ("3", 3),
        ("5", 5),
    ]

    TIMEOUT_OPTIONS: list[tuple[str, int]] = [
        ("30 s", 30),
        ("60 s", 60),
        ("120 s", 120),
        ("180 s", 180),
        ("300 s", 300),
    ]

    MODE_OPTIONS: list[tuple[str, str]] = [
        ("Sequential", "sequential"),
        ("Parallel — chapters", "parallel_chapters"),
        ("Parallel — chunks", "parallel_chunks"),
    ]

    def __init__(self, on_config_changed: Optional[Callable] = None) -> None:
        super().__init__()
        self.on_config_changed = on_config_changed
        self.config = TranslationConfig()

        # References to controls so we can read their values later
        self._agents_dd: Optional[ft.Dropdown] = None
        self._mode_radio: Optional[ft.RadioGroup] = None
        self._retries_dd: Optional[ft.Dropdown] = None
        self._timeout_dd: Optional[ft.Dropdown] = None

    def build(self) -> ft.Column:
        """Build the settings form."""
        self._agents_dd = ft.Dropdown(
            label="Parallel Translation Agents",
            value=str(self.config.max_agents),
            options=[
                ft.dropdown.Option(text=label, key=key)
                for label, key in self.AGENT_OPTIONS
            ],
            on_change=self._on_setting_changed,
        )

        self._retries_dd = ft.Dropdown(
            label="Max Retries",
            value=str(self.config.max_retries),
            options=[
                ft.dropdown.Option(text=label, key=key)
                for label, key in self.RETRY_OPTIONS
            ],
            on_change=self._on_setting_changed,
        )

        self._timeout_dd = ft.Dropdown(
            label="Timeout",
            value=f"{self.config.timeout_seconds} s",
            options=[
                ft.dropdown.Option(text=label, key=str(key))
                for label, key in self.TIMEOUT_OPTIONS
            ],
            on_change=self._on_setting_changed,
        )

        self._mode_radio = ft.RadioGroup(
            content=ft.Column(
                [
                    ft.Radio(
                        value=mode_value,
                        label=mode_label,
                    )
                    for mode_label, mode_value in self.MODE_OPTIONS
                ]
            ),
            value=self.config.translation_mode,
            on_change=self._on_setting_changed,
        )

        return ft.Column(
            controls=[
                ft.Text("Agent Settings", size=16, weight=ft.FontWeight.BOLD),
                self._agents_dd,
                ft.Divider(height=1),
                ft.Text("Translation Mode", size=14),
                self._mode_radio,
                ft.Divider(height=1),
                ft.Row(
                    controls=[self._retries_dd, self._timeout_dd],
                    spacing=10,
                ),
            ],
            spacing=10,
        )

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_setting_changed(self, e: ft.ControlEvent) -> None:
        """Read current widget values and update ``self.config``."""
        self.config.max_agents = int(self._agents_dd.value)
        self.config.max_retries = int(self._retries_dd.value)
        # timeout value stored as "<N> s" — parse the integer prefix
        timeout_str: str = self._timeout_dd.value
        self.config.timeout_seconds = int(timeout_str.split()[0])
        self.config.translation_mode = self._mode_radio.value

        if self.on_config_changed:
            self.on_config_changed(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> TranslationConfig:
        """Return the current :class:`TranslationConfig`."""
        return TranslationConfig(
            max_agents=self.config.max_agents,
            translation_mode=self.config.translation_mode,
            max_retries=self.config.max_retries,
            timeout_seconds=self.config.timeout_seconds,
        )

    def set_config(self, cfg: TranslationConfig) -> None:
        """Programmatically set all controls from a *cfg* object."""
        self.config = TranslationConfig(
            max_agents=cfg.max_agents,
            translation_mode=cfg.translation_mode,
            max_retries=cfg.max_retries,
            timeout_seconds=cfg.timeout_seconds,
        )
        if self._agents_dd is not None:
            self._agents_dd.value = str(self.config.max_agents)
            self._retries_dd.value = str(self.config.max_retries)
            self._timeout_dd.value = f"{self.config.timeout_seconds} s"
            self._mode_radio.value = self.config.translation_mode
            self.update()
