"""
Translation Service — high-level orchestrator for the KDP translation pipeline.

Wires together the :class:`TranslationProvider`, :class:`AgentPool`,
:class:`TranslationScheduler`, and :class:`TitleGenerator` into a
convenient one-stop entry point for the UI layer.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from app.core.config import TranslationConfig
from app.core.epub_processor import EpubAnalysis, EpubProcessor
from app.core.logger import get_logger
from app.providers.base import TranslationProvider
from app.services.agent_pool import AgentPool
from app.services.title_generator import TitleConfirmation, TitleGenerator, TitleSuggestion
from app.services.translation_scheduler import TranslationScheduler

logger = get_logger()


class TranslationService:
    """High-level orchestrator for the KDP translation pipeline.

    Usage::

        service = TranslationService(provider=my_provider, config=config)

        # 1. Analyse the EPUB
        analysis = service.analyze_epub("input.epub")

        # 2. Generate title suggestions for a target language
        suggestions = service.generate_titles(analysis, "de")

        # 3. User picks a title, we build a confirmation
        confirmation = TitleConfirmation(
            language_code="de",
            selected_title=suggestions.market,
            selection_type="market",
            confirmed=True,
            suggestions=suggestions,
        )

        # 4. Start translation
        results = service.start_translation(
            analysis=analysis,
            confirmations={"de": confirmation},
            on_progress=lambda done, total: print(f"{done}/{total}"),
        )

        # 5. Save the result
        service.save_translated_epub("output.de.epub", analysis, "de", confirmation)
    """

    def __init__(
        self,
        provider: TranslationProvider,
        config: TranslationConfig,
    ) -> None:
        if provider is None:
            raise ValueError("provider must not be None")
        if config is None:
            raise ValueError("config must not be None")

        self._provider: TranslationProvider = provider
        self._config: TranslationConfig = config

        # --- Create sub-components ---
        self.agent_pool: AgentPool = AgentPool(
            max_agents=config.max_agents,
            provider=provider,
        )

        self.title_generator: TitleGenerator = TitleGenerator(provider=provider)

        # Scheduler — we create it without an EpubProcessor; one will be
        # set when analyze_epub() is called.
        self.scheduler: TranslationScheduler = TranslationScheduler(
            agent_pool=self.agent_pool,
            chunker_module=None,  # unused; we import chunker directly
            html_translator_module=None,
            epub_processor=None,
        )
        self.scheduler.set_provider(provider)

        # --- Internal state ---
        self._epub_processor: Optional[EpubProcessor] = None
        self._current_filepath: Optional[str] = None

    # ------------------------------------------------------------------
    # EPUB analysis
    # ------------------------------------------------------------------

    def analyze_epub(self, filepath: str) -> EpubAnalysis:
        """Load, analyse, and return metadata / chapters for *filepath*.

        The internal :class:`EpubProcessor` is retained so that
        :meth:`start_translation` and :meth:`save_translated_epub` can
        update and write the EPUB.
        """
        processor = EpubProcessor(filepath)
        processor.get_chapters()
        analysis = processor.analyse()

        self._epub_processor = processor
        self._current_filepath = filepath

        # Wire the processor into the scheduler
        self.scheduler.epub_processor = processor

        logger.info(
            "Analysed EPUB — title=%r language=%s chapters=%d",
            analysis.title,
            analysis.language,
            len(analysis.chapters),
        )
        return analysis

    # ------------------------------------------------------------------
    # Title generation
    # ------------------------------------------------------------------

    def generate_titles(
        self,
        analysis: EpubAnalysis,
        language: str,
        sample_content: Optional[str] = None,
    ) -> TitleSuggestion:
        """Generate title suggestions for *language* from the EPUB analysis.

        Parameters
        ----------
        analysis:
            Result of a previous :meth:`analyze_epub` call.
        language:
            ISO 639-1 target language code.
        sample_content:
            Optional short excerpt to help the provider tailor
            suggestions.

        Returns
        -------
        A :class:`TitleSuggestion` with literal, market, and SEO variants.
        """
        return self.title_generator.generate(
            original_title=analysis.title,
            subtitle=analysis.subtitle or None,
            description=analysis.description or "",
            genre=analysis.genre or "",
            target_language=language,
            sample_content=sample_content,
        )

    def get_translation_context(
        self, confirmation: TitleConfirmation
    ) -> str:
        """Return a context string for the translation provider.

        This is a convenience wrapper around
        :meth:`TitleGenerator.get_translation_context`.
        """
        return TitleGenerator.get_translation_context(confirmation)

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def start_translation(
        self,
        analysis: EpubAnalysis,
        confirmations: Dict[str, TitleConfirmation],
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_agent_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> Dict[str, bool]:
        """Translate the loaded EPUB into one or more target languages.

        Each language is translated from the **original** EPUB content.
        A fresh :class:`EpubProcessor` is created per language so that
        earlier translations never contaminate later ones.

        Parameters
        ----------
        analysis:
            Result of a previous :meth:`analyze_epub` call.
        confirmations:
            Dict mapping language codes (e.g. ``"de"``, ``"fr"``) to
            their respective :class:`TitleConfirmation` objects.
        on_progress:
            Optional callback ``(completed, total)`` invoked after each
            chunk translation.
        on_agent_update:
            Optional callback ``(agents_status)`` invoked whenever an
            agent's state changes.

        Returns
        -------
        Dict mapping each language code to a boolean success indicator.

        Raises
        ------
        RuntimeError
            If :meth:`analyze_epub` has not been called first.
        """
        if self._epub_processor is None:
            raise RuntimeError(
                "No EPUB loaded. Call analyze_epub() before start_translation()."
            )

        logger.info(
            "Starting translation for %d language(s): %s",
            len(confirmations),
            list(confirmations.keys()),
        )

        results: Dict[str, bool] = {}

        # Share the cancellation flag across all per-language schedulers
        # so that cancel_all() stops all in-flight work.
        cancel_flag = self.scheduler._cancel_flag

        for lang, confirmation in confirmations.items():
            if cancel_flag.is_set():
                logger.warning(
                    "Skipping language '%s' — cancellation in progress", lang
                )
                results[lang] = False
                continue

            logger.info("Starting translation for language '%s'", lang)

            # 1. Create a fresh EpubProcessor from the original file so
            #    this language translates the ORIGINAL content, not a
            #    previously-mutated version.
            processor = EpubProcessor(self._current_filepath)
            processor.get_chapters()

            # 2. Create a temporary scheduler wired to the fresh processor
            temp_scheduler = TranslationScheduler(
                agent_pool=self.agent_pool,
                chunker_module=None,
                html_translator_module=None,
                epub_processor=processor,
            )
            temp_scheduler.set_provider(self._provider)
            # Share the same cancellation event so cancel_all() works
            temp_scheduler._cancel_flag = cancel_flag

            # 3. Run translation on the fresh processor
            ok = temp_scheduler.schedule_translation(
                epub_analysis=analysis,
                target_language=lang,
                title_confirmation=confirmation,
                on_progress=on_progress,
                on_agent_update=on_agent_update,
            )
            results[lang] = ok

            logger.info(
                "Translation for language '%s' %s",
                lang,
                "succeeded" if ok else "failed",
            )

            # 4. Update internal state so that save_translated_epub()
            #    can write the most recently translated version.
            self._epub_processor = processor
            self.scheduler.epub_processor = processor

        return results

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_translated_epub(
        self,
        output_path: str,
        analysis: EpubAnalysis,
        language: str,
        title_confirmation: Optional[TitleConfirmation] = None,
    ) -> str:
        """Write the translated EPUB to *output_path*.

        Parameters
        ----------
        output_path:
            Target file path for the new EPUB.
        analysis:
            The :class:`EpubAnalysis` (used for genre, description).
        language:
            ISO 639-1 target language code.
        title_confirmation:
            Optional :class:`TitleConfirmation` whose selected title
            becomes the EPUB's title metadata.

        Returns
        -------
        The absolute path of the saved file.

        Raises
        ------
        RuntimeError
            If no EPUB has been loaded via :meth:`analyze_epub`.
        """
        if self._epub_processor is None:
            raise RuntimeError(
                "No EPUB loaded. Call analyze_epub() before save_translated_epub()."
            )

        title = analysis.title
        subtitle = analysis.subtitle or None
        description = analysis.description or None
        genre = analysis.genre or None

        if title_confirmation is not None and title_confirmation.confirmed:
            title = title_confirmation.selected_title

        resolved = self._epub_processor.save(
            output_path=output_path,
            title=title,
            language=language,
            subtitle=subtitle,
            description=description,
            genre=genre,
        )

        logger.info("Translated EPUB saved to %s", resolved)
        return resolved

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_all(self) -> None:
        """Request cancellation of any in-flight translation.

        This is a convenience that delegates to
        :meth:`TranslationScheduler.cancel`.
        """
        self.scheduler.cancel()
        logger.info("All translations cancelled")

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def get_translation_status(self) -> Dict[str, Any]:
        """Return a comprehensive status snapshot of the service.

        Includes agent pool summary, queue stats, and current file.
        """
        return {
            "filepath": self._current_filepath,
            "agent_pool_summary": self.agent_pool.get_status_summary(),
            "agent_pool_status": self.agent_pool.get_agents_status(),
            "queue_stats": self.scheduler.get_queue_stats(),
            "config": {
                "max_agents": self._config.max_agents,
                "translation_mode": self._config.translation_mode,
                "max_retries": self._config.max_retries,
                "timeout_seconds": self._config.timeout_seconds,
            },
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def provider(self) -> TranslationProvider:
        """The configured translation provider."""
        return self._provider

    @property
    def config(self) -> TranslationConfig:
        """The configuration used by this service instance."""
        return self._config
