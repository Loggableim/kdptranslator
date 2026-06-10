"""Tests for the chunker module."""

from app.core.chunker import (
    Chunk,
    chunk_text,
    merge_chunks,
    validate_chunk_order,
)


# ---------------------------------------------------------------------------
# chunk_text: basic behaviour
# ---------------------------------------------------------------------------


def test_chunk_text_basic():
    """Simple text is split into chunks respecting max_chars."""
    text = "Hello world. " * 100
    chunks = chunk_text(text, chapter_id="test", chapter_order=0, max_chars=500)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.original_text) > 0
        assert c.chapter_id == "test"
        assert c.chapter_order == 0


def test_chunk_text_paragraph_boundaries():
    """Respects paragraph breaks (blank lines)."""
    text = "Short para.\n\nAnother para.\n\n\nYet another."
    chunks = chunk_text(text, chapter_id="ch1", chapter_order=0, max_chars=2000)
    assert len(chunks) >= 1


def test_chunk_text_max_chars():
    """Does not exceed max_chars unless forced by a single sentence."""
    text = "A short sentence. " * 10
    chunks = chunk_text(text, chapter_id="ch1", chapter_order=0, max_chars=100)
    for c in chunks:
        assert len(c.original_text) <= 100, (
            f"Chunk {c.chunk_order} exceeds max_chars: {len(c.original_text)}"
        )


def test_chunk_text_oversized_paragraph():
    """Splits a single long paragraph that exceeds max_chars."""
    sentence = "This is a sentence that goes on for a bit of length. "
    text = (sentence * 30).strip()
    chunks = chunk_text(text, chapter_id="ch1", chapter_order=0, max_chars=200)
    assert len(chunks) >= 2, "Oversized paragraph should be split into multiple chunks"
    for c in chunks:
        assert len(c.original_text) > 0
    # All original content should be recoverable (whitespace may differ)
    all_text = " ".join(c.original_text.replace("\n", " ") for c in chunks)
    assert "This is a sentence that goes on for a bit of length" in all_text
    assert all_text.count("a bit of length") == 30, "All 30 sentences should be present"


# ---------------------------------------------------------------------------
# merge_chunks
# ---------------------------------------------------------------------------


def test_merge_chunks_order():
    """Merges chunks in correct order."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="First part. "),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="Second part."),
    ]
    merged = merge_chunks(chunks)
    assert "First part" in merged
    assert "Second part" in merged


def test_merge_chunks_uses_translated():
    """Uses translated_text when available."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="Hello", translated_text="Hallo"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="World", translated_text="Welt"),
    ]
    merged = merge_chunks(chunks)
    assert "Hallo" in merged
    assert "Welt" in merged
    assert "Hello" not in merged


def test_merge_chunks_falls_back_to_original():
    """Falls back to original_text when translated_text is None."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="Hello"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="World"),
    ]
    merged = merge_chunks(chunks)
    assert "Hello" in merged
    assert "World" in merged


# ---------------------------------------------------------------------------
# validate_chunk_order
# ---------------------------------------------------------------------------


def test_validate_chunk_order_valid():
    """Valid sequential order returns True."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="A"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="B"),
    ]
    assert validate_chunk_order(chunks) is True


def test_validate_chunk_order_gap():
    """Gap in order returns False."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="A"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=2,
              original_text="B"),
    ]
    assert validate_chunk_order(chunks) is False


def test_validate_chunk_order_non_zero_start():
    """Non-zero start returns False."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="A"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=2,
              original_text="B"),
    ]
    assert validate_chunk_order(chunks) is False


def test_validate_chunk_order_empty():
    """Empty list returns True."""
    assert validate_chunk_order([]) is True


def test_validate_chunk_order_multiple_chapters():
    """Multiple chapters are validated independently."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="A"),
        Chunk(chunk_id="b", chapter_id="ch1", chapter_order=0, chunk_order=1,
              original_text="B"),
        Chunk(chunk_id="c", chapter_id="ch2", chapter_order=1, chunk_order=0,
              original_text="C"),
    ]
    assert validate_chunk_order(chunks) is True


def test_validate_chunk_order_multiple_chapters_gap():
    """Gap in one chapter among multiple returns False."""
    chunks = [
        Chunk(chunk_id="a", chapter_id="ch1", chapter_order=0, chunk_order=0,
              original_text="A"),
        Chunk(chunk_id="b", chapter_id="ch2", chapter_order=1, chunk_order=0,
              original_text="B"),
        Chunk(chunk_id="c", chapter_id="ch2", chapter_order=1, chunk_order=2,
              original_text="C"),
    ]
    assert validate_chunk_order(chunks) is False
