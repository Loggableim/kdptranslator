"""OllamaCloud translation provider.

Implementation of the :class:`TranslationProvider` ABC backed by an
OllamaCloud-compatible (OpenAI-compatible) chat completion API.

Configuration
-------------
Values are resolved in this order of precedence (highest wins):

1. Constructor keyword arguments (``api_key``, ``base_url``, ``model``,
   ``max_retries``, ``timeout_seconds``).
2. Environment variables / ``.env`` file (see :class:`AppConfig`).
3. Built-in defaults (``http://localhost:11434``, ``llama3``, 3 retries,
   120 s timeout).

Usage::

    from app.providers.ollamacloud import OllamaCloudProvider

    provider = OllamaCloudProvider()
    translated = provider.translate_text("Hello world", "en", "de")
    suggestions = provider.generate_title_suggestions(
        title="My Book",
        subtitle="A Story",
        description="An amazing story...",
        genre="Fiction",
        target_language="de",
    )
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import AppConfig
from app.core.logger import get_logger as _ensure_logging
from app.providers.base import TranslationProvider

# Ensure the project logging system is initialised (idempotent)
_ensure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional literary translator specialized in Kindle Direct "
    "Publishing books. Translate faithfully into the target language. "
    "Requirements:"
    " - preserve meaning"
    " - preserve tone"
    " - preserve narrative style"
    " - preserve paragraph structure"
    " - preserve names unless translation is natural"
    " - preserve punctuation style"
    " - preserve emphasis"
    " - preserve genre style"
    " - preserve consistency with the selected localized title."
    " Do not explain anything."
    " Do not add comments."
    " Do not add notes."
    " Do not output markdown."
    " Return only the translated text."
)

TITLE_SYSTEM_PROMPT = (
    "You are a professional international publishing consultant specialized "
    "in Amazon KDP. Your task is not to literally translate book titles only. "
    "Instead create titles that are:"
    " - natural in the target language"
    " - genre appropriate"
    " - commercially attractive"
    " - marketable"
    " - suitable for Amazon readers"
    " - optimized for discoverability"
    " - not awkward literal translations."
    " Return valid JSON only."
)

# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OllamaCloudProvider(TranslationProvider):
    """Translation provider backed by an OllamaCloud / OpenAI-compatible API.

    Uses ``httpx`` for HTTP requests with configurable retry logic and
    timeout handling.

    Parameters
    ----------
    api_key:
        Override the API key from ``AppConfig``.
    base_url:
        Override the API base URL (e.g. ``https://api.ollama.cloud``).
    model:
        Override the model identifier (e.g. ``llama3.1:70b``).
    max_retries:
        Maximum number of HTTP call retries on failure.
    timeout_seconds:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        config = AppConfig.load()
        translation_config = AppConfig.translation_config()

        self._api_key: Optional[str] = api_key or config.ollamacloud_api_key
        self._base_url: str = (
            base_url or config.ollamacloud_base_url
        ).rstrip("/")
        self._model: str = model or config.ollamcloud_model
        self._max_retries: int = (
            max_retries if max_retries is not None else translation_config.max_retries
        )
        self._timeout_seconds: int = (
            timeout_seconds
            if timeout_seconds is not None
            else translation_config.timeout_seconds
        )

        if not self._api_key:
            logger.warning(
                "No OllamaCloud API key configured — set OLLAMACLOUD_API_KEY "
                "or OPENAI_API_KEY in your .env file."
            )

    # ------------------------------------------------------------------
    # Provider metadata
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "OllamaCloud"

    @property
    def supported_models(self) -> List[str]:
        """List of model identifiers supported by this provider."""
        return [
            "llama3.1:70b",
            "llama3:70b",
            "mixtral:8x7b",
            "qwen2.5:72b",
            "deepseek-v4-flash",
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Build the JSON body for a chat completion request."""
        return {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
        }

    def _call_api(self, messages: List[Dict[str, str]]) -> str:
        """Send a chat completion request with exponential-backoff retries.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.

        Returns:
            The content string from the assistant response.

        Raises:
            RuntimeError: If all retries are exhausted or the response
                cannot be parsed.
        """
        url = f"{self._base_url}/v1/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(messages)

        last_exception: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.debug(
                    "OllamaCloud API — attempt %d/%d  model=%s  url=%s",
                    attempt,
                    self._max_retries,
                    self._model,
                    url,
                )

                with httpx.Client(
                    timeout=httpx.Timeout(self._timeout_seconds)
                ) as client:
                    response = client.post(url, headers=headers, json=payload)

                response.raise_for_status()
                data: Dict[str, Any] = response.json()

                choices = data.get("choices", [])
                if not choices:
                    raise ValueError("API response contained no choices")

                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    raise ValueError("API response message content is empty")

                usage = data.get("usage", {})
                logger.info(
                    "OllamaCloud API call succeeded — "
                    "model=%s  prompt_tokens=%s  completion_tokens=%s",
                    self._model,
                    usage.get("prompt_tokens", "?"),
                    usage.get("completion_tokens", "?"),
                )
                return content

            except httpx.TimeoutException as exc:
                last_exception = exc
                logger.warning(
                    "OllamaCloud API timeout (attempt %d/%d): %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                logger.warning(
                    "OllamaCloud API HTTP %d (attempt %d/%d): %s",
                    exc.response.status_code,
                    attempt,
                    self._max_retries,
                    exc.response.text[:300],
                )
            except httpx.RequestError as exc:
                last_exception = exc
                logger.warning(
                    "OllamaCloud API request error (attempt %d/%d): %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
            except (ValueError, json.JSONDecodeError) as exc:
                # Covers response.json() parse failures and our own checks
                last_exception = exc
                logger.warning(
                    "OllamaCloud API parse error (attempt %d/%d): %s",
                    attempt,
                    self._max_retries,
                    exc,
                )

            # Exponential backoff before next retry (1 s, 2 s, 4 s, …)
            if attempt < self._max_retries:
                backoff = 2 ** (attempt - 1)
                logger.info("Retrying in %d s...", backoff)
                time.sleep(backoff)

        # All retries exhausted – raise
        raise RuntimeError(
            f"OllamaCloud API call failed after {self._max_retries} retries. "
            f"Last error: {last_exception}"
        ) from last_exception

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_translation_messages(
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build the messages array for a literary translation request.

        The ``context`` parameter may contain a selected localized title
        for consistency.  Accepted formats:

        * ``"My Localized Title"`` — treated as the title alone.
        * ``"My Title | Additional translation notes"`` — title and
          extra context separated by ``|``.
        * Anything else is passed as-is in the *Additional context* field.
        """
        selected_title: Optional[str] = None
        extra_context: Optional[str] = None

        if context:
            # Try to split on pipe for "selected_title | extra context"
            if "|" in context:
                parts = [p.strip() for p in context.split("|", 1)]
                selected_title = parts[0]
                extra_context = parts[1] if len(parts) > 1 else None
            else:
                # Treat the entire context string as the selected title
                selected_title = context

        lines: List[str] = [
            f"Source language: {source_language}",
            f"Target language: {target_language}",
        ]
        if selected_title:
            lines.append(f"Selected localized title: {selected_title}")
        if extra_context:
            lines.append(f"Context: {extra_context}")
        lines.append("")
        lines.append("Text to translate:")
        lines.append(text)

        return [
            {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(lines)},
        ]

    @staticmethod
    def _build_title_messages(
        title: str,
        subtitle: Optional[str],
        description: str,
        genre: str,
        target_language: str,
        sample_content: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build the messages array for a title suggestion request."""
        lines: List[str] = [
            f"Original title: {title}",
            f"Subtitle: {subtitle or 'N/A'}",
            f"Description: {description}",
            f"Genre: {genre}",
            f"Target language: {target_language}",
        ]

        if sample_content:
            truncated = sample_content[:500]
            suffix = "…" if len(sample_content) > 500 else ""
            lines.append(f"Sample content: {truncated}{suffix}")

        lines.append("")
        lines.append(
            "Return valid JSON with keys: literal, market, seo, reasoning_short. "
            "reasoning_short must itself be an object with keys: "
            "literal, market, seo."
        )

        return [
            {"role": "system", "content": TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(lines)},
        ]

    # ------------------------------------------------------------------
    # Public API — TranslationProvider interface
    # ------------------------------------------------------------------

    def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """Translate *text* from *source_language* to *target_language*.

        Uses the OllamaCloud chat completion API with a professional
        literary-translator system prompt.

        Args:
            text: The text to translate.
            source_language: Source language code (e.g. ``'en'``, ``'de'``).
            target_language: Target language code.
            context: Optional contextual information.  See
                :meth:`_build_translation_messages` for supported formats.

        Returns:
            The translated text, stripped of leading/trailing whitespace.

        Raises:
            RuntimeError: If the API call fails after all configured
                retries.
        """
        logger.info(
            "OllamaCloudProvider.translate_text — "
            "source=%s target=%s text_len=%d context_provided=%s model=%s",
            source_language,
            target_language,
            len(text),
            context is not None,
            self._model,
        )

        messages = self._build_translation_messages(
            text=text,
            source_language=source_language,
            target_language=target_language,
            context=context,
        )

        result = self._call_api(messages)
        return result.strip()

    def generate_title_suggestions(
        self,
        title: str,
        subtitle: Optional[str],
        description: str,
        genre: str,
        target_language: str,
        sample_content: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate title suggestions in *target_language*.

        Uses the OllamaCloud chat API with a publishing-consultant system
        prompt.  Expects the model to return valid JSON matching this schema::

            {
                "literal": "...",
                "market": "...",
                "seo": "...",
                "reasoning_short": {
                    "literal": "...",
                    "market": "...",
                    "seo": "..."
                }
            }

        The raw response is leniently parsed — markdown code fences (`````)
        are stripped before JSON deserialisation.

        Args:
            title: Original book title.
            subtitle: Optional subtitle (``None`` if absent).
            description: Book description or blurb.
            genre: Book genre (e.g. ``\"Fiction\"``, ``\"Science Fiction\"``).
            target_language: Target language for the localised titles.
            sample_content: Optional sample text from the book (will be
                truncated to 500 characters).

        Returns:
            Dict with keys ``literal``, ``market``, ``seo``, and
            ``reasoning_short`` (itself a dict with the same three keys).

        Raises:
            RuntimeError: If the API call fails after all retries, or if
                the response cannot be parsed as the required JSON schema.
        """
        logger.info(
            "OllamaCloudProvider.generate_title_suggestions — "
            "title=%s target=%s genre=%s subtitle_provided=%s "
            "sample_provided=%s model=%s",
            title,
            target_language,
            genre,
            subtitle is not None,
            sample_content is not None,
            self._model,
        )

        messages = self._build_title_messages(
            title=title,
            subtitle=subtitle,
            description=description,
            genre=genre,
            target_language=target_language,
            sample_content=sample_content,
        )

        raw_response = self._call_api(messages)

        # --- Attempt to parse JSON from the model response ---
        # Models sometimes wrap JSON in markdown code fences; strip them.
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Remove opening fence (first line)
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence (last line if it's ```)
            if lines and lines[-1].strip() in ("```", "```json", "```json\n"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data: Dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse title suggestions JSON: %s\nRaw response: %s",
                exc,
                raw_response[:600],
            )
            raise RuntimeError(
                f"Failed to parse model response as JSON: {exc}"
            ) from exc

        # --- Validate required top-level keys ---
        required_keys = {"literal", "market", "seo", "reasoning_short"}
        missing = required_keys - data.keys()
        if missing:
            raise RuntimeError(
                f"Title suggestions response missing required key(s): "
                f"{', '.join(sorted(missing))}"
            )

        # --- Validate reasoning_short sub-keys ---
        reasoning = data.get("reasoning_short", {})
        if not isinstance(reasoning, dict):
            raise RuntimeError(
                "Title suggestions 'reasoning_short' must be a dict, "
                f"got {type(reasoning).__name__}"
            )

        reasoning_required = {"literal", "market", "seo"}
        reasoning_missing = reasoning_required - reasoning.keys()
        if reasoning_missing:
            raise RuntimeError(
                f"Title suggestions 'reasoning_short' missing key(s): "
                f"{', '.join(sorted(reasoning_missing))}"
            )

        # --- Return normalised result ---
        return {
            "literal": str(data["literal"]),
            "market": str(data["market"]),
            "seo": str(data["seo"]),
            "reasoning_short": {
                "literal": str(reasoning["literal"]),
                "market": str(reasoning["market"]),
                "seo": str(reasoning["seo"]),
            },
        }
