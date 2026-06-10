"""
Flet UI component for selecting target languages.

Provides a scrollable grid of language checkboxes backed by
:func:`app.core.language.get_supported_languages`.
"""

from __future__ import annotations

import flet as ft
from typing import Callable, List, Optional, Dict

from app.core.language import get_supported_languages, Language


class LanguageSelector(ft.UserControl):
    """Checkbox grid for choosing target translation languages.

    Parameters
    ----------
    on_languages_changed:
        Optional callback invoked whenever the selection changes.  It receives
        the component instance as argument so the caller can call
        :meth:`get_selected_languages` to obtain the current codes.
    """

    def __init__(self, on_languages_changed: Optional[Callable] = None) -> None:
        super().__init__()
        self.on_languages_changed = on_languages_changed
        self.selected_codes: List[str] = []
        self._checkboxes: Dict[str, ft.Checkbox] = {}

    def build(self) -> ft.Column:
        """Build the language selector UI."""
        languages = get_supported_languages()
        checkbox_controls: List[ft.Control] = []

        for lang in languages:
            cb = ft.Checkbox(
                label=f"{lang.name} ({lang.native_name})",
                value=False,
                on_change=self._on_checkbox_change,
                data=lang.code,  # store code in data attribute
            )
            self._checkboxes[lang.code] = cb
            checkbox_controls.append(cb)

        return ft.Column(
            controls=[
                ft.Text("Target Languages", size=16, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=checkbox_controls,
                    wrap=True,
                    spacing=10,
                    run_spacing=5,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_checkbox_change(self, e: ft.ControlEvent) -> None:
        """Update *selected_codes* and fire the callback."""
        cb: ft.Checkbox = e.control
        code: str = cb.data

        if cb.value and code not in self.selected_codes:
            self.selected_codes.append(code)
        elif not cb.value and code in self.selected_codes:
            self.selected_codes.remove(code)

        if self.on_languages_changed:
            self.on_languages_changed(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_languages(self) -> List[str]:
        """Return ISO 639-1 codes of all currently checked languages."""
        return list(self.selected_codes)

    def select_language(self, code: str) -> None:
        """Programmatically check the checkbox for *code*.

        Raises :exc:`KeyError` if *code* is not a supported language.
        """
        if code not in self._checkboxes:
            raise KeyError(f"Unsupported language code: {code!r}")
        if code not in self.selected_codes:
            self._checkboxes[code].value = True
            self.selected_codes.append(code)
            self.update()

    def deselect_language(self, code: str) -> None:
        """Programmatically un-check the checkbox for *code*.

        Silently ignored if *code* is not supported.
        """
        if code in self._checkboxes and code in self.selected_codes:
            self._checkboxes[code].value = False
            self.selected_codes.remove(code)
            self.update()

    def reset(self) -> None:
        """Un-check all language checkboxes."""
        for code, cb in self._checkboxes.items():
            cb.value = False
        self.selected_codes.clear()
        self.update()
