"""Tests for app.core.validation."""

from app.core.validation import (
    are_all_titles_confirmed,
    get_missing_languages,
    is_translation_ready,
)
from app.services.title_generator import (
    TitleConfirmation,
    TitleSuggestion,
)


def _make_confirmation(
    lang: str,
    confirmed: bool = True,
    title: str = "Some Title",
) -> TitleConfirmation:
    return TitleConfirmation(
        language_code=lang,
        selected_title=title,
        selection_type="literal",
        confirmed=confirmed,
        suggestions=None,
    )


# ---------------------------------------------------------------------------
# are_all_titles_confirmed
# ---------------------------------------------------------------------------


def test_are_all_titles_confirmed_true():
    """Returns True when all selected languages have confirmed titles."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=True),
    }
    selected = ["de", "fr"]

    assert are_all_titles_confirmed(confirmations, selected) is True


def test_are_all_titles_confirmed_false_missing():
    """Returns False when a selected language is missing from confirmations."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
    }
    selected = ["de", "fr"]  # 'fr' missing

    assert are_all_titles_confirmed(confirmations, selected) is False


def test_are_all_titles_confirmed_false_not_confirmed():
    """Returns False when one language exists but is not confirmed."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=False),
    }
    selected = ["de", "fr"]

    assert are_all_titles_confirmed(confirmations, selected) is False


def test_are_all_titles_confirmed_empty_selection():
    """Returns True when no languages are selected (vacuously true)."""
    assert are_all_titles_confirmed({}, []) is True


# ---------------------------------------------------------------------------
# get_missing_languages
# ---------------------------------------------------------------------------


def test_get_missing_languages():
    """Returns correct list of languages needing confirmation."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=False),
        # 'es' missing entirely
    }
    selected = ["de", "fr", "es", "ja"]

    missing = get_missing_languages(confirmations, selected)
    assert "fr" in missing
    assert "es" in missing
    assert "ja" in missing
    assert "de" not in missing


def test_get_missing_languages_none_missing():
    """Returns empty list when all confirmed."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=True),
    }
    assert get_missing_languages(confirmations, ["de", "fr"]) == []


def test_get_missing_languages_all_missing():
    """Returns all languages when none have confirmations."""
    assert get_missing_languages({}, ["de", "fr"]) == ["de", "fr"]


# ---------------------------------------------------------------------------
# is_translation_ready
# ---------------------------------------------------------------------------


def test_is_translation_ready_all_good():
    """Returns (True, '') when everything is ready."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=True),
    }
    ready, msg = is_translation_ready(
        confirmations=confirmations,
        selected_languages=["de", "fr"],
        epub_loaded=True,
    )

    assert ready is True
    assert msg == ""


def test_is_translation_ready_no_epub():
    """Returns (False, message) when EPUB not loaded."""
    ready, msg = is_translation_ready(
        confirmations={},
        selected_languages=["de"],
        epub_loaded=False,
    )

    assert ready is False
    assert "No EPUB file loaded" in msg


def test_is_translation_ready_no_languages():
    """Returns (False, message) when no languages selected."""
    ready, msg = is_translation_ready(
        confirmations={},
        selected_languages=[],
        epub_loaded=True,
    )

    assert ready is False
    assert "No languages selected" in msg


def test_is_translation_ready_titles_not_confirmed():
    """Returns (False, message) when titles are missing."""
    confirmations = {
        "de": _make_confirmation("de", confirmed=True),
        "fr": _make_confirmation("fr", confirmed=False),
    }
    ready, msg = is_translation_ready(
        confirmations=confirmations,
        selected_languages=["de", "fr"],
        epub_loaded=True,
    )

    assert ready is False
    assert "Titles not yet confirmed" in msg
    assert "fr" in msg
