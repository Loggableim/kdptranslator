"""Mock translation provider for testing.

Provides a fake translation backend that does not require any API key.
All translate calls return the original text prefixed with a mock marker;
all title-suggestion calls return placeholder JSON with literal/market/SEO
variations.

Usage:
    provider = MockTranslationProvider()
    result = provider.translate_text("Hello", "en", "de")
    # → "[MOCK: de] Hello"
"""

import logging
from typing import Dict, List, Optional

from app.core.logger import get_logger as _ensure_logging
from app.providers.base import TranslationProvider

# Ensure the project logging system is initialised (idempotent)
_ensure_logging()

logger = logging.getLogger(__name__)


class MockTranslationProvider(TranslationProvider):
    """Translation provider that returns mock responses — no API key needed.

    This is useful for:
    * Offline / CI testing of the translation pipeline.
    * UI development without incurring API costs.
    * Acceptance tests where deterministic output is required.
    """

    @property
    def name(self) -> str:
        return "MockProvider"

    @property
    def supported_models(self) -> List[str]:
        return ["mock-model"]

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """Return a mock translation by prefixing *text* with ``[MOCK: …]``.

        Logs the call parameters at INFO level.
        """
        logger.info(
            "MockTranslationProvider.translate_text — "
            "source=%s target=%s text_len=%d context_provided=%s",
            source_language,
            target_language,
            len(text),
            context is not None,
        )

        # Return the prefixed mock result
        return f"[MOCK: {target_language}] {text}"

    # ------------------------------------------------------------------
    # Title suggestions
    # ------------------------------------------------------------------

    def generate_title_suggestions(
        self,
        title: str,
        subtitle: Optional[str],
        description: str,
        genre: str,
        target_language: str,
        sample_content: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate mock title suggestions in the target language.

        Returns a dict with ``literal``, ``market``, ``seo`` keys and an
        accompanying ``reasoning_short`` dict with brief placeholder
        explanations for each variation.
        """
        logger.info(
            "MockTranslationProvider.generate_title_suggestions — "
            "title=%s target=%s genre=%s subtitle_provided=%s sample_provided=%s",
            title,
            target_language,
            genre,
            subtitle is not None,
            sample_content is not None,
        )

        # Build a deterministic mock suggestion based on the original title.
        literal = f"[MOCK:{target_language}/literal] {title}"
        market = f"[MOCK:{target_language}/market] {title}"
        seo = f"[MOCK:{target_language}/seo] {title}"

        return {
            "literal": literal,
            "market": market,
            "seo": seo,
            "reasoning_short": {
                "literal": f"Direct translation placeholder for '{title}'",
                "market": (
                    f"Market-adapted variant for '{title}' "
                    f"in {target_language} ({genre})"
                ),
                "seo": (
                    f"SEO-optimised variant for '{title}' "
                    f"derived from {description[:50] if description else 'N/A'}…"
                ),
            },
        }
