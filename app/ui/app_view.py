"""
KDP Translator — main Flet application view.

This module implements the primary window layout that orchestrates the
full translation workflow: file selection → language/title selection →
provider configuration → translation execution → output delivery.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import flet as ft

from app.core.config import AppConfig, TranslationConfig
from app.core.epub_processor import EpubAnalysis
from app.core.language import get_supported_languages, Language
from app.core.logger import get_logger, get_view_handler, LogViewHandler
from app.core.metadata import generate_output_filename
from app.core.validation import are_all_titles_confirmed, is_translation_ready
from app.providers.base import TranslationProvider
from app.providers.mock import MockTranslationProvider
from app.providers.ollamacloud import OllamaCloudProvider
from app.services.title_generator import TitleConfirmation, TitleSuggestion
from app.services.translation_service import TranslationService
from app.ui.agent_settings import AgentSettings
from app.ui.language_selector import LanguageSelector
from app.ui.log_view import LogView
from app.ui.progress_view import ProgressView
from app.ui.title_selector import TitleSelector

logger = get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROVIDER_MAP: Dict[str, type] = {
    "MockProvider": MockTranslationProvider,
    "OllamaCloud": OllamaCloudProvider,
}

# ---------------------------------------------------------------------------
# Main Application View
# ---------------------------------------------------------------------------


class AppView(ft.Column):
    """Main application view — the single-window Flet UI."""

    def __init__(self, page: ft.Page, service: TranslationService) -> None:
        super().__init__()
        self._page: ft.Page = page
        self._service: TranslationService = service

        # --- Internal state ---
        self._epub_analysis: Optional["EpubAnalysis"] = None
        self._epub_path: Optional[str] = None
        self._confirmations: Dict[str, TitleConfirmation] = {}
        self._provider: TranslationProvider = service.provider
        self._config: TranslationConfig = service.config
        self._selected_languages: List[str] = []
        self._proposed_titles: Dict[str, TitleSuggestion] = {}
        self._translation_running: bool = False
        self._translation_cancelled: bool = False
        self._output_paths: List[str] = []

        # --- UI references (filled by build_layout) ---
        self._file_path_text: Optional[ft.Text] = None
        self._file_picker: Optional[ft.FilePicker] = None
        self._provider_dropdown: Optional[ft.Dropdown] = None
        self._model_dropdown: Optional[ft.Dropdown] = None
        self._language_selector: Optional[LanguageSelector] = None
        self._agent_settings: Optional[AgentSettings] = None
        self._generate_titles_btn: Optional[ft.ElevatedButton] = None
        self._title_selectors_container: Optional[ft.Column] = None
        self._title_selectors: Dict[str, TitleSelector] = {}
        self._validation_status: Optional[ft.Text] = None
        self._start_btn: Optional[ft.ElevatedButton] = None
        self._cancel_btn: Optional[ft.ElevatedButton] = None
        self._progress_view: Optional[ProgressView] = None
        self._agent_status_grid: Optional[ft.Column] = None
        self._log_view: Optional[LogView] = None
        self._output_btn: Optional[ft.ElevatedButton] = None
        self._output_folder_text: Optional[ft.Text] = None

        # Build the full layout into self
        self.build_layout()

    # ======================================================================
    # Layout construction
    # ======================================================================

    def build_layout(self) -> None:
        """Build the complete UI layout as children of this Column."""
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self._page.overlay.append(self._file_picker)

        # --- Header ---
        header = ft.Row(
            controls=[
                ft.Text("KDP Translator", size=28, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        # --- File picker row ---
        self._file_path_text = ft.Text(
            "No file selected",
            italic=True,
            color=ft.Colors.GREY_600,
            expand=True,
        )
        file_picker_row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "Select EPUB",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda _: self._file_picker.pick_files(
                        allow_multiple=False,
                        allowed_extensions=["epub"],
                    ),
                ),
                self._file_path_text,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # --- Provider / Model selection ---
        self._provider_dropdown = ft.Dropdown(
            label="Provider",
            value=self._provider.name,
            options=[
                ft.dropdown.Option("MockProvider"),
                ft.dropdown.Option("OllamaCloud"),
            ],
            on_change=self._on_provider_changed,
            width=240,
        )
        self._model_dropdown = ft.Dropdown(
            label="Model",
            value=self._provider.supported_models[0]
            if self._provider.supported_models
            else "",
            options=[
                ft.dropdown.Option(m) for m in self._provider.supported_models
            ],
            on_change=self._on_model_changed,
            width=300,
        )
        provider_settings_row = ft.Row(
            controls=[self._provider_dropdown, self._model_dropdown],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        # --- Language selector ---
        self._language_selector = LanguageSelector(
            on_languages_changed=self._on_languages_changed,
        )

        # --- Agent settings ---
        self._agent_settings = AgentSettings(
            on_config_changed=self._on_agent_settings_changed,
        )

        # --- Generate Title Suggestions button ---
        self._generate_titles_btn = ft.ElevatedButton(
            "Generate Title Suggestions",
            icon=ft.Icons.EDIT,
            disabled=True,
            on_click=self._on_generate_titles,
        )

        # --- Title selectors (dynamically created) ---
        self._title_selectors_container = ft.Column(spacing=8)

        # --- Validation status ---
        self._validation_status = ft.Text(
            "Load an EPUB file to begin.",
            italic=True,
            color=ft.Colors.GREY_600,
        )

        # --- Action buttons ---
        self._start_btn = ft.ElevatedButton(
            "Start Translation",
            icon=ft.Icons.PLAY_ARROW,
            disabled=True,
            on_click=self._on_start_translation,
        )
        self._cancel_btn = ft.ElevatedButton(
            "Cancel",
            icon=ft.Icons.CANCEL,
            disabled=True,
            on_click=self._on_cancel_translation,
        )
        action_buttons_row = ft.Row(
            controls=[self._start_btn, self._cancel_btn],
            alignment=ft.MainAxisAlignment.START,
            spacing=12,
        )

        # --- Progress view ---
        self._progress_view = ProgressView()

        # --- Agent status display ---
        self._agent_status_grid = ft.Column(spacing=4)

        # --- Log view ---
        self._log_view = LogView()

        # --- Output button ---
        self._output_folder_text = ft.Text(
            "",
            italic=True,
            color=ft.Colors.GREY_600,
            expand=True,
        )
        self._output_btn = ft.ElevatedButton(
            "Open Output Folder",
            icon=ft.Icons.FOLDER_OPEN,
            disabled=True,
            on_click=self._open_output_folder,
        )
        output_row = ft.Row(
            controls=[self._output_btn, self._output_folder_text],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # --- Assemble the main column (populate self) ---
        self.controls = [
            header,
            ft.Divider(height=1),
            file_picker_row,
            ft.Divider(height=1),
            provider_settings_row,
            ft.Divider(height=1),
            self._language_selector,
            ft.Divider(height=1),
            self._agent_settings,
            ft.Divider(height=1),
            self._generate_titles_btn,
            self._title_selectors_container,
            self._validation_status,
            action_buttons_row,
            ft.Divider(height=1),
            self._progress_view,
            self._agent_status_grid,
            ft.Divider(height=1),
            self._log_view,
            ft.Divider(height=1),
            output_row,
        ]
        self.spacing = 8

    # ======================================================================
    # Event handlers
    # ======================================================================

    # -- File picker --------------------------------------------------------

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Handle EPUB file selection."""
        if e.files and len(e.files) > 0:
            path = e.files[0].path
            self._epub_path = path
            self._file_path_text.value = path
            self._file_path_text.color = ft.Colors.BLACK87
            self._file_path_text.italic = False
            self._page.update()

            self._load_epub(path)

    def _load_epub(self, path: str) -> None:
        """Analyse the selected EPUB file and update UI state."""
        # Reset previous state
        self._reset_state()

        try:
            logger.info("Analysing EPUB: %s", path)
            self._file_path_text.value = f"Loading: {path} ..."
            self._file_path_text.italic = True
            self._page.update()

            analysis = self._service.analyze_epub(path)
            self._epub_analysis = analysis

            self._file_path_text.value = (
                f"Loaded: {analysis.title} "
                f"({len(analysis.chapters)} chapters, {analysis.language})"
            )
            self._file_path_text.color = ft.Colors.GREEN_700
            self._file_path_text.italic = False

            logger.info(
                "EPUB analysed — title=%r language=%s chapters=%d",
                analysis.title,
                analysis.language,
                len(analysis.chapters),
            )
        except Exception as exc:
            logger.error("Failed to load EPUB: %s", exc)
            self._file_path_text.value = f"Error: {exc}"
            self._file_path_text.color = ft.Colors.RED_700
            self._file_path_text.italic = True

        self._update_ui_state()

    # -- Provider / Model ---------------------------------------------------

    def _on_provider_changed(self, e: ft.ControlEvent) -> None:
        """Handle provider dropdown change — rebuild provider and models."""
        provider_name = self._provider_dropdown.value
        self._switch_provider(provider_name)

    def _switch_provider(self, provider_name: str) -> None:
        """Create a new provider instance and update the service."""
        provider_class = _PROVIDER_MAP.get(provider_name)
        if provider_class is None:
            logger.warning("Unknown provider: %s", provider_name)
            return

        try:
            if provider_class is MockTranslationProvider:
                new_provider = MockTranslationProvider()
            else:
                new_provider = provider_class()

            self._provider = new_provider

            # Update model dropdown
            self._model_dropdown.options = [
                ft.dropdown.Option(m) for m in new_provider.supported_models
            ]
            if new_provider.supported_models:
                self._model_dropdown.value = new_provider.supported_models[0]
            else:
                self._model_dropdown.value = ""
            self._model_dropdown.update()

            # Rebuild service with new provider
            self._service = TranslationService(
                provider=new_provider,
                config=self._config,
            )
            # Re-analyse the current EPUB if one was loaded
            if self._epub_path and self._epub_analysis is not None:
                try:
                    self._service.analyze_epub(self._epub_path)
                except Exception as exc:
                    logger.warning(
                        "Re-analysis after provider change failed: %s", exc
                    )

            logger.info("Switched provider to %s", provider_name)
        except Exception as exc:
            logger.error("Failed to switch provider: %s", exc)

        self._update_ui_state()

    def _on_model_changed(self, e: ft.ControlEvent) -> None:
        """Handle model dropdown change — update provider model if applicable."""
        model = self._model_dropdown.value
        logger.info("Model changed to: %s", model)
        # Some providers don't support dynamic model switching after
        # construction; we recreate the provider with the new model.
        provider_type = type(self._provider)
        if provider_type in (OllamaCloudProvider,):
            try:
                new_provider = provider_type(model=model)
                self._provider = new_provider
                self._service = TranslationService(
                    provider=new_provider,
                    config=self._config,
                )
                if self._epub_path and self._epub_analysis is not None:
                    try:
                        self._service.analyze_epub(self._epub_path)
                    except Exception as exc:
                        logger.warning(
                            "Re-analysis after model change failed: %s", exc
                        )
                logger.info("Switched model to %s", model)
            except Exception as exc:
                logger.error("Failed to switch model: %s", exc)

    # -- Languages ----------------------------------------------------------

    def _on_languages_changed(self, component: LanguageSelector) -> None:
        """Handle language selection changes.

        Called by LanguageSelector when the user adds/removes languages.
        """
        selected_codes = component.get_selected_languages()
        self._selected_languages = selected_codes

        # Remove confirmations for languages no longer selected
        removed = set(self._confirmations.keys()) - set(selected_codes)
        for code in removed:
            del self._confirmations[code]
            self._proposed_titles.pop(code, None)
            # Remove title selector widget
            ts = self._title_selectors.pop(code, None)
            if ts is not None:
                self._title_selectors_container.controls.remove(ts)

        # Rebuild title selector controls to match current selection
        self._rebuild_title_selectors()
        self._update_ui_state()

    # -- Agent settings ----------------------------------------------------

    def _on_agent_settings_changed(self, component: AgentSettings) -> None:
        """Handle updates to agent/settings configuration."""
        self._config = component.get_config()
        # Update the service config
        self._service = TranslationService(
            provider=self._provider,
            config=self._config,
        )
        if self._epub_path and self._epub_analysis is not None:
            try:
                self._service.analyze_epub(self._epub_path)
            except Exception as exc:
                logger.warning(
                    "Re-analysis after config change failed: %s", exc
                )
        logger.info(
            "Agent settings updated — max_agents=%d mode=%s retries=%d timeout=%d",
            config.max_agents,
            config.translation_mode,
            config.max_retries,
            config.timeout_seconds,
        )

    # -- Title generation --------------------------------------------------

    def _on_generate_titles(self, e: ft.ControlEvent) -> None:
        """Generate title suggestions for all selected languages."""
        if self._epub_analysis is None:
            self._validation_status.value = (
                "No EPUB loaded. Please select a file first."
            )
            self._validation_status.color = ft.Colors.RED_700
            self._page.update()
            return

        if not self._selected_languages:
            self._validation_status.value = (
                "No languages selected. Please select at least one target language."
            )
            self._validation_status.color = ft.Colors.RED_700
            self._page.update()
            return

        analysis = self._epub_analysis
        self._generate_titles_btn.disabled = True
        self._generate_titles_btn.text = "Generating..."
        self._validation_status.value = "Generating title suggestions..."
        self._validation_status.color = ft.Colors.BLUE_700
        self._page.update()

        def _generate() -> None:
            """Run title generation in a background thread."""
            try:
                for lang_code in self._selected_languages:
                    try:
                        suggestions = self._service.generate_titles(
                            analysis=analysis,
                            language=lang_code,
                        )
                        self._proposed_titles[lang_code] = suggestions
                        logger.info(
                            "Titles generated for %s: literal=%r market=%r seo=%r",
                            lang_code,
                            suggestions.literal,
                            suggestions.market,
                            suggestions.seo,
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to generate titles for %s: %s",
                            lang_code,
                            exc,
                        )
                        self._page.post(lambda: self._show_title_error(
                            lang_code, str(exc)
                        ))
                        return

                # All successful — update UI
                self._page.post(self._on_titles_generated)
            except Exception as exc:
                logger.error("Title generation thread error: %s", exc)
                self._page.post(lambda: self._show_title_error(
                    "all", str(exc)
                ))

        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()

    def _show_title_error(self, lang_code: str, error: str) -> None:
        """Display a title generation error in the UI."""
        self._generate_titles_btn.disabled = False
        self._generate_titles_btn.text = "Generate Title Suggestions"
        self._validation_status.value = (
            f"Title generation failed for {lang_code}: {error}"
        )
        self._validation_status.color = ft.Colors.RED_700
        self._page.update()

    def _on_titles_generated(self) -> None:
        """Callback after all titles have been generated successfully."""
        self._generate_titles_btn.disabled = False
        self._generate_titles_btn.text = "Generate Title Suggestions"
        self._validation_status.value = (
            "Title suggestions generated. Please confirm a title for each language."
        )
        self._validation_status.color = ft.Colors.GREEN_700

        # Rebuild title selectors with the new suggestions
        self._rebuild_title_selectors()
        self._update_ui_state()

    # -- Title confirmation -------------------------------------------------

    def _on_title_confirmed(
        self,
        language_code: str,
        confirmation: TitleConfirmation,
    ) -> None:
        """Handle a title confirmation from a TitleSelector widget."""
        if confirmation.confirmed:
            self._confirmations[language_code] = confirmation
            logger.info(
                "Title confirmed for %s: %s (type=%s)",
                language_code,
                confirmation.selected_title,
                confirmation.selection_type,
            )
        else:
            # User unconfirmed — remove from confirmations
            self._confirmations.pop(language_code, None)

        self._update_ui_state()

    # -- Title selector management -----------------------------------------

    def _rebuild_title_selectors(self) -> None:
        """Rebuild the TitleSelector widgets for each selected language."""
        self._title_selectors_container.controls.clear()
        self._title_selectors.clear()

        for lang_code in self._selected_languages:
            lang = None
            for l in get_supported_languages():
                if l.code == lang_code:
                    lang = l
                    break

            suggestions = self._proposed_titles.get(lang_code)
            existing_confirmation = self._confirmations.get(lang_code)

            selector = TitleSelector(
                language_code=lang.code,
                language_name=lang.name,
                suggestions=suggestions,
                on_confirmed=self._on_title_confirmed,
            )
            self._title_selectors[lang_code] = selector
            self._title_selectors_container.controls.append(selector)

        self._title_selectors_container.update()
        self._page.update()

    # -- Translation -------------------------------------------------------

    def _on_start_translation(self, e: ft.ControlEvent) -> None:
        """Start the translation process."""
        if self._translation_running:
            logger.warning("Translation already in progress.")
            return

        if self._epub_analysis is None:
            self._validation_status.value = "No EPUB loaded."
            self._validation_status.color = ft.Colors.RED_700
            self._page.update()
            return

        ready, msg = is_translation_ready(
            confirmations=self._confirmations,
            selected_languages=self._selected_languages,
            epub_loaded=True,
        )
        if not ready:
            self._validation_status.value = msg
            self._validation_status.color = ft.Colors.RED_700
            self._page.update()
            return

        self._translation_running = True
        self._translation_cancelled = False
        self._output_paths = []
        self._start_btn.disabled = True
        self._cancel_btn.disabled = False
        self._generate_titles_btn.disabled = True
        self._validation_status.value = "Translation in progress..."
        self._validation_status.color = ft.Colors.BLUE_700
        self._progress_view.reset()
        self._progress_view.set_visible(True)
        self._page.update()

        analysis = self._epub_analysis

        def _translate() -> None:
            """Run translation in a background thread."""
            try:
                results = self._service.start_translation(
                    analysis=analysis,
                    confirmations=self._confirmations,
                    on_progress=self._on_translation_progress,
                    on_agent_update=self._on_agent_update,
                )

                if self._translation_cancelled:
                    self._page.post(self._on_translation_cancelled)
                    return

                # Save each translated EPUB
                saved_paths: List[str] = []
                for lang_code in self._selected_languages:
                    try:
                        confirmation = self._confirmations.get(lang_code)
                        filename = generate_output_filename(
                            original_title=analysis.title,
                            language_code=lang_code,
                            use_title=bool(
                                confirmation and confirmation.confirmed
                            ),
                        )
                        output_dir = AppConfig.OUTPUT_DIR
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = str(output_dir / filename)

                        saved = self._service.save_translated_epub(
                            output_path=output_path,
                            analysis=analysis,
                            language=lang_code,
                            title_confirmation=confirmation,
                        )
                        saved_paths.append(saved)
                        logger.info("Saved: %s", saved)
                    except Exception as exc:
                        logger.error(
                            "Failed to save EPUB for %s: %s",
                            lang_code,
                            exc,
                        )

                self._output_paths = saved_paths
                self._page.post(self._on_translation_completed)
            except Exception as exc:
                logger.error("Translation error: %s", exc)
                self._page.post(lambda: self._on_translation_error(str(exc)))

        thread = threading.Thread(target=_translate, daemon=True)
        thread.start()

    def _on_translation_progress(self, completed: int, total: int) -> None:
        """Callback for progress updates from the translation service.

        This is called from a background thread — use page.post to update
        the UI safely.
        """
        if total > 0:
            pct = round(completed / total * 100, 1)
        else:
            pct = 0.0

        self._page.post(
            lambda: self._progress_view.update_overall(completed, total)
        )

    def _on_agent_update(self, agents_status: List[Dict[str, Any]]) -> None:
        """Callback for agent status updates from the translation service."""
        self._page.post(
            lambda: self._refresh_agent_status(agents_status)
        )

    def _refresh_agent_status(
        self, agents_status: List[Dict[str, Any]]
    ) -> None:
        """Update the agent status display with current agent states."""
        self._agent_status_grid.controls.clear()

        if not agents_status:
            self._agent_status_grid.controls.append(
                ft.Text("No active agents", italic=True, color=ft.Colors.GREY_600)
            )
        else:
            for agent in agents_status:
                agent_id = agent.get("agent_id", "?")
                status = agent.get("status", "?")
                lang = agent.get("current_language", "")
                chapter = agent.get("current_chapter", "")
                progress_val = agent.get("progress", 0.0)

                # Determine color based on status
                status_lower = str(status).lower()
                if status_lower == "completed":
                    color = ft.Colors.GREEN_700
                elif status_lower == "error":
                    color = ft.Colors.RED_700
                elif status_lower in ("working",):
                    color = ft.Colors.BLUE_700
                elif status_lower == "retry":
                    color = ft.Colors.ORANGE_700
                else:
                    color = ft.Colors.GREY_700

                row = ft.Row(
                    controls=[
                        ft.Text(f"[{agent_id}]", weight=ft.FontWeight.BOLD, width=80),
                        ft.Text(
                            str(status),
                            color=color,
                            weight=ft.FontWeight.W_500,
                            width=100,
                        ),
                        ft.Text(lang or "", width=40),
                        ft.Text(f"ch:{chapter or '-'}", width=120),
                        ft.ProgressBar(
                            value=progress_val,
                            width=120,
                            color=color,
                        ),
                    ],
                    spacing=4,
                )
                self._agent_status_grid.controls.append(row)

        self._agent_status_grid.update()

    def _on_translation_completed(self) -> None:
        """Handle successful completion of translation."""
        self._translation_running = False
        self._start_btn.disabled = False
        self._cancel_btn.disabled = True
        self._generate_titles_btn.disabled = False

        if self._output_paths:
            path_list = "\n".join(self._output_paths)
            self._validation_status.value = (
                f"Translation completed successfully!\nSaved:\n{path_list}"
            )
            self._validation_status.color = ft.Colors.GREEN_700
            self._output_btn.disabled = False
            self._output_folder_text.value = (
                f"Output folder: {AppConfig.OUTPUT_DIR}"
            )
            self._output_folder_text.color = ft.Colors.BLACK87
            self._output_folder_text.italic = False
        else:
            self._validation_status.value = (
                "Translation completed but no output files were saved."
            )
            self._validation_status.color = ft.Colors.ORANGE_700

        self._progress_view.set_visible(False)
        self._page.update()

    def _on_translation_error(self, error: str) -> None:
        """Handle a translation error."""
        self._translation_running = False
        self._start_btn.disabled = False
        self._cancel_btn.disabled = True
        self._generate_titles_btn.disabled = False
        self._validation_status.value = f"Translation failed: {error}"
        self._validation_status.color = ft.Colors.RED_700
        self._progress_view.set_visible(False)
        self._page.update()

    def _on_cancel_translation(self, e: ft.ControlEvent) -> None:
        """Cancel the in-progress translation."""
        logger.info("User requested cancellation.")
        self._translation_cancelled = True
        self._service.cancel_all()
        self._cancel_btn.disabled = True
        self._cancel_btn.text = "Cancelling..."
        self._validation_status.value = "Cancelling translation..."
        self._validation_status.color = ft.Colors.ORANGE_700
        self._page.update()

    def _on_translation_cancelled(self) -> None:
        """Handle post-cancellation state."""
        self._translation_running = False
        self._start_btn.disabled = False
        self._cancel_btn.disabled = True
        self._cancel_btn.text = "Cancel"
        self._generate_titles_btn.disabled = False
        self._validation_status.value = "Translation cancelled by user."
        self._validation_status.color = ft.Colors.ORANGE_700
        self._progress_view.set_visible(False)
        self._page.update()

    # -- Output folder -----------------------------------------------------

    def _open_output_folder(self, e: ft.ControlEvent) -> None:
        """Open the output folder in the system file manager."""
        output_dir = AppConfig.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            path_str = str(output_dir.resolve())
            logger.info("Opening output folder: %s", path_str)
            self._page.launch_url(path_str)
        except Exception as exc:
            logger.error("Failed to open output folder: %s", exc)
            self._validation_status.value = (
                f"Could not open folder: {exc}"
            )
            self._validation_status.color = ft.Colors.RED_700
            self._page.update()

    # ======================================================================
    # UI state management
    # ======================================================================

    def _update_ui_state(self) -> None:
        """Enable/disable buttons and update validation text based on current state."""
        epub_loaded = self._epub_analysis is not None
        has_languages = len(self._selected_languages) > 0

        # Generate titles: enabled when EPUB loaded and languages selected
        self._generate_titles_btn.disabled = (
            not epub_loaded or not has_languages or self._translation_running
        )

        # Start translation: enabled when all titles confirmed and ready
        if epub_loaded and has_languages and not self._translation_running:
            ready, msg = is_translation_ready(
                confirmations=self._confirmations,
                selected_languages=self._selected_languages,
                epub_loaded=True,
            )
            self._start_btn.disabled = not ready
            if ready:
                self._validation_status.value = (
                    "Ready to start translation."
                )
                self._validation_status.color = ft.Colors.GREEN_700
            elif msg:
                self._validation_status.value = msg
                self._validation_status.color = ft.Colors.GREY_700
        elif not epub_loaded:
            self._validation_status.value = (
                "Load an EPUB file to begin."
            )
            self._validation_status.color = ft.Colors.GREY_600
            self._start_btn.disabled = True
        elif not has_languages:
            self._validation_status.value = (
                "Select at least one target language."
            )
            self._validation_status.color = ft.Colors.GREY_600
            self._start_btn.disabled = True

        self._page.update()
    # ======================================================================
    # Helpers
    # ======================================================================

    def _reset_state(self) -> None:
        """Reset all workflow state (called when a new EPUB is loaded)."""
        self._epub_analysis = None
        self._confirmations.clear()
        self._proposed_titles.clear()
        self._selected_languages = []
        self._output_paths = []
        self._translation_running = False
        self._translation_cancelled = False

        # Clear title selectors
        self._title_selectors_container.controls.clear()
        self._title_selectors.clear()

        # Reset UI sub-components
        self._language_selector.reset()
        self._progress_view.reset()
        self._progress_view.set_visible(False)
        self._agent_status_grid.controls.clear()
        self._log_view.clear()
        self._output_btn.disabled = True
        self._output_folder_text.value = ""
        self._output_folder_text.color = ft.Colors.GREY_600
        self._output_folder_text.italic = True

        self._page.update()
