"""
Chunking logic for KDP Translator.

Splits chapter text into manageable chunks for LLM translation while
respecting paragraph boundaries and configurable token limits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Chunk data model
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A single text chunk ready for (or already carrying) translation.

    Attributes
    ----------
    chunk_id:
        Unique identifier (UUID v4 hex string) for this chunk.
    chapter_id:
        Identifies the source chapter this chunk belongs to.
    chapter_order:
        Zero-based ordering of the source chapter within the book.
    chunk_order:
        Zero-based ordering of this chunk within its chapter.
    original_text:
        The untranslated source text carried by this chunk.
    translated_text:
        The target-language translation, populated after translation.
    status:
        Lifecycle status — ``'pending'`` | ``'translated'`` | ``'failed'`` |
        ``'skipped'``.
    retry_count:
        How many times translation has been attempted for this chunk.
    agent_id:
        Identifier of the agent that translated (or is translating) this
        chunk.  ``None`` until a translation attempt is made.
    language:
        ISO 639-1 language code of the *translated* text (or the desired
        target language).  ``None`` until a translation target is known.
    """

    chunk_id: str
    chapter_id: str
    chapter_order: int
    chunk_order: int
    original_text: str
    translated_text: Optional[str] = None
    status: str = "pending"
    retry_count: int = 0
    agent_id: Optional[str] = None
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Paragraph-aware chunking
# ---------------------------------------------------------------------------


def _generate_chunk_id() -> str:
    """Return a hex UUID v4 string to be used as a chunk identifier."""
    return uuid.uuid4().hex


def _split_paragraphs(text: str) -> List[str]:
    """Split *text* into logical paragraphs.

    Paragraphs are separated by one or more blank lines (``\\n\\n`` or more).
    Consecutive blank lines are collapsed so that each returned element is
    a meaningful paragraph — never empty.
    """
    raw = text.split("\n")
    paragraphs: List[str] = []
    buf: List[str] = []

    for line in raw:
        if line.strip() == "":
            # Blank line → flush the buffer as a paragraph (if non-empty).
            if buf:
                paragraphs.append("\n".join(buf))
                buf = []
        else:
            buf.append(line)

    # Flush remaining buffer.
    if buf:
        paragraphs.append("\n".join(buf))

    return paragraphs


def chunk_text(
    text: str,
    chapter_id: str,
    chapter_order: int,
    max_chars: int = 2000,
) -> List[Chunk]:
    """Split *text* into :class:`Chunk` objects respecting paragraph boundaries.

    The algorithm:

    1. Split the input into paragraphs (separated by one or more blank lines).
    2. Accumulate paragraphs into a chunk until adding the next paragraph
       would exceed ``max_chars``.
    3. If a **single** paragraph is longer than ``max_chars`` it is
       forcefully split on sentence boundaries (``.``, ``!``, ``?``) and,
       as a last resort, on the character limit directly.
    4. Each chunk is assigned a stable UUID-based ``chunk_id`` and sequential
       ``chunk_order`` within the chapter.

    Parameters
    ----------
    text:
        The full chapter text to split.
    chapter_id:
        An identifier for the source chapter (e.g. a filename stem or DB key).
    chapter_order:
        Zero-based position of the chapter in the book.
    max_chars:
        Maximum *characters* allowed per chunk (default ``2000``).  This is
        a soft upper bound — individual oversized paragraphs will be broken
        at sentence boundaries, so a single resulting chunk may slightly
        exceed ``max_chars`` if a sentence is itself longer.

    Returns
    -------
    List[Chunk]
        The ordered list of chunks for the chapter.
    """
    paragraphs = _split_paragraphs(text)
    chunks: List[Chunk] = []
    chunk_order = 0

    def _flush(buf_paras: List[str]) -> None:
        nonlocal chunk_order
        joined = "\n\n".join(buf_paras)
        chunks.append(
            Chunk(
                chunk_id=_generate_chunk_id(),
                chapter_id=chapter_id,
                chapter_order=chapter_order,
                chunk_order=chunk_order,
                original_text=joined,
            )
        )
        chunk_order += 1

    # ------------------------------------------------------------------
    # Helper: split an over-long paragraph at sentence boundaries
    # ------------------------------------------------------------------
    def _split_long_paragraph(long_para: str) -> List[str]:
        """Break a single paragraph that exceeds ``max_chars``."""
        # Sentence-ending punctuation followed by whitespace.
        fragments: List[str] = []
        start = 0
        for pos, ch in enumerate(long_para):
            if ch in (".", "!", "?"):
                # Include the punctuation and any trailing spaces/newlines
                # up to the start of the next sentence.
                end = pos + 1
                while end < len(long_para) and long_para[end] in (
                    " ",
                    "\t",
                    "\n",
                    "\r",
                ):
                    end += 1
                fragment = long_para[start:end].strip()
                if fragment:
                    fragments.append(fragment)
                start = end

        # Remaining text after the last sentence-ending punctuation.
        remaining = long_para[start:].strip()
        if remaining:
            fragments.append(remaining)

        # If sentence-splitting didn't help or there were no sentence
        # boundaries, fall back to character-level splitting.
        if not fragments:
            fragments = _split_by_chars(long_para)

        return fragments

    def _split_by_chars(long_text: str) -> List[str]:
        """Last-resort: split text at ``max_chars`` boundaries."""
        parts: List[str] = []
        i = 0
        while i < len(long_text):
            parts.append(long_text[i : i + max_chars])
            i += max_chars
        return parts

    # ------------------------------------------------------------------
    # Main accumulation loop
    # ------------------------------------------------------------------
    buffer: List[str] = []
    buffer_len = 0

    for para in paragraphs:
        para_len = len(para)

        # Can we fit this paragraph as-is?
        if buffer_len + para_len + (2 if buffer else 0) <= max_chars:
            # ``+2`` for the ``\n\n`` separator that will be inserted
            # when joining the buffer.
            buffer.append(para)
            buffer_len += para_len + (2 if len(buffer) > 1 else 0)
            continue

        # The paragraph itself is oversize — we must split it.
        if para_len >= max_chars:
            # Flush any existing buffer first.
            if buffer:
                _flush(buffer)
                buffer = []
                buffer_len = 0

            sub_paras = _split_long_paragraph(para)
            # Re-accumulate sub-paragraphs into chunks.
            for sp in sub_paras:
                if not buffer:
                    # Start a new chunk.
                    buffer.append(sp)
                    buffer_len = len(sp)
                elif buffer_len + 1 + len(sp) <= max_chars:
                    # ``+1`` for the newline that will separate sub-paras
                    # inside the chunk.
                    buffer.append(sp)
                    buffer_len += 1 + len(sp)
                else:
                    _flush(buffer)
                    buffer = [sp]
                    buffer_len = len(sp)
            continue

        # Paragraph fits by itself but not on top of the current buffer.
        _flush(buffer)
        buffer = [para]
        buffer_len = para_len

    # Flush the final buffer.
    if buffer:
        _flush(buffer)

    return chunks


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_chunks(chunks: List[Chunk]) -> str:
    """Reconstruct the full text from a list of chunks in their original order.

    Each chunk contributes its ``translated_text`` if available (not ``None``),
    otherwise its ``original_text``.  Chunks are first sorted by
    ``(chapter_order, chunk_order)`` to ensure correct ordering regardless
    of input order.

    Parameters
    ----------
    chunks:
        The list of chunks to merge, potentially out of order.

    Returns
    -------
    str
        The concatenated text with double-newline paragraph separators
        between chunks.
    """
    if not chunks:
        return ""

    sorted_chunks = sorted(chunks, key=lambda c: (c.chapter_order, c.chunk_order))

    parts: List[str] = []
    for c in sorted_chunks:
        text = c.translated_text if c.translated_text is not None else c.original_text
        parts.append(text)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_chunk_order(chunks: List[Chunk]) -> bool:
    """Verify that chunk ordering is sequential and gap-free.

    For each distinct chapter (identified by ``chapter_id``) the function
    checks that:

    - Chunk orders start at ``0``.
    - Chunk orders are consecutive (no missing numbers).

    Parameters
    ----------
    chunks:
        The list of chunks to validate.

    Returns
    -------
    bool
        ``True`` if all chapters have well-ordered chunks, ``False``
        otherwise.
    """
    if not chunks:
        return True

    from collections import defaultdict

    by_chapter: dict[str, List[int]] = defaultdict(list)
    for c in chunks:
        by_chapter[c.chapter_id].append(c.chunk_order)

    for chapter_id, orders in by_chapter.items():
        orders.sort()
        if orders[0] != 0:
            return False
        for i in range(1, len(orders)):
            if orders[i] != orders[i - 1] + 1:
                return False

    return True
