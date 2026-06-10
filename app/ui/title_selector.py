"""
Title Selector UI component for KDP Translator.

Presents the user with three auto-generated title options (literal, market,
SEO-optimised) plus a custom title field, and collects the user's
confirmation into a TitleConfirmation dataclass.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable

import flet as ft

from app.services.title_generator import TitleConfirmation, TitleSuggestion

logger = logging.getLogger(__name__)


class TitleSelector(ft.UserControl):
    """Flet component for selecting and confirming a title per language.

    Displays the three suggestion variants from a TitleSuggestion (literal,
    market, SEO) as radio options, plus a custom-title text field.  When the
    user clicks "Confirm Title" the component builds a TitleConfirmation and
    fires the *on_confirmed* callback.

    Parameters
    ----------
    language_code:
        ISO 639-1 code (e.g. ``"de"``, ``"fr"``).
    language_name:
        Human-readable name (e.g. ``"German"``, ``"French"``).
    suggestions:
        The three-variant :class:`TitleSuggestion` to display.
    on_confirmed:
        Optional callback ``(language_code, TitleConfirmation)`` invoked
        when the user confirms a title.
    """

    def __init__(
        self,
        language_code: str,
        language_name: str,
        suggestions: TitleSuggestion,
        on_confirmed: Optional[Callable[[str, TitleConfirmation], None]] = None,
    ) -> None:
        super().__init__()
        self.language_code: str = language_code
        self.language_name: str = language_name
        self.suggestions: TitleSuggestion = suggestions
        self.on_confirmed: Optional[Callable[[str, TitleConfirmation], None]] = (
            on_confirmed
        )

        # --- Internal state ---
        self._confirmation: Optional[TitleConfirmation] = None
        self._selected_type: str = "market"
        self._custom_title: str = ""

        # --- Refs for dynamic updates ---
        self._status_ref = ft.Ref[ft.Text]()
        self._custom_field_ref = ft.Ref[ft.TextField]()
        self._confirm_btn_ref = ft.Ref[ft.ElevatedButton]()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> ft.Control:
        """Construct the control tree."""
        return ft.Column(
            controls=[
                # Language header
                ft.Text(
                    f"{self.language_name} ({self.language_code})",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                ),
                # Radio group with the three suggestion variants
                ft.RadioGroup(
                    content=ft.Column(
                        controls=[
                            ft.Radio(
                                value="literal",
                                label=f"Literal: {self.suggestions.literal}",
                            ),
                            ft.Radio(
                                value="market",
                                label=f"Market Optimized: {self.suggestions.market}",
                            ),
                            ft.Radio(
                                value="seo",
                                label=f"SEO Optimized: {self.suggestions.seo}",
                            ),
                        ],
                        spacing=4,
                    ),
                    value="market",
                    on_change=self._on_radio_change,
                ),
                # Custom title text field
                ft.TextField(
                    ref=self._custom_field_ref,
                    label="Custom Title",
                    hint_text="Enter a custom title…",
                    on_change=self._on_custom_title_change,
                ),
                # Action row
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            ref=self._confirm_btn_ref,
                            text="Confirm Title",
                            on_click=self._on_confirm,
                        ),
                    ],
                    spacing=8,
                ),
                # Status indicator
                ft.Text(
                    ref=self._status_ref,
                    value="⚠ Not confirmed",
                    size=12,
                    italic=True,
                ),
                ft.Divider(height=1, color=ft.Colors.GREY_300),
            ],
            spacing=8,
            width=500,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_radio_change(self, e: ft.ControlEvent) -> None:
        """Store the selected radio option type."""
        self._selected_type = e.control.value
        logger.debug(
            "TitleSelector (%s) — radio changed to %r",
            self.language_code,
            self._selected_type,
        )

    def _on_custom_title_change(self, e: ft.ControlEvent) -> None:
        """Store the custom-title field value."""
        self._custom_title = e.control.value or ""

    def _on_confirm(self, e: ft.ControlEvent) -> None:
        """Build a TitleConfirmation and call the on_confirmed callback."""
        # Determine which suggested title to use as base
        if self._selected_type == "literal":
            selected_title = self.suggestions.literal
        elif self._selected_type == "market":
            selected_title = self.suggestions.market
        elif self._selected_type == "seo":
            selected_title = self.suggestions.seo
        else:
            selected_title = self._selected_type  # fallback — should not happen

        # If custom title field is non-empty, it takes priority
        custom_text = self._custom_title.strip()
        if custom_text:
            selected_title = custom_text
            selection_type = "custom"
        else:
            selection_type = self._selected_type

        self._confirmation = TitleConfirmation(
            language_code=self.language_code,
            selected_title=selected_title,
            selection_type=selection_type,
            confirmed=True,
            suggestions=self.suggestions,
        )

        # Update status indicator
        if self._status_ref.current is not None:
            self._status_ref.current.value = f"✓ Confirmed: {selected_title}"
            self._status_ref.current.color = ft.Colors.GREEN
            self._status_ref.current.italic = False
            self._status_ref.current.update()

        # Disable confirm button so user cannot double-confirm
        if self._confirm_btn_ref.current is not None:
            self._confirm_btn_ref.current.disabled = True
            self._confirm_btn_ref.current.update()

        logger.info(
            "Title confirmed for %s — type=%r title=%r",
            self.language_code,
            selection_type,
            selected_title,
        )

        # Fire callback
        if self.on_confirmed is not None:
            self.on_confirmed(self.language_code, self._confirmation)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_confirmation(self) -> Optional[TitleConfirmation]:
        """Return the current :class:`TitleConfirmation`, or *None* if not
        yet confirmed."""
        return self._confirmation

    @property
    def is_confirmed(self) -> bool:
        """``True`` once the title has been confirmed."""
        return self._confirmation is not None and self._confirmation.confirmed
