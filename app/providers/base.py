from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TranslationResult:
    """Result of a single translation chunk."""
    original_text: str
    translated_text: str
    chunk_id: str
    success: bool
    error: Optional[str] = None
    retry_count: int = 0


class TranslationProvider(ABC):
    """Abstract base class for all translation providers.

    Each concrete provider implements one or more translation backends
    (e.g. DeepL, OpenAI, Anthropic).
    """

    @abstractmethod
    def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """Translate a single string from source to target language.

        Args:
            text: The text to translate.
            source_language: Source language code (e.g. 'en', 'de').
            target_language: Target language code.
            context: Optional contextual information to guide translation.

        Returns:
            The translated text.
        """
        ...

    @abstractmethod
    def generate_title_suggestions(
        self,
        title: str,
        subtitle: Optional[str],
        description: str,
        genre: str,
        target_language: str,
        sample_content: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate title suggestions in the target language.

        Returns a dict with keys 'literal', 'market', 'seo', and
        'reasoning_short' (itself a dict with the same three keys).

        Example return value:
            {
                'literal': '...',
                'market': '...',
                'seo': '...',
                'reasoning_short': {
                    'literal': '...',
                    'market': '...',
                    'seo': '...',
                },
            }
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'DeepL', 'OpenAI')."""
        ...

    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """List of model identifiers supported by this provider."""
        ...
