"""Tests for app.services.title_generator."""

import pytest

from app.services.title_generator import (
    TitleSuggestion,
    TitleConfirmation,
    TitleGenerator,
)
from app.providers.mock import MockTranslationProvider


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


def test_title_suggestion_dataclass():
    """Creates TitleSuggestion correctly with all fields."""
    suggestion = TitleSuggestion(
        literal="Literales Titel",
        market="Marktgerechter Titel",
        seo="SEO Titel",
        reasoning={
            "literal": "Direct translation",
            "market": "Market adaptation",
            "seo": "SEO optimisation",
        },
    )

    assert suggestion.literal == "Literales Titel"
    assert suggestion.market == "Marktgerechter Titel"
    assert suggestion.seo == "SEO Titel"
    assert suggestion.reasoning["literal"] == "Direct translation"
    assert suggestion.reasoning["market"] == "Market adaptation"
    assert suggestion.reasoning["seo"] == "SEO optimisation"


def test_title_confirmation_dataclass():
    """Creates TitleConfirmation correctly with all fields."""
    suggestion = TitleSuggestion(
        literal="Lit",
        market="Mkt",
        seo="Seo",
        reasoning={"literal": "a", "market": "b", "seo": "c"},
    )
    confirmation = TitleConfirmation(
        language_code="de",
        selected_title="Mkt",
        selection_type="market",
        confirmed=True,
        suggestions=suggestion,
    )

    assert confirmation.language_code == "de"
    assert confirmation.selected_title == "Mkt"
    assert confirmation.selection_type == "market"
    assert confirmation.confirmed is True
    assert confirmation.suggestions is suggestion
    assert confirmation.suggestions.literal == "Lit"


# ---------------------------------------------------------------------------
# TitleGenerator
# ---------------------------------------------------------------------------


def test_title_generator_raises_on_none_provider():
    """Raises ValueError when provider is None."""
    with pytest.raises(ValueError, match="provider must not be None"):
        TitleGenerator(provider=None)


def test_title_generator_context():
    """get_translation_context returns correct string."""
    suggestion = TitleSuggestion(
        literal="Lit",
        market="Mkt",
        seo="Seo",
        reasoning={"literal": "a", "market": "b", "seo": "c"},
    )
    confirmation = TitleConfirmation(
        language_code="de",
        selected_title="Der schöne Titel",
        selection_type="market",
        confirmed=True,
        suggestions=suggestion,
    )

    context = TitleGenerator.get_translation_context(confirmation)
    assert context == "Localized title: Der schöne Titel"


def test_mock_provider_generates_titles():
    """MockTranslationProvider returns proper JSON via TitleGenerator.generate()."""
    provider = MockTranslationProvider()
    generator = TitleGenerator(provider=provider)

    suggestion = generator.generate(
        original_title="The Beautiful Title",
        subtitle="A Subtitle",
        description="A book description for testing.",
        genre="Fiction",
        target_language="de",
        sample_content="Some sample text.",
    )

    assert isinstance(suggestion, TitleSuggestion)
    assert "[MOCK:de/literal]" in suggestion.literal
    assert "[MOCK:de/market]" in suggestion.market
    assert "[MOCK:de/seo]" in suggestion.seo
    assert "The Beautiful Title" in suggestion.literal

    # reasoning should contain three keys
    assert "literal" in suggestion.reasoning
    assert "market" in suggestion.reasoning
    assert "seo" in suggestion.reasoning


def test_generate_without_subtitle():
    """Works correctly when subtitle is None."""
    provider = MockTranslationProvider()
    generator = TitleGenerator(provider=provider)

    suggestion = generator.generate(
        original_title="Short Title",
        subtitle=None,
        description="Desc.",
        genre="Non-Fiction",
        target_language="fr",
    )

    assert suggestion.literal.startswith("[MOCK:fr/literal]")


def test_generate_without_sample_content():
    """Works correctly when sample_content is None."""
    provider = MockTranslationProvider()
    generator = TitleGenerator(provider=provider)

    suggestion = generator.generate(
        original_title="Test",
        subtitle="Sub",
        description="Desc.",
        genre="Sci-Fi",
        target_language="ja",
        sample_content=None,
    )

    assert suggestion.market.startswith("[MOCK:ja/market]")


def test_generate_raises_on_provider_failure():
    """Raises RuntimeError if the provider raises an exception."""
    class FailingProvider(MockTranslationProvider):
        def generate_title_suggestions(self, **kwargs):
            raise ConnectionError("API unreachable")

    provider = FailingProvider()
    generator = TitleGenerator(provider=provider)

    with pytest.raises(RuntimeError, match="failed to generate title suggestions"):
        generator.generate(
            original_title="X",
            subtitle=None,
            description="Y",
            genre="Z",
            target_language="de",
        )


def test_generate_raises_on_missing_keys():
    """Raises ValueError if provider response is missing required keys."""
    class IncompleteProvider(MockTranslationProvider):
        def generate_title_suggestions(self, **kwargs):
            return {"literal": "only"}  # missing market, seo

    provider = IncompleteProvider()
    generator = TitleGenerator(provider=provider)

    with pytest.raises(ValueError, match="missing required key"):
        generator.generate(
            original_title="X",
            subtitle=None,
            description="Y",
            genre="Z",
            target_language="de",
        )
