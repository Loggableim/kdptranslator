"""
Title generator service for KDP Translator.

Produces localized title suggestions (literal, market-aware, SEO-optimised)
via the configured translation provider, and stores the user's selection
for downstream translation context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.providers.base import TranslationProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class TitleSuggestion:
    """Three-variant title suggestion produced by a provider.

    Attributes
    ----------
    literal:
        A direct / literal translation of the original title.
    market:
        A version adapted for the target market (cultural nuance, idioms).
    seo:
        A version optimised for search / discoverability in the target
        language.
    reasoning:
        Per-type rationale explaining why each variant was chosen.
    """

    literal: str
    market: str
    seo: str
    reasoning: Dict[str, str]  # keys: 'literal', 'market', 'seo'


@dataclass
class TitleConfirmation:
    """Records what title the user ultimately selected for a language.

    This is persisted and later fed back to the translation pipeline as
    context so that the body translation respects the chosen title.

    Attributes
    ----------
    language_code:
        Target language (e.g. ``"de"``, ``"fr"``).
    selected_title:
        The final title string chosen by the user.
    selection_type:
        One of ``'literal'``, ``'market'``, ``'seo'``, or ``'custom'``.
    confirmed:
        ``True`` once the user has explicitly confirmed the selection.
    suggestions:
        The full :class:`TitleSuggestion` that was presented, if any.
    """

    language_code: str
    selected_title: str
    selection_type: str  # 'literal', 'market', 'seo', 'custom'
    confirmed: bool = False
    suggestions: Optional[TitleSuggestion] = None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class TitleGenerator:
    """Orchestrates title suggestion generation and selection tracking.

    Usage::

        generator = TitleGenerator(provider=my_deepl_provider)
        suggestion = generator.generate(
            original_title="The Art of War",
            subtitle="Ancient Wisdom for Modern Times",
            description="...",
            genre="Non-Fiction",
            target_language="de",
        )
        # Present suggestion to user, get their choice …
        confirmation = TitleConfirmation(
            language_code="de",
            selected_title=suggestion.market,
            selection_type="market",
            confirmed=True,
            suggestions=suggestion,
        )
        context = generator.get_translation_context(confirmation)
    """

    def __init__(self, provider: TranslationProvider) -> None:
        if provider is None:
            raise ValueError("provider must not be None")
        self.provider = provider

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        original_title: str,
        subtitle: Optional[str],
        description: str,
        genre: str,
        target_language: str,
        sample_content: Optional[str] = None,
    ) -> TitleSuggestion:
        """Call the configured provider and parse its response into a
        :class:`TitleSuggestion`.

        Parameters
        ----------
        original_title:
            The book's original (source-language) title.
        subtitle:
            Optional subtitle (may be ``None``).
        description:
            Book description / blurb, used as extra context.
        genre:
            Book genre (e.g. ``"Fantasy"``, ``"Self-Help"``).
        target_language:
            Target language code (e.g. ``"de"``, ``"fr"``, ``"ja"``).
        sample_content:
            Optional short excerpt of the book text.

        Returns
        -------
        A :class:`TitleSuggestion` with the three variants and their
        associated reasoning.

        Raises
        ------
        ValueError
            If the provider returns a malformed response (missing keys).
        RuntimeError
            If the underlying provider call fails.
        """
        logger.info(
            "Generating title suggestions — title=%r lang=%s genre=%s",
            original_title,
            target_language,
            genre,
        )

        try:
            raw: Dict[str, str] = self.provider.generate_title_suggestions(
                title=original_title,
                subtitle=subtitle,
                description=description,
                genre=genre,
                target_language=target_language,
                sample_content=sample_content,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Provider {self.provider.name!r} failed to generate title "
                f"suggestions: {exc}"
            ) from exc

        # --- validate & parse --------------------------------------------------
        missing = [k for k in ("literal", "market", "seo") if k not in raw]
        if missing:
            raise ValueError(
                f"Provider returned title suggestions missing required key(s): "
                f"{missing}.  Got keys: {list(raw.keys())}"
            )

        reasoning_raw = raw.get("reasoning_short", raw.get("reasoning", {}))
        if not isinstance(reasoning_raw, dict):
            logger.warning(
                "Provider returned non-dict reasoning (%r); falling back to "
                "empty dict",
                type(reasoning_raw).__name__,
            )
            reasoning_raw = {}

        reasoning: Dict[str, str] = {
            key: str(reasoning_raw.get(key, ""))
            for key in ("literal", "market", "seo")
        }

        suggestion = TitleSuggestion(
            literal=str(raw["literal"]),
            market=str(raw["market"]),
            seo=str(raw["seo"]),
            reasoning=reasoning,
        )

        logger.info(
            "Title suggestions generated — literal=%r market=%r seo=%r",
            suggestion.literal,
            suggestion.market,
            suggestion.seo,
        )
        return suggestion

    # ------------------------------------------------------------------
    # Context helper
    # ------------------------------------------------------------------

    @staticmethod
    def get_translation_context(confirmation: TitleConfirmation) -> str:
        """Return a context string that tells the translation engine which
        title the user chose for the target language.

        This should be injected as the ``context`` parameter of
        :meth:`TranslationProvider.translate_text` so that the body
        translation is consistent with the chosen localized title.
        """
        return f"Localized title: {confirmation.selected_title}"
