"""
Translation Scheduler — orchestrates parallel chunk translation.

Splits every chapter into chunks via :func:`chunk_text`, dispatches them
to the :class:`AgentPool` for parallel translation via the configured
:class:`TranslationProvider`, handles retries, merges translated chunks
back in order, and writes the result into the EPUB document via the
:class:`EpubProcessor`.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.core.chunker import Chunk, chunk_text, merge_chunks, validate_chunk_order
from app.services.agent_pool import Agent, AgentPool, AgentStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum characters per chunk (passed to chunk_text).
_MAX_CHUNK_CHARS: int = 2000

# Default retry count when no config is available.
_DEFAULT_MAX_RETRIES: int = 3

# Backoff base in seconds between retries.
_RETRY_BACKOFF: float = 1.0


# ---------------------------------------------------------------------------
# Text-node splitting
# ---------------------------------------------------------------------------


def _build_node_separator(
    node_texts: List[str],
) -> str:
    """Build a separator string that is guaranteed not to appear in *text*.

    Uses a random UUID hex string wrapped in distinctive delimiters.
    """
    while True:
        sep = f"\x00__TN_SEP_{uuid.uuid4().hex}__\x00"
        # Verify it does not appear in any node text
        ok = True
        for t in node_texts:
            if sep in t:
                ok = False
                break
        if ok:
            return sep


def _split_translated_by_separator(
    original_node_texts: List[str],
    translated_full_text: str,
) -> List[str]:
    """Split *translated_full_text* back into per-text-node strings.

    Strategy
    --------
    1. Join the original node texts with a unique separator that is known
       not to appear in any text.
    2. The translated full text is the result after chunking, translation,
       and merging — we assume the separator markers survive those steps
       *because* they are control characters (``\\x00``) that the chunker
       will carry along and LLMs are unlikely to modify.
    3. Split the translated text on the same separator to recover
       per-node translations.
    4. If the split produces a different number of parts, fall back to
       proportional character-length splitting.
    """
    if not original_node_texts:
        return []

    if len(original_node_texts) == 1:
        return [translated_full_text]

    separator = _build_node_separator(original_node_texts)
    joined = separator.join(original_node_texts)

    # If the original joined text equals the translated text (no change),
    # just return the originals.
    if joined == translated_full_text:
        return list(original_node_texts)

    # Attempt to split by the separator
    parts = translated_full_text.split(separator)

    if len(parts) == len(original_node_texts):
        return parts

    # Fall back to proportional character-length splitting
    logger.warning(
        "Separator split yielded %d parts, expected %d. "
        "Falling back to proportional splitting.",
        len(parts),
        len(original_node_texts),
    )
    return _split_proportional(original_node_texts, translated_full_text)


def _split_proportional(
    original_node_texts: List[str],
    translated_full_text: str,
) -> List[str]:
    """Split *translated_full_text* proportionally by original character counts."""
    orig_lengths = [len(t) for t in original_node_texts]
    total_orig = sum(orig_lengths)
    total_trans = len(translated_full_text)

    if total_orig == 0:
        return [""] * len(original_node_texts)

    result: List[str] = []
    cursor = 0
    for i, olen in enumerate(orig_lengths):
        if i == len(orig_lengths) - 1:
            # Last node gets all remaining characters
            result.append(translated_full_text[cursor:])
        else:
            ratio = olen / total_orig
            chunk_size = max(1, round(total_trans * ratio))
            # Clamp so we never exceed the buffer
            chunk_size = min(chunk_size, total_trans - cursor - (len(orig_lengths) - i - 1))
            result.append(translated_full_text[cursor : cursor + chunk_size])
            cursor += chunk_size

    return result


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class TranslationScheduler:
    """Orchestrates the translation of an EPUB document.

    Typical usage::

        scheduler = TranslationScheduler(agent_pool, chunker, html_translator, processor)
        scheduler.set_provider(my_provider)
        success = scheduler.schedule_translation(analysis, "de", confirmation)
    """

    def __init__(
        self,
        agent_pool: AgentPool,
        chunker_module: Any = None,  # kept for interface compatibility
        html_translator_module: Any = None,  # kept for interface compatibility
        epub_processor: Any = None,
    ) -> None:
        self.agent_pool: AgentPool = agent_pool
        self._chunker = chunker_module  # kept for compatibility
        self._html_translator = html_translator_module
        self.epub_processor: Any = epub_processor
        self._provider: Any = None
        self._cancel_flag: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._stats: Dict[str, int] = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
        }

    # ------------------------------------------------------------------
    # Provider setter
    # ------------------------------------------------------------------

    def set_provider(self, provider: Any) -> None:
        """Set the :class:`TranslationProvider` used for translation calls."""
        self._provider = provider

    # ------------------------------------------------------------------
    # Per-language translation
    # ------------------------------------------------------------------

    def schedule_translation(
        self,
        epub_analysis: Any,
        target_language: str,
        title_confirmation: Any = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_agent_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> bool:
        """Translate all chapters of *epub_analysis* into *target_language*.

        Parameters
        ----------
        epub_analysis:
            The :class:`EpubAnalysis` returned by
            :meth:`EpubProcessor.analyse`.
        target_language:
            ISO 639-1 language code (e.g. ``"de"``, ``"fr"``).
        title_confirmation:
            Optional :class:`TitleConfirmation` whose selected title is
            injected as translation context.
        on_progress:
            Callback ``(completed, total)`` invoked after each chunk
            translation.
        on_agent_update:
            Callback ``(agents_status)`` invoked whenever an agent's
            state changes.

        Returns
        -------
        ``True`` if all chapters were translated successfully,
        ``False`` on failure or cancellation.
        """
        if self._provider is None:
            raise RuntimeError(
                "No provider set. Call set_provider() before schedule_translation()."
            )
        if self.epub_processor is None:
            raise RuntimeError(
                "No EpubProcessor set. Provide one via the constructor or "
                "set epub_processor directly."
            )

        self._cancel_flag.clear()
        source_language: str = epub_analysis.language or "en"

        # Build translation context from the title confirmation
        context: Optional[str] = None
        if title_confirmation is not None and hasattr(title_confirmation, "confirmed"):
            if title_confirmation.confirmed and title_confirmation.selected_title:
                from app.services.title_generator import TitleGenerator
                context = TitleGenerator.get_translation_context(title_confirmation)

        # ------------------------------------------------------------------
        # Phase 1 — Chunk every chapter
        # ------------------------------------------------------------------
        all_chunks: List[Chunk] = []
        chapter_chunk_map: Dict[str, List[Chunk]] = {}

        for chapter in epub_analysis.chapters:
            node_texts: List[str] = [
                node["text"] for node in chapter.text_nodes
            ]

            if not node_texts:
                logger.info("Chapter %s has no translatable text nodes — skipping", chapter.id)
                continue

            # Join with a unique separator so we can later split back.
            separator = _build_node_separator(node_texts)
            full_text = separator.join(node_texts)

            chunks = chunk_text(
                text=full_text,
                chapter_id=chapter.id,
                chapter_order=chapter.order,
                max_chars=_MAX_CHUNK_CHARS,
            )
            all_chunks.extend(chunks)
            chapter_chunk_map[chapter.id] = chunks

        total_chunks = len(all_chunks)
        logger.info(
            "Phase 1 complete — %d chunks across %d chapters",
            total_chunks,
            len(epub_analysis.chapters),
        )

        if total_chunks == 0:
            logger.warning("No chunks to translate — returning success.")
            return True

        with self._lock:
            self._stats = {
                "total": total_chunks,
                "completed": 0,
                "failed": 0,
                "pending": total_chunks,
            }

        # ------------------------------------------------------------------
        # Phase 2 — Translate every chunk (parallel dispatch)
        # ------------------------------------------------------------------

        # We use a separate thread-pool whose max_workers matches the
        # agent pool size.  Each worker thread grabs an agent, translates,
        # and releases it.
        translated_chunks: List[Chunk] = []

        def _translate_one(chunk: Chunk) -> Optional[Chunk]:
            """Translate a single chunk.  Called from thread-pool threads."""
            if self._cancel_flag.is_set():
                return None

            agent: Optional[Agent] = self.agent_pool.get_idle_agent()
            if agent is None:
                # All agents busy — this should not happen if we limit
                # concurrency to pool size, but handle gracefully.
                logger.warning("No idle agent available for chunk %s — retrying later", chunk.chunk_id)
                return None  # Will need to be re-queued

            self.agent_pool.assign_chunk(agent, chunk, target_language, chunk.chapter_id)
            if on_agent_update:
                on_agent_update(self.agent_pool.get_agents_status())

            max_retries = _DEFAULT_MAX_RETRIES
            last_error: Optional[str] = None
            success = False

            for attempt in range(1, max_retries + 2):  # +1 for initial try
                if self._cancel_flag.is_set():
                    self.agent_pool.release_agent(agent.agent_id)
                    return None

                try:
                    translated: str = self._provider.translate_text(
                        text=chunk.original_text,
                        source_language=source_language,
                        target_language=target_language,
                        context=context,
                    )
                    chunk.translated_text = translated
                    chunk.status = "translated"
                    chunk.retry_count = attempt - 1
                    chunk.agent_id = agent.agent_id
                    chunk.language = target_language

                    success = True
                    break

                except Exception as exc:
                    last_error = str(exc)
                    chunk.retry_count = attempt
                    agent.retry_count = attempt
                    agent.last_error = last_error
                    agent.status = AgentStatus.RETRY

                    if on_agent_update:
                        on_agent_update(self.agent_pool.get_agents_status())

                    if attempt <= max_retries:
                        backoff = _RETRY_BACKOFF * attempt
                        logger.warning(
                            "Translation attempt %d/%d failed for chunk %s "
                            "(chapter=%s): %s.  Retrying in %.1fs …",
                            attempt,
                            max_retries + 1,
                            chunk.chunk_id,
                            chunk.chapter_id,
                            last_error,
                            backoff,
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(
                            "Translation failed after %d attempts for chunk %s: %s",
                            attempt,
                            chunk.chunk_id,
                            last_error,
                        )

            if success:
                # Update agent counters
                agent.chunks_completed += 1
                agent.status = AgentStatus.COMPLETED
                self.agent_pool.release_agent(agent.agent_id)

                with self._lock:
                    self._stats["completed"] += 1
                    self._stats["pending"] -= 1

                if on_progress:
                    on_progress(self._stats["completed"], self._stats["total"])
                if on_agent_update:
                    on_agent_update(self.agent_pool.get_agents_status())

                return chunk
            else:
                # Mark as failed
                chunk.status = "failed"
                agent.status = AgentStatus.ERROR
                agent.chunks_failed += 1
                agent.last_error = last_error
                self.agent_pool.release_agent(agent.agent_id)

                with self._lock:
                    self._stats["failed"] += 1
                    self._stats["pending"] -= 1

                if on_progress:
                    on_progress(
                        self._stats["completed"] + self._stats["failed"],
                        self._stats["total"],
                    )
                if on_agent_update:
                    on_agent_update(self.agent_pool.get_agents_status())

                return chunk  # Return chunk with failed status

        # Dispatch all chunks to the thread pool
        max_workers = min(self.agent_pool._max_agents, total_chunks)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="trans"
        ) as executor:
            future_map: Dict[concurrent.futures.Future, Chunk] = {
                executor.submit(_translate_one, chunk): chunk
                for chunk in all_chunks
            }

            for future in concurrent.futures.as_completed(future_map):
                try:
                    result = future.result()
                    if result is not None:
                        translated_chunks.append(result)
                    # If None, the chunk was skipped (no idle agent or cancelled)
                except Exception as exc:
                    chunk = future_map[future]
                    logger.error(
                        "Unhandled exception translating chunk %s: %s",
                        chunk.chunk_id,
                        exc,
                    )
                    chunk.status = "failed"
                    translated_chunks.append(chunk)

        if self._cancel_flag.is_set():
            logger.info("Translation cancelled for language '%s'", target_language)
            return False

        logger.info(
            "Phase 2 complete — %d translated, %d failed (of %d total)",
            self._stats["completed"],
            self._stats["failed"],
            total_chunks,
        )

        # ------------------------------------------------------------------
        # Phase 3 — Merge & update chapters
        # ------------------------------------------------------------------
        all_ok = True

        for chapter in epub_analysis.chapters:
            chapter_chunks = [
                c for c in translated_chunks if c.chapter_id == chapter.id
            ]
            if not chapter_chunks:
                continue

            # Sort by chunk order (must be stable)
            chapter_chunks.sort(key=lambda c: c.chunk_order)

            # Validate ordering
            if not validate_chunk_order(chapter_chunks):
                logger.warning("Chunk order validation failed for chapter %s", chapter.id)

            # Merge translated chunks back into a single text
            merged_text: str = merge_chunks(chapter_chunks)

            # Recover per-text-node translated strings
            node_texts_orig: List[str] = [
                node["text"] for node in chapter.text_nodes
            ]

            if not node_texts_orig:
                continue

            translated_node_texts: List[str] = _split_translated_by_separator(
                original_node_texts=node_texts_orig,
                translated_full_text=merged_text,
            )

            # Ensure we have exactly the right number of strings
            if len(translated_node_texts) != len(node_texts_orig):
                logger.warning(
                    "Node count mismatch for chapter %s: "
                    "expected %d translated strings, got %d. "
                    "Using proportional fallback.",
                    chapter.id,
                    len(node_texts_orig),
                    len(translated_node_texts),
                )
                translated_node_texts = _split_proportional(
                    node_texts_orig, merged_text
                )

            # Update chapter HTML via EpubProcessor
            try:
                self.epub_processor.update_chapter_text(
                    chapter.id, translated_node_texts
                )
                logger.debug("Updated chapter %s (%s)", chapter.id, chapter.title)
            except Exception as exc:
                logger.error(
                    "Failed to update chapter %s: %s",
                    chapter.id,
                    exc,
                )
                all_ok = False

        return all_ok

    # ------------------------------------------------------------------
    # Multi-language translation
    # ------------------------------------------------------------------

    def translate_all(
        self,
        epub_analysis: Any,
        confirmations: Dict[str, Any],
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_agent_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> Dict[str, bool]:
        """Translate the document into multiple languages sequentially.

        *confirmations* maps language codes to
        :class:`TitleConfirmation` objects.

        Returns a dict mapping each language code to a boolean success
        flag.
        """
        results: Dict[str, bool] = {}
        for lang, confirmation in confirmations.items():
            if self._cancel_flag.is_set():
                logger.warning("Skipping language '%s' — cancellation in progress", lang)
                results[lang] = False
                continue

            logger.info("Starting translation for language '%s'", lang)
            ok = self.schedule_translation(
                epub_analysis=epub_analysis,
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
        return results

    # ------------------------------------------------------------------
    # Cancellation & stats
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request cancellation of any in-flight translation.

        Sets a thread-safe flag that worker threads check before each
        chunk translation.
        """
        self._cancel_flag.set()
        logger.info("Translation cancellation requested")

    def get_queue_stats(self) -> Dict[str, int]:
        """Return a snapshot of translation queue statistics.

        Keys: ``total``, ``completed``, ``failed``, ``pending``.
        """
        with self._lock:
            return dict(self._stats)
