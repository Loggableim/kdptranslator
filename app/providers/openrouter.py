"""
OpenRouter translation provider.

Implementation of the :class:`TranslationProvider` ABC backed by the
OpenRouter AI API (OpenAI-compatible chat completions).

Configuration
-------------
Values resolved in order (highest wins):

1. Constructor keyword arguments (``api_key``, ``base_url``, ``model``,
   ``max_retries``, ``timeout_seconds``).
2. Environment variables / ``.env`` file (see :class:`AppConfig`).
3. Built-in defaults.

Usage::

    from app.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider()
    translated = provider.translate_text("Hello world", "en", "de")
    suggestions = provider.generate_title_suggestions(...)
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

_ensure_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts  (shared with OllamaCloudProvider)
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
    " JSON schema: {"
    '   "literal": "...",'
    '   "market": "...",'
    '   "seo": "...",'
    '   "reasoning_short": {'
    '       "literal": "...",'
    '       "market": "...",'
    '       "seo": "..."'
    "   }"
    "}"
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "openai/gpt-4o-mini"
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_TIMEOUT = 120

# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenRouterProvider(TranslationProvider):
    """Translation provider using the OpenRouter API.

    Parameters
    ----------
    api_key:
        OpenRouter API key. Falls back to ``OPENROUTER_API_KEY`` env var.
    base_url:
        API base URL. Falls back to ``OPENROUTER_BASE_URL`` env var, then
        ``https://openrouter.ai/api/v1``.
    model:
        Model identifier. Falls back to ``OPENROUTER_MODEL`` env var, then
        ``openai/gpt-4o-mini``.
    max_retries:
        Max retry attempts on transient errors (default 3).
    timeout_seconds:
        HTTP request timeout (default 120).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        cfg = AppConfig.load()

        self.api_key: str = (
            api_key
            or self._get_env("OPENROUTER_API_KEY")
            or cfg.ollamacloud_api_key
            or ""
        )
        self.base_url: str = (
            base_url
            or self._get_env("OPENROUTER_BASE_URL")
            or _DEFAULT_BASE_URL
        )
        self.model: str = (
            model
            or self._get_env("OPENROUTER_MODEL")
            or cfg.ollamcloud_model
            or _DEFAULT_MODEL
        )
        self.max_retries: int = max_retries or _DEFAULT_MAX_RETRIES
        self.timeout_seconds: int = timeout_seconds or _DEFAULT_TIMEOUT

        if not self.api_key:
            logger.warning(
                "No OpenRouter API key configured. "
                "Set OPENROUTER_API_KEY in .env or pass api_key."
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "OpenRouter"

    @property
    def supported_models(self) -> List[str]:
        return [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "google/gemini-2.5-pro-preview-03-25",
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/mistral-large-2411",
            "qwen/qwen-2.5-72b-instruct",
        ]

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
        """Translate *text* via OpenRouter chat completion."""
        if not text or not text.strip():
            return text

        user_parts: List[str] = [
            f"Source language: {source_language}",
            f"Target language: {target_language}",
        ]
        if context:
            user_parts.append(f"Selected localized title: {context}")
        user_parts.append(f"Text:\n{text}")

        user_message = "\n".join(user_parts)

        messages = [
            {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response_text = self._chat_completion(messages, temperature=0.3)
        return response_text.strip()

    # ------------------------------------------------------------------
    # Title generation
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
        """Generate title suggestions via OpenRouter."""
        user_parts: List[str] = [
            f"Original title: {title}",
        ]
        if subtitle:
            user_parts.append(f"Original subtitle: {subtitle}")
        user_parts.append(f"Book description: {description}")
        user_parts.append(f"Detected genre: {genre}")
        user_parts.append(f"Target language: {target_language}")
        if sample_content:
            truncated = sample_content[:500]
            user_parts.append(f"Sample content:\n{truncated}")

        user_message = "\n".join(user_parts)

        messages = [
            {"role": "system", "content": TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response_text = self._chat_completion(messages, temperature=0.7)
        return self._parse_title_json(response_text)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
    ) -> str:
        """Call the OpenRouter chat completion API with retry logic."""
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Loggableim/kdptranslator",
            "X-Title": "KDP Translator",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "OpenRouter API call (attempt %d/%d) — model=%s",
                    attempt,
                    self.max_retries,
                    self.model,
                )
                with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                content = data["choices"][0]["message"]["content"]
                logger.info(
                    "OpenRouter API success — model=%s input=%d output=%d",
                    self.model,
                    data.get("usage", {}).get("prompt_tokens", 0),
                    data.get("usage", {}).get("completion_tokens", 0),
                )
                return content

            except httpx.TimeoutException as exc:
                last_error = f"Timeout after {self.timeout_seconds}s: {exc}"
                logger.warning(
                    "OpenRouter attempt %d/%d timed out: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                body = exc.response.text[:500]
                last_error = f"HTTP {status}: {body}"
                logger.warning(
                    "OpenRouter attempt %d/%d HTTP error: %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )
                # Don't retry 4xx errors except 429 (rate limit)
                if 400 <= status < 500 and status != 429:
                    break
            except httpx.RequestError as exc:
                last_error = f"Request failed: {exc}"
                logger.warning(
                    "OpenRouter attempt %d/%d connection error: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )

            if attempt < self.max_retries:
                delay = 2 ** (attempt - 1)  # 1, 2, 4, ...
                logger.debug("Retrying in %ds …", delay)
                time.sleep(delay)

        raise RuntimeError(
            f"OpenRouter API call failed after {self.max_retries} "
            f"retries: {last_error}"
        )

    @staticmethod
    def _parse_title_json(response_text: str) -> Dict[str, str]:
        """Parse JSON from the model response, stripping markdown fences."""
        text = response_text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            # Strip first line of fences
            lines = text.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse title JSON: {exc}\nRaw: {text[:500]}"
            ) from exc

        required = {"literal", "market", "seo", "reasoning_short"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"Title JSON missing keys: {missing}. Got: {list(data.keys())}"
            )

        reasoning = data.get("reasoning_short", {})
        if not isinstance(reasoning, dict):
            reasoning = {}
        for key in ("literal", "market", "seo"):
            if key not in reasoning:
                reasoning[key] = ""

        return {
            "literal": str(data["literal"]),
            "market": str(data["market"]),
            "seo": str(data["seo"]),
            "reasoning_short": reasoning,
        }

    @staticmethod
    def _get_env(key: str) -> Optional[str]:
        """Read an environment variable."""
        import os
        return os.environ.get(key)
