"""Tests for app.core.html_translator."""

from app.core.html_translator import extract_text_chunks, apply_translation


# ---------------------------------------------------------------------------
# extract_text_chunks
# ---------------------------------------------------------------------------


def test_extract_text_chunks_basic():
    """Extracts text from simple paragraphs."""
    html = "<html><body><p>Hello world.</p><p>Second paragraph.</p></body></html>"
    chunks = extract_text_chunks(html)

    assert len(chunks) == 2
    assert chunks[0].text == "Hello world."
    assert chunks[1].text == "Second paragraph."
    assert chunks[0].xpath == "/html/body/p[1]"
    assert chunks[1].xpath == "/html/body/p[2]"


def test_extract_text_chunks_skips_script():
    """Skips script tags."""
    html = "<html><body><p>Visible text.</p><script>var x = 1;</script></body></html>"
    chunks = extract_text_chunks(html)

    assert len(chunks) == 1
    assert chunks[0].text == "Visible text."


def test_extract_text_chunks_skips_style():
    """Skips style tags."""
    html = "<html><body><p>Visible text.</p><style>body { color: red; }</style></body></html>"
    chunks = extract_text_chunks(html)

    assert len(chunks) == 1
    assert chunks[0].text == "Visible text."


def test_extract_text_chunks_skips_nav():
    """Skips nav tags."""
    html = "<html><body><nav>Navigation</nav><p>Content.</p></body></html>"
    chunks = extract_text_chunks(html)

    assert len(chunks) == 1
    assert chunks[0].text == "Content."


def test_extract_text_chunks_numbers_only_skipped():
    """Skips numeric-only text."""
    html = "<html><body><p>42</p><p>3.14</p><p>Real text here.</p></body></html>"
    chunks = extract_text_chunks(html)

    assert len(chunks) == 1
    assert chunks[0].text == "Real text here."


def test_extract_text_chunks_empty_result():
    """Returns empty list for content with no translatable text."""
    html = "<html><body><script>only script</script></body></html>"
    assert extract_text_chunks(html) == []


def test_extract_text_chunks_preserves_inner_html():
    """Inner_html retains inline tags."""
    html = '<html><body><p>Hello <strong>world</strong>!</p></body></html>'
    chunks = extract_text_chunks(html)

    assert len(chunks) == 1
    assert chunks[0].text == "Hello world!"
    assert '<strong>world</strong>' in chunks[0].inner_html


def test_extract_text_chunks_headings():
    """Extracts text from heading elements."""
    html = '<html><body><h1>Title</h1><h2>Subtitle</h2></body></html>'
    chunks = extract_text_chunks(html)

    assert len(chunks) == 2
    assert chunks[0].text == "Title"
    assert chunks[1].text == "Subtitle"


def test_extract_text_chunks_list_items():
    """Extracts text from list items."""
    html = '<html><body><ul><li>Item one</li><li>Item two</li></ul></body></html>'
    chunks = extract_text_chunks(html)

    assert len(chunks) == 2
    assert chunks[0].text == "Item one"
    assert chunks[1].text == "Item two"


# ---------------------------------------------------------------------------
# apply_translation
# ---------------------------------------------------------------------------


def test_apply_translation_basic():
    """Applies translation correctly for simple text."""
    html = "<html><body><p>Hello world.</p></body></html>"
    translations = {"Hello world.": "Hola mundo."}
    result = apply_translation(html, translations)

    assert "Hola mundo." in result
    assert "<p>" in result


def test_apply_translation_preserves_inline_tags():
    """Preserves <strong>, <em>, etc. while applying translation."""
    html = '<html><body><p>Hello <strong>world</strong>!</p></body></html>'
    translations = {"Hello world!": "¡Hola mundo!"}
    result = apply_translation(html, translations)

    # The inline tag should be preserved
    assert "<strong>" in result, "Inline <strong> tag should be preserved"
    assert "</strong>" in result, "Closing </strong> tag should be preserved"
    # The translated text should be distributed across inline tags
    assert "mundo" in result, "Translated text should appear in result"
    # The original English text should be replaced
    assert "Hello" not in result, "Original text should be replaced"


def test_apply_translation_preserves_attributes():
    """Preserves HTML attributes like href, class, id."""
    html = '<html><body><p class="intro" id="p1">Hello world.</p></body></html>'
    translations = {"Hello world.": "Hola mundo."}
    result = apply_translation(html, translations)

    assert 'class="intro"' in result
    assert 'id="p1"' in result
    assert "Hola mundo." in result


def test_apply_translation_empty_returns_unchanged():
    """Empty translations dict returns original HTML unchanged."""
    html = "<html><body><p>Hello world.</p></body></html>"
    result = apply_translation(html, {})

    assert result == html


def test_apply_translation_multiple_paragraphs():
    """Translates multiple paragraphs independently."""
    html = "<html><body><p>First.</p><p>Second.</p></body></html>"
    translations = {"First.": "Primero.", "Second.": "Segundo."}
    result = apply_translation(html, translations)

    assert "Primero." in result
    assert "Segundo." in result
    assert "First." not in result
    assert "Second." not in result


def test_apply_translation_unknown_text_unchanged():
    """Text not in translations dict remains unchanged."""
    html = "<html><body><p>Keep this.</p><p>Change this.</p></body></html>"
    translations = {"Change this.": "Cambia esto."}
    result = apply_translation(html, translations)

    assert "Keep this." in result
    assert "Cambia esto." in result


def test_apply_translation_skip_tags_not_translated():
    """Content inside script/style/nav is not affected."""
    html = "<html><body><p>Visible.</p><script>var x = 'Keep';</script></body></html>"
    translations = {"Visible.": "Visible."}
    result = apply_translation(html, translations)

    assert "var x = 'Keep'" in result
