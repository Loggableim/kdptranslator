"""EPUB processing module for KDP Translator.

Provides complete EPUB reading, analysis, and writing with full structure
preservation including cover images, CSS, fonts, media, and TOC/NCX.

Dependencies
------------
- ebooklib  : load / write EPUB files
- beautifulsoup4 + lxml : parse and manipulate HTML content
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString
from ebooklib import epub

from app.core.logger import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Chapter:
    """Represents a single EPUB chapter (an HTML document item).

    Attributes
    ----------
    id : str
        Unique identifier for the chapter (e.g. ``chapter_0``).
    order : int
        Zero-based index reflecting the order in which the chapter
        appears in the EPUB spine.
    title : str
        Extracted title (from ``<title>``, ``<h1>``, or a fallback).
    file_name : str
        Relative path of the file inside the EPUB (e.g. ``OEBPS/ch01.xhtml``).
    html_content : str
        The full HTML source of the chapter.
    text_nodes : list[dict]
        Visible text nodes extracted from the chapter.
        Each dict has the keys:
        - ``id``: unique string (``chunk_0``, ``chunk_1``, …)
        - ``text``: the visible text content
        - ``parent_tag``: tag name of the containing element (e.g. ``p``)
    """

    id: str
    order: int
    title: str
    file_name: str
    html_content: str
    text_nodes: List[dict] = field(default_factory=list)


@dataclass
class EpubAnalysis:
    """Result of analysing an EPUB file.

    Attributes
    ----------
    title : str
        Book title from OPF metadata.
    subtitle : str
        Subtitle (if stored as an OPF meta property).
    description : str
        Book description from DC metadata.
    language : str
        Language code (ISO 639-1, e.g. ``en``).
    genre : str
        Subject / genre from DC metadata.
    chapters : list[Chapter]
        The list of chapters found in the EPUB.
    cover_path : str or None
        Internal path of the cover image, if any.
    metadata : dict[str, str]
        Raw metadata key-value pairs from the OPF file.
    """

    title: str = ""
    subtitle: str = ""
    description: str = ""
    language: str = ""
    genre: str = ""
    chapters: List[Chapter] = field(default_factory=list)
    cover_path: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


# Tags whose text content should be excluded from translation.
# We skip these entirely — their content is not visible to the reader.
_EXCLUDED_TAGS: set = {
    "script",
    "style",
    "nav",
    "head",
    "meta",
    "link",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "math",
}

# ---------------------------------------------------------------------------
# EPUB processor
# ---------------------------------------------------------------------------


class EpubProcessor:
    """Read, analyse, and write EPUB files while preserving all structure.

    Typical workflow::

        proc = EpubProcessor("input.epub")
        chapters = proc.get_chapters()           # extract text nodes
        for ch in chapters:
            chunks = [n["text"] for n in ch.text_nodes]
            translated = translate(chunks)        # external call
            proc.update_chapter_text(ch.id, translated)
        proc.save("output.epub", title="Translated Title", language="de")
    """

    def __init__(self, filepath: str) -> None:
        self._filepath: str = filepath
        self._book: Optional[epub.EpubBook] = None
        self._chapters: List[Chapter] = []
        self._text_node_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_chapters(self) -> List[Chapter]:
        """Load the EPUB and extract all chapters with visible text nodes.

        Each chapter's ``text_nodes`` list contains every visible text
        fragment in document order.  Content inside ``script``, ``style``,
        ``nav``, ``head``, and similar non-visible elements is excluded.
        Whitespace-only nodes are also skipped.

        Returns
        -------
        list[Chapter]
            Chapters with ``id``, ``order``, ``title``, ``file_name``,
            ``html_content``, and ``text_nodes`` populated.
        """
        self._chapters.clear()
        self._text_node_counter = 0

        self._book = epub.read_epub(self._filepath)

        doc_items: List[Any] = [
            item
            for item in self._book.get_items()
            if item.get_type() == ebooklib.ITEM_DOCUMENT
        ]

        for order, item in enumerate(doc_items):
            raw: bytes = item.get_content()
            content: str = raw.decode("utf-8", errors="replace")

            chapter_id = f"chapter_{order}"
            title = self._extract_title(content, order)
            file_name: str = item.get_name()

            text_nodes = self._extract_text_nodes(content)

            chapter = Chapter(
                id=chapter_id,
                order=order,
                title=title,
                file_name=file_name,
                html_content=content,
                text_nodes=text_nodes,
            )
            self._chapters.append(chapter)

        logger.info(
            "Loaded %d chapters from %s", len(self._chapters), self._filepath
        )
        return list(self._chapters)

    def update_chapter_text(
        self, chapter_id: str, translated_chunks: List[str]
    ) -> Chapter:
        """Replace visible text in a chapter with translated content.

        The number of elements in *translated_chunks* **must** equal the
        number of text nodes originally extracted from the chapter.  Each
        element replaces the corresponding text node in document order.

        Parameters
        ----------
        chapter_id : str
            The ``id`` of the chapter to update (e.g. ``chapter_0``).
        translated_chunks : list[str]
            Ordered list of translated text strings, one per original
            text node.

        Returns
        -------
        Chapter
            The same chapter object with an updated ``html_content``.

        Raises
        ------
        ValueError
            If the chapter id does not exist or chunk count mismatches.
        """
        chapter = self._find_chapter(chapter_id)
        if chapter is None:
            raise ValueError(
                f"Chapter not found: {chapter_id!r}. "
                f"Available chapters: {[c.id for c in self._chapters]}"
            )

        expected = len(chapter.text_nodes)
        actual = len(translated_chunks)
        if expected != actual:
            raise ValueError(
                f"Translated chunk count mismatch for chapter "
                f"{chapter_id!r}: expected {expected}, got {actual}"
            )

        updated = self._apply_translation(
            chapter.html_content, translated_chunks
        )
        chapter.html_content = updated
        return chapter

    def save(
        self,
        output_path: str,
        title: str,
        language: str,
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> str:
        """Write a new EPUB file with translated content and metadata.

        The following are automatically preserved:
        - cover images (any ITEM_IMAGE)
        - CSS stylesheets (ITEM_STYLE)
        - embedded fonts (ITEM_FONT)
        - media files (IMAGE, AUDIO, VIDEO)
        - TOC / NCX navigation
        - all other non-document items

        Parameters
        ----------
        output_path : str
            Target file path for the translated EPUB.
        title : str
            Translated (or original) book title.
        language : str
            Target language ISO-639-1 code (e.g. ``de``, ``fr``).
        subtitle : str or None
            Optional translated subtitle.
        description : str or None
            Optional translated description.
        genre : str or None
            Optional book genre / subject.

        Returns
        -------
        str
            Absolute path of the generated EPUB file.
        """
        if self._book is None:
            raise RuntimeError(
                "No EPUB loaded. Call get_chapters() before save()."
            )

        # 1. Write updated chapter content back into the EpubBook items.
        self._flush_chapters_to_book()

        # 2. Update OPF metadata.
        self._update_metadata(title, language, subtitle, description, genre)

        # 3. Ensure output directory exists.
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # 4. Write the EPUB.
        epub.write_epub(str(out), self._book, {})

        resolved = str(out.resolve())
        logger.info("EPUB saved to %s", resolved)
        return resolved

    def analyse(self) -> EpubAnalysis:
        """Return a full analysis of the loaded EPUB.

        Requires that ``get_chapters()`` has already been called.

        Returns
        -------
        EpubAnalysis
            Metadata, cover path, and chapters.
        """
        if self._book is None:
            raise RuntimeError(
                "No EPUB loaded. Call get_chapters() first."
            )
        book = self._book

        # Title
        title = self._get_dc(book, "title", "")

        # Language
        language = self._get_dc(book, "language", "")

        # Description
        description = self._get_dc(book, "description", "")

        # Genre / subject
        genre = self._get_dc(book, "subject", "")

        # Subtitle (stored as OPF meta with property="subtitle")
        subtitle = ""
        for meta in book.get_metadata("OPF", "meta"):
            if isinstance(meta, tuple) and len(meta) >= 2:
                # meta format: (value, {attribs})
                meta_value = meta[0]
                meta_attrs = meta[1] if isinstance(meta[1], dict) else {}
                if meta_attrs.get("property") == "subtitle":
                    subtitle = str(meta_value)
                    break

        # Cover image: look for the first IMAGE item
        cover_path: Optional[str] = None
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                cover_path = item.get_name()
                break

        # Collect all DC metadata
        all_meta: Dict[str, str] = {}
        dc_tags = [
            "title",
            "language",
            "description",
            "subject",
            "creator",
            "publisher",
            "date",
            "identifier",
            "rights",
            "contributor",
            "source",
            "type",
        ]
        for tag in dc_tags:
            val = self._get_dc(book, tag, None)
            if val is not None:
                all_meta[tag] = val

        return EpubAnalysis(
            title=title,
            subtitle=subtitle,
            description=description,
            language=language,
            genre=genre,
            chapters=list(self._chapters),
            cover_path=cover_path,
            metadata=all_meta,
        )

    # ------------------------------------------------------------------
    # Internal helpers — chapter / text processing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(html_content: str, order: int) -> str:
        """Return a human-readable title from the HTML content."""
        soup = BeautifulSoup(html_content, "lxml")

        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            if text:
                return text

        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text

        return f"Chapter {order + 1}"

    def _extract_text_nodes(self, html_content: str) -> List[dict]:
        """Find all visible text nodes in the HTML content.

        Returns a list of dicts with keys ``id``, ``text``, ``parent_tag``.
        """
        soup = BeautifulSoup(html_content, "lxml")
        nodes: List[dict] = []

        for element in soup.descendants:
            if not isinstance(element, NavigableString):
                continue

            parent = element.parent
            if parent is None or parent.name in _EXCLUDED_TAGS:
                continue

            text = str(element).strip()
            if not text:
                continue

            node_id = f"chunk_{self._text_node_counter}"
            self._text_node_counter += 1

            nodes.append(
                {
                    "id": node_id,
                    "text": text,
                    "parent_tag": parent.name,
                }
            )

        return nodes

    @staticmethod
    def _apply_translation(
        html_content: str, translated_chunks: List[str]
    ) -> str:
        """Replace visible text nodes in HTML with translated strings.

        Re-traverses the parse tree identically to ``_extract_text_nodes``
        so that text-node order is guaranteed to match.
        """
        soup = BeautifulSoup(html_content, "lxml")
        chunk_idx = 0

        for element in soup.descendants:
            if not isinstance(element, NavigableString):
                continue

            parent = element.parent
            if parent is None or parent.name in _EXCLUDED_TAGS:
                continue

            if not str(element).strip():
                continue

            if chunk_idx >= len(translated_chunks):
                break

            replacement = translated_chunks[chunk_idx]
            element.replace_with(NavigableString(replacement))
            chunk_idx += 1

        return str(soup)

    def _find_chapter(self, chapter_id: str) -> Optional[Chapter]:
        """Locate a chapter by id.  O(1) via dict if needed in hot paths."""
        for ch in self._chapters:
            if ch.id == chapter_id:
                return ch
        return None

    # ------------------------------------------------------------------
    # Internal helpers — EPUB book manipulation
    # ------------------------------------------------------------------

    def _flush_chapters_to_book(self) -> None:
        """Write updated chapter HTML back into the EpubBook items.

        Matches by file name (``item.get_name()``) so that spine order,
        media-type, and all other item attributes are automatically
        preserved.
        """
        if self._book is None:
            return

        name_map: Dict[str, Chapter] = {
            ch.file_name: ch for ch in self._chapters
        }

        for item in self._book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            chapter = name_map.get(item.get_name())
            if chapter is not None:
                item.set_content(chapter.html_content.encode("utf-8"))

    def _update_metadata(
        self,
        title: str,
        language: str,
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> None:
        """Update the OPF metadata with translated values.

        ebooklib's ``set_title`` and ``set_language`` replace the first
        DC element of that type.  Additional metadata fields are added
        via ``add_metadata``.  Existing entries are *not* removed (the
        EPUB spec expects at least one of each).
        """
        if self._book is None:
            return

        # --- Core DC fields ------------------------------------------------
        self._book.set_title(title)
        self._book.set_language(language)

        # --- Supplementary fields (add_metadata allows duplicates, which
        #     is fine — most readers use the first occurrence) ----------------
        if subtitle:
            self._book.add_metadata("DC", "description", subtitle)
        if description:
            self._book.add_metadata("DC", "description", description)
        if genre:
            self._book.add_metadata("DC", "subject", genre)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_dc(
        book: epub.EpubBook, tag: str, default: Optional[str] = None
    ) -> Optional[str]:
        """Safely retrieve a single DC metadata value from the book.

        ``book.get_metadata("DC", tag)`` returns a list of
        ``(value, {attributes})`` tuples.  We return the first value found
        or *default* if empty.
        """
        records = book.get_metadata("DC", tag)
        if records and isinstance(records, list) and len(records) > 0:
            first = records[0]
            if isinstance(first, tuple) and len(first) >= 1:
                return str(first[0])
            return str(first)
        return default


# ---------------------------------------------------------------------------
# Standalone convenience functions
# ---------------------------------------------------------------------------


def analyze_epub(filepath: str) -> EpubAnalysis:
    """Load an EPUB file and return a complete analysis.

    This is a convenience entry point that internally creates an
    ``EpubProcessor``, extracts chapters, and builds the analysis.

    Parameters
    ----------
    filepath : str
        Path to an EPUB file.

    Returns
    -------
    EpubAnalysis
        All available metadata, cover path, and chapter list.
    """
    processor = EpubProcessor(filepath)
    processor.get_chapters()
    return processor.analyse()


def generate_output_filename(
    title: str, language: str, suffix: str = "_translated"
) -> str:
    """Generate a sanitised output EPUB filename from the translated title.

    Special characters are replaced with underscores and the result is
    truncated to a reasonable length to avoid filesystem problems.

    Parameters
    ----------
    title : str
        Book title (translated or original).
    language : str
        Target language code (ISO 639-1), appended after the title.
    suffix : str
        Optional suffix inserted before the extension (default: ``_translated``).

    Returns
    -------
    str
        A filesystem-safe filename (``Title_Translated_de.epub``).
    """
    safe = re.sub(r"[^\w\s-]", "", title).strip()
    safe = re.sub(r"[-\s]+", "_", safe)
    if len(safe) > 80:
        safe = safe[:80]
    return f"{safe}{suffix}_{language}.epub"
