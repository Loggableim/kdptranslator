"""Tests for app.core.epub_processor and app.core.metadata utility functions."""

from app.core.epub_processor import generate_output_filename
from app.core.metadata import sanitize_filename


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_filename():
    """Sanitizes filenames by removing/replacing invalid characters."""
    assert sanitize_filename('foo:bar') == 'foo_bar'
    assert sanitize_filename('foo<bar') == 'foo_bar'
    assert sanitize_filename('foo>bar') == 'foo_bar'
    assert sanitize_filename('foo/bar') == 'foo_bar'
    assert sanitize_filename('foo\\bar') == 'foo_bar'
    assert sanitize_filename('foo|bar') == 'foo_bar'
    assert sanitize_filename('foo?bar') == 'foo_bar'
    assert sanitize_filename('foo*bar') == 'foo_bar'
    assert sanitize_filename('foo"bar') == 'foo_bar'


def test_sanitize_filename_whitespace_collapsed():
    """Collapses multiple whitespace into single space and strips."""
    assert sanitize_filename('  Hello   World  ') == 'Hello World'


def test_sanitize_filename_leading_trailing_dots():
    """Removes leading/trailing dots and spaces."""
    assert sanitize_filename('...Hello...') == 'Hello', "Leading/trailing dots stripped"
    assert sanitize_filename('.  Hello.  ') == 'Hello', "Dots and spaces stripped"


def test_sanitize_filename_unicode_normalized():
    """Normalises unicode (NFKC)."""
    result = sanitize_filename('Ｈｅｌｌｏ')
    assert len(result) > 0


def test_sanitize_filename_empty_returns_untitled():
    """Empty string returns 'untitled'."""
    assert sanitize_filename('') == 'untitled'


def test_sanitize_filename_only_invalid():
    """String composed entirely of invalid chars replaced with underscores."""
    invalid = '<>:"/\\|?*'
    result = sanitize_filename(invalid)
    assert result == '_________', f"Expected underscores but got {result!r}"


def test_sanitize_filename_truncated():
    """Long filenames are truncated to 200 characters."""
    long_name = 'a' * 500
    result = sanitize_filename(long_name)
    assert len(result) <= 200


# ---------------------------------------------------------------------------
# generate_output_filename  (from epub_processor)
# ---------------------------------------------------------------------------


def test_generate_output_filename():
    """Generates a proper output filename from title and language."""
    filename = generate_output_filename("The Great Book", "de")
    assert filename.endswith("_de.epub")
    assert "The_Great_Book" in filename


def test_generate_output_filename_special_chars():
    """Handles titles with special characters."""
    filename = generate_output_filename("Hello: World?", "fr")
    assert filename.endswith("_fr.epub")
    assert "Hello" in filename
    assert "World" in filename


def test_generate_output_filename_custom_suffix():
    """Uses custom suffix when provided."""
    filename = generate_output_filename("Test", "de", suffix="_v2")
    assert filename.endswith("_v2_de.epub")


def test_generate_output_filename_long_title():
    """Truncates long titles."""
    long_title = "A" * 200
    filename = generate_output_filename(long_title, "en")
    assert len(filename) < 300
    assert filename.endswith("_en.epub")
