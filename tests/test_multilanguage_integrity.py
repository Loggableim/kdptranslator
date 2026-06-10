"""Test that each language gets a FRESH EpubProcessor (not reused from previous language).

The key design invariant tested here:

  - Two :class:`EpubProcessor` instances loaded from the same file are completely
    independent — modifying text in one does **not** affect the other.
  - Calling :meth:`~EpubProcessor.get_chapters` again after modifications
    reloads from the original file, giving a fresh view.
  - When :class:`~app.services.translation_service.TranslationService` starts
    a translation for multiple languages it creates a brand-new processor per
    language, ensuring each language translates the **original** content.
"""
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from app.core.epub_processor import EpubProcessor

# Path to the test fixture EPUB shipped with the repo
_TEST_EPUB = str(Path(__file__).resolve().parent.parent / "input" / "test_book.epub")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_opf_language(epub_path: str) -> str:
    """Return the ``<dc:language>`` value inside *epub_path*."""
    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        opf = [n for n in names if n.endswith(".opf")]
        if not opf:
            raise AssertionError(f"No OPF file in {epub_path}")
        content = zf.read(opf[0]).decode("utf-8")
    # Simple XML tag parse
    import re

    m = re.search(r"<dc:language[^>]*>(.*?)</dc:language>", content)
    if m:
        return m.group(1).strip()
    m = re.search(r'<dc:language[^>]*\s+(\w{2,5})\s*/>', content)
    if m:
        return m.group(1).strip()
    raise AssertionError(f"Could not extract language from OPF: {opf[0]}")


# ---------------------------------------------------------------------------
# Instance independence
# ---------------------------------------------------------------------------


def test_processor_independence():
    """Two EpubProcessor instances from the same file are independent.

    Modifying chapter text in one does **not** affect the other.
    """
    proc_a = EpubProcessor(_TEST_EPUB)
    proc_b = EpubProcessor(_TEST_EPUB)

    chapters_a = proc_a.get_chapters()
    chapters_b = proc_b.get_chapters()

    # Both start identical
    assert len(chapters_a) == len(chapters_b)
    for ca, cb in zip(chapters_a, chapters_b):
        assert ca.html_content == cb.html_content
        assert len(ca.text_nodes) == len(cb.text_nodes)

    # ---- Modify a chapter in proc_a ----
    ch = chapters_a[0]
    fake_translation = [
        f"[LANG:TEST] {n['text']}" for n in ch.text_nodes
    ]
    proc_a.update_chapter_text(ch.id, fake_translation)

    # proc_a was changed
    ch_a_updated = proc_a._find_chapter(ch.id)
    assert "[LANG:TEST]" in ch_a_updated.html_content

    # proc_b still has the original content
    ch_b_unchanged = proc_b._find_chapter(ch.id)
    assert "[LANG:TEST]" not in ch_b_unchanged.html_content
    assert ch_b_unchanged.html_content == chapters_b[0].html_content


def test_processor_independence_multiple_chapters():
    """Modification isolation holds across all chapters."""
    proc = EpubProcessor(_TEST_EPUB)
    chapters = proc.get_chapters()
    assert len(chapters) >= 2, "Test EPUB must have at least 2 chapters"

    # Modify first chapter in one processor
    proc_a = EpubProcessor(_TEST_EPUB)
    proc_b = EpubProcessor(_TEST_EPUB)
    ch_a = proc_a.get_chapters()[0]
    ch_b = proc_b.get_chapters()[0]

    translated = ["[MUTATION]"] * len(ch_a.text_nodes)
    proc_a.update_chapter_text(ch_a.id, translated)

    # Second chapter in proc_b should be untouched
    ch_b_second = proc_b.get_chapters()[1]
    # Also proc_a's second chapter should still be original
    ch_a_second = proc_a.get_chapters()[1]

    assert "[MUTATION]" not in ch_a_second.html_content
    assert "[MUTATION]" not in ch_b_second.html_content


# ---------------------------------------------------------------------------
# Multi-language save independence
# ---------------------------------------------------------------------------


def test_processor_saves_independent_languages():
    """Two processors can be saved with different languages independently.

    Each output EPUB carries the correct language metadata.
    """
    proc_de = EpubProcessor(_TEST_EPUB)
    proc_fr = EpubProcessor(_TEST_EPUB)
    proc_de.get_chapters()
    proc_fr.get_chapters()

    tmpdir = tempfile.mkdtemp()
    try:
        out_de = proc_de.save(
            os.path.join(tmpdir, "out_de.epub"),
            title="German Title",
            language="de",
        )
        out_fr = proc_fr.save(
            os.path.join(tmpdir, "out_fr.epub"),
            title="French Title",
            language="fr",
        )

        assert os.path.isfile(out_de), f"Missing output: {out_de}"
        assert os.path.isfile(out_fr), f"Missing output: {out_fr}"

        assert _read_opf_language(out_de) == "de", "German EPUB has wrong language"
        assert _read_opf_language(out_fr) == "fr", "French EPUB has wrong language"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fresh-reload behaviour (used per-language in TranslationService)
# ---------------------------------------------------------------------------


def test_get_chapters_reloads_from_disk():
    """A fresh EpubProcessor always loads the original file content.

    This is exactly what TranslationService.start_translation() relies on:
    each language creates a NEW processor from the original file path,
    so every language gets a clean, unmodified view of the source EPUB.
    """
    proc1 = EpubProcessor(_TEST_EPUB)
    chapters_first = proc1.get_chapters()

    # Store original content before mutation
    original_content = chapters_first[0].html_content

    # Mutate the first processor's content
    ch = chapters_first[0]
    translated = ["[DIRTY]"] * len(ch.text_nodes)
    proc1.update_chapter_text(ch.id, translated)

    # Verify the mutation stuck on proc1
    ch_mutated = proc1._find_chapter(ch.id)
    assert "[DIRTY]" in ch_mutated.html_content

    # Create a FRESH processor from the same file
    proc2 = EpubProcessor(_TEST_EPUB)
    chapters_second = proc2.get_chapters()

    # The content should be back to the original (uncorrupted)
    ch_reloaded = chapters_second[0]
    assert "[DIRTY]" not in ch_reloaded.html_content
    assert ch_reloaded.html_content == original_content, (
        "Reloaded content should match the original file content, "
        "not the mutated version"
    )


# ---------------------------------------------------------------------------
# Service-level: TranslationService.analyze_epub creates fresh processors
# ---------------------------------------------------------------------------


def test_analyze_epub_creates_fresh_processor():
    """Each call to analyze_epub() replaces the internal processor.

    This ensures that if the user analyses a second file, the old processor
    state is not reused.
    """
    from app.core.config import TranslationConfig
    from app.providers.mock import MockTranslationProvider
    from app.services.translation_service import TranslationService

    provider = MockTranslationProvider()
    config = TranslationConfig()
    service = TranslationService(provider=provider, config=config)

    analysis1 = service.analyze_epub(_TEST_EPUB)
    proc1 = service._epub_processor

    analysis2 = service.analyze_epub(_TEST_EPUB)
    proc2 = service._epub_processor

    assert proc1 is not proc2, (
        "analyze_epub() must create a fresh EpubProcessor, "
        "not reuse the previous one"
    )
    assert analysis1 is not analysis2
    assert analysis1.title == analysis2.title
