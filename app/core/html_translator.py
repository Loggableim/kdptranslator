"""
HTML text extraction and translation application for KDP Translator.

Provides pure functions for:
- Extracting translatable text chunks from HTML while preserving inline tags.
- Applying translated text back into the original HTML structure.

Usage:
    chunks = extract_text_chunks("<p>Hello <strong>world</strong></p>")
    # -> [TextChunk(text='Hello world', xpath='/html/body/p[1]',
    #               inner_html='Hello <strong>world</strong>')]

    translations = {"Hello world": "Hola mundo"}
    result = apply_translation("<p>Hello <strong>world</strong></p>", translations)
    # -> "<p>Hola <strong>mundo</strong></p>"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag, Comment

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "blockquote", "div",
})

SKIP_TAGS = frozenset({
    "script", "style", "nav", "head", "meta",
})

# Inline tags whose inner text is translatable and whose structure must be
# preserved during application.
INLINE_TAGS = frozenset({
    "strong", "em", "b", "i", "u", "sub", "sup",
    "a", "span", "br", "q", "code", "mark", "small",
    "abbr", "cite", "dfn", "kbd", "samp", "var", "time",
    "del", "ins", "s", "tt", "wbr",
})

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """A translatable text fragment extracted from an HTML element.

    Attributes:
        text:       Plain text content (HTML stripped, whitespace
                    normalised). This is the text the translation engine
                    should translate.
        xpath:      XPath expression that identifies the containing
                    block-level element in the original document.
        inner_html: Raw inner HTML of the element with inline tags
                    preserved. Used internally during translation
                    application.
    """
    text: str
    xpath: str
    inner_html: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup instance choosing the best parser.

    Uses ``lxml-xml`` (the XML parser) when the document appears to be
    XHTML (has an XML declaration or an ``xmlns`` attribute on the root
    element).  Otherwise uses ``lxml`` (the HTML5 parser).

    Args:
        html: Raw HTML/XHTML string.

    Returns:
        A ``BeautifulSoup`` instance.
    """
    stripped = html.lstrip()
    if stripped.startswith("<?xml") or "xmlns=" in stripped[:1000]:
        return BeautifulSoup(html, "lxml-xml")
    return BeautifulSoup(html, "lxml")


def _build_xpath(element: Tag) -> str:
    """Build a minimal XPath expression locating *element* in its document.

    The path uses tag names with positional predicates (1-based) only
    when needed for disambiguation.

    Args:
        element: A ``Tag`` in a parsed BeautifulSoup tree.

    Returns:
        XPath string (e.g. ``/html/body/div[2]/p[1]``).
    """
    parts: List[str] = []

    # Walk from element up through ancestors
    for ancestor in [element] + list(element.parents):
        if not isinstance(ancestor, Tag):
            continue
        name = ancestor.name
        if name in ("[document]", None):
            continue

        parent = ancestor.parent
        if not isinstance(parent, Tag):
            # We have reached the root (html tag or similar)
            parts.append(name)
            break

        # Count same-tag siblings
        same_tag_siblings = [
            s for s in parent.children
            if isinstance(s, Tag) and s.name == name
        ]

        if len(same_tag_siblings) == 1:
            parts.append(name)
        else:
            # Find this element's position among siblings
            pos = 1
            for s in parent.children:
                if s is ancestor:
                    break
                if isinstance(s, Tag) and s.name == name:
                    pos += 1
            parts.append(f"{name}[{pos}]")

    return "/" + "/".join(reversed(parts))


def _should_skip_element(element: Tag) -> bool:
    """Return ``True`` if *element* or any of its ancestors is inside a
    skip tag (``<script>``, ``<style>``, ``<nav>``, ``<head>``,
    ``<meta>``)."""
    for parent in element.parents:
        if isinstance(parent, Tag) and parent.name in SKIP_TAGS:
            return True
    return False


def _collect_text_segments(element: Tag) -> List[str]:
    """Collect text segments from *element*, excluding text that belongs
    to nested block-level children.

    This walks only direct ``NavigableString`` children and recurses
    into inline tag children.  Block-level children are intentionally
    skipped because they will be handled as separate ``TextChunk``
    instances.

    Args:
        element: A block-level ``Tag``.

    Returns:
        A list of text strings in document order.
    """
    segments: List[str] = []
    for child in element.children:
        if isinstance(child, Comment):
            # Comments are not translatable text
            continue
        if isinstance(child, NavigableString):
            segments.append(str(child))
        elif isinstance(child, Tag):
            if child.name not in BLOCK_TAGS:
                # Inline (or unknown non-block) tag — recurse
                segments.extend(_collect_text_segments(child))
            # Block-level children are intentionally skipped
    return segments


def _normalise_text(text: str) -> str:
    """Collapse runs of whitespace into a single space and strip leading
    / trailing whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _should_skip(text: str) -> bool:
    """Return ``True`` if *text* should NOT be sent for translation.

    Criteria: empty, whitespace-only, numbers-only, or pure
    punctuation/symbols (no word characters).
    """
    t = text.strip()
    if not t:
        return True
    # Digits only (e.g. "42", "3.14")
    if re.match(r"^\d+(?:[.,]\d+)?$", t):
        return True
    # No word characters at all (punctuation-only, symbols-only)
    if not re.search(r"\w", t):
        return True
    return False


def _collect_text_nodes(
    parent: Tag,
    *,
    skip_block: bool = True,
) -> List[NavigableString]:
    """Collect all ``NavigableString`` descendants of *parent*,
    excluding those inside nested block elements when ``skip_block`` is
    ``True``.

    Comments are excluded from the result.

    Args:
        parent:     A ``Tag`` to search within.
        skip_block: If ``True``, text inside nested block elements is
                    excluded (default ``True``).

    Returns:
        A list of ``NavigableString`` nodes in document order.
    """
    nodes: List[NavigableString] = []

    def _walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                nodes.append(child)
            elif isinstance(child, Tag):
                if skip_block and child.name in BLOCK_TAGS:
                    continue
                _walk(child)

    _walk(parent)
    return nodes


def _word_tokenize(text: str) -> List[str]:
    """Split *text* into words (whitespace-separated sequences)."""
    return re.findall(r"\S+", text)


def _preserve_whitespace(original: str, replacement: str) -> str:
    """Transfer leading and trailing whitespace from *original* to
    *replacement*.

    The inner content of *replacement* is stripped so that whitespace
    from *original* is used instead.
    """
    leading = re.match(r"^(\s*)", original)
    trailing = re.search(r"(\s*)$", original)
    lead = leading.group(1) if leading else ""
    trail = trailing.group(1) if trailing else ""
    return lead + replacement.strip() + trail


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text_chunks(html: str) -> List[TextChunk]:
    """Extract translatable text chunks from an HTML string.

    Visible text is extracted from block-level elements:
    ``<p>``, ``<h1>``–``<h6>``, ``<li>``, ``<td>``, ``<th>``,
    ``<blockquote>``, and ``<div>``.

    Text nested inside other block elements (e.g. a ``<p>`` inside a
    ``<div>``) is treated as a separate chunk.  Inline tags such as
    ``<strong>``, ``<em>``, ``<a>``, ``<span>``, and ``<br/>`` are
    preserved in ``inner_html`` but stripped from ``text``.

    Chunks consisting solely of digits, whitespace, or punctuation are
    excluded.

    Args:
        html: Raw HTML/XHTML string.

    Returns:
        A list of ``TextChunk`` objects in document order.
    """
    soup = _create_soup(html)
    chunks: List[TextChunk] = []

    for element in soup.find_all(BLOCK_TAGS):
        if _should_skip_element(element):
            continue

        # Collect text segments (excluding nested block children)
        segments = _collect_text_segments(element)
        if not segments:
            continue

        plain_text = _normalise_text("".join(segments))
        if _should_skip(plain_text):
            continue

        inner_html = "".join(str(c) for c in element.children)
        xpath = _build_xpath(element)

        chunks.append(TextChunk(
            text=plain_text,
            xpath=xpath,
            inner_html=inner_html,
        ))

    return chunks


def apply_translation(html: str, translations: Dict[str, str]) -> str:
    """Apply translations to an HTML string.

    The *translations* dict maps original plain text (as returned by
    :func:`extract_text_chunks`) to translated plain text.  For each
    target element whose plain text matches a key in the dict, the
    element's content is replaced while preserving inline tags.

    Inline tags (``<strong>``, ``<em>``, ``<b>``, ``<i>``, ``<a>``,
    ``<span>``, ``<br/>``, etc.) are kept in place.  Only the text
    content of text nodes is replaced.  Word-level proportional
    allocation ensures that multi-word text inside inline tags is
    distributed sensibly when the translation has a different number of
    words than the original.

    All HTML attributes are preserved unchanged.

    Args:
        html:         Original HTML/XHTML string.
        translations: Mapping of original → translated plain text.

    Returns:
        The updated HTML string with translations applied.
    """
    if not translations:
        return html

    soup = _create_soup(html)

    for element in soup.find_all(BLOCK_TAGS):
        if _should_skip_element(element):
            continue

        # Get the plain text (same logic as extraction)
        segments = _collect_text_segments(element)
        if not segments:
            continue
        plain_text = _normalise_text("".join(segments))
        if not plain_text:
            continue

        translated = translations.get(plain_text)
        if translated is None:
            continue

        # Collect text nodes inside this element (excluding block children)
        text_nodes = _collect_text_nodes(element, skip_block=True)
        if not text_nodes:
            continue

        # Count original words per text node
        orig_words_per_node: List[List[str]] = []
        total_orig_words = 0
        for node in text_nodes:
            words = _word_tokenize(str(node))
            orig_words_per_node.append(words)
            total_orig_words += len(words)

        if total_orig_words == 0:
            continue

        trans_words = _word_tokenize(translated)
        total_trans_words = len(trans_words)

        # Word-level proportional distribution
        cursor = 0
        for i, node in enumerate(text_nodes):
            orig_word_count = len(orig_words_per_node[i])
            if orig_word_count == 0:
                # Only whitespace in this segment — preserve as-is
                node.replace_with(NavigableString(str(node)))
                continue

            if i == len(text_nodes) - 1:
                # Last node gets all remaining words
                assigned_words = trans_words[cursor:]
            else:
                # Proportional allocation (at least 1 word)
                ratio = orig_word_count / max(total_orig_words, 1)
                chunk_size = max(1, round(total_trans_words * ratio))
                assigned_words = trans_words[cursor:cursor + chunk_size]
                cursor += chunk_size

            assigned_text = " ".join(assigned_words)
            full_text = _preserve_whitespace(str(node), assigned_text)
            node.replace_with(NavigableString(full_text))

    return str(soup)
