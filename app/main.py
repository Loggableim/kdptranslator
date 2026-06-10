"""
KDP Translator — Main Entry Point.

A local desktop application for KDP publishers that translates complete EPUB
books into multiple languages using AI language models.

Usage:
    python -m app.main
    (or from the project root:  flet run app/main.py)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path when running via `python -m app.main`
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import flet as ft

from app.core.config import AppConfig, TranslationConfig
from app.core.logger import setup_logging, get_logger, get_view_handler
from app.providers.mock import MockTranslationProvider
from app.providers.ollamacloud import OllamaCloudProvider
from app.services.translation_service import TranslationService
from app.ui.app_view import AppView


def main(page: ft.Page) -> None:
    """Flet application entry point."""
    # --- Page setup ---
    page.title = "KDP Translator"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1100
    page.window.height = 900
    page.window.min_width = 900
    page.window.min_height = 700
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # --- Configuration ---
    app_config = AppConfig.load()
    app_config.ensure_directories()

    # --- Logging ---
    setup_logging(
        level=app_config.log_level,
        log_file=str(app_config.log_file),
    )
    logger = get_logger()
    logger.info("KDP Translator starting …")

    # --- Translation service ---
    # Start with MockProvider so the app works without any API key
    provider = MockTranslationProvider()
    config = TranslationConfig(
        max_agents=app_config.translation_config().max_agents,
        translation_mode=app_config.translation_config().translation_mode,
        max_retries=app_config.translation_config().max_retries,
        timeout_seconds=app_config.translation_config().timeout_seconds,
    )
    service = TranslationService(provider=provider, config=config)

    # --- Build UI ---
    app_view = AppView(page, service)
    page.add(app_view)

    logger.info("UI ready — waiting for user input")
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
