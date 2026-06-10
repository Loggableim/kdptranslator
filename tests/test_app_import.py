"""Test that the app module imports without errors."""
import sys
import pathlib
import py_compile

import pytest


def test_import_epub_processor():
    """EpubProcessor import works."""
    from app.core.epub_processor import EpubProcessor, analyze_epub
    from app.core.epub_processor import generate_output_filename

    assert EpubProcessor is not None
    assert callable(analyze_epub)
    assert callable(generate_output_filename)


def test_import_all_providers():
    """All providers import without errors."""
    from app.providers.base import TranslationProvider
    from app.providers.mock import MockTranslationProvider
    from app.providers.ollamacloud import OllamaCloudProvider

    assert TranslationProvider is not None
    assert MockTranslationProvider is not None
    assert OllamaCloudProvider is not None


def test_import_all_core():
    """All core modules import without errors."""
    from app.core.config import AppConfig, TranslationConfig
    from app.core.chunker import Chunk, chunk_text, merge_chunks, validate_chunk_order
    from app.core.html_translator import extract_text_chunks, apply_translation
    from app.core.language import get_supported_languages, Language
    from app.core.logger import get_logger, setup_logging, get_view_handler
    from app.core.metadata import sanitize_filename
    from app.core.validation import are_all_titles_confirmed, is_translation_ready

    assert all([
        AppConfig, TranslationConfig,
        Chunk, chunk_text, merge_chunks, validate_chunk_order,
        extract_text_chunks, apply_translation,
        get_supported_languages, Language,
        get_logger, setup_logging, get_view_handler,
        sanitize_filename,
        are_all_titles_confirmed, is_translation_ready,
    ])


def test_import_all_services():
    """All service modules import without errors."""
    from app.services.translation_service import TranslationService
    from app.services.translation_scheduler import TranslationScheduler
    from app.services.agent_pool import AgentPool, Agent, AgentStatus
    from app.services.title_generator import (
        TitleGenerator,
        TitleSuggestion,
        TitleConfirmation,
    )

    assert all([
        TranslationService,
        TranslationScheduler,
        AgentPool, Agent, AgentStatus,
        TitleGenerator, TitleSuggestion, TitleConfirmation,
    ])


def test_import_app_main():
    """import app.main must not raise ImportError (requires flet)."""
    pytest.importorskip("flet")

    # Clear any cached modules so we force a fresh import from disk
    for mod in list(sys.modules.keys()):
        if mod.startswith("app."):
            del sys.modules[mod]
    if "app" in sys.modules:
        del sys.modules["app"]

    from app.main import main

    assert callable(main)


def test_import_all_ui():
    """All UI components import without errors (requires flet)."""
    pytest.importorskip("flet")

    from app.ui.language_selector import LanguageSelector
    from app.ui.title_selector import TitleSelector
    from app.ui.agent_settings import AgentSettings
    from app.ui.progress_view import ProgressView
    from app.ui.log_view import LogView

    assert all([
        LanguageSelector,
        TitleSelector,
        AgentSettings,
        ProgressView,
        LogView,
    ])


def test_compile_all():
    """All app modules compile without syntax errors."""
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    errors = []
    for pyfile in sorted(app_dir.rglob("*.py")):
        try:
            py_compile.compile(str(pyfile), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))

    if errors:
        pytest.fail(
            "Compile errors found:\n" + "\n".join(errors)
        )
