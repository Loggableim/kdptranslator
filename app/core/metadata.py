"""Metadata utilities for EPUB books."""

import re
import unicodedata
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Genre detection map  –  simple keyword-based heuristic
# ---------------------------------------------------------------------------
_GENRE_KEYWORDS: Dict[str, list[str]] = {
    "fiction": [
        "novel", "fiction", "story", "tale", "narrative", "saga",
        "chronicle", "fable",
    ],
    "non-fiction": [
        "biography", "autobiography", "memoir", "history", "historical",
        "essay", "journalism", "report", "documentary", "reference",
        "textbook", "guide", "manual", "handbook", "cookbook",
        "self-help", "self help", "how-to", "how to",
    ],
    "fantasy": [
        "fantasy", "magic", "dragon", "sword", "sorcery", "wizard",
        "mage", "mythical", "legend", "enchanted", "otherworld",
        "fae", "faerie", "dungeon", "goblin", "elf", "dwarf",
        "epic fantasy", "high fantasy", "dark fantasy",
    ],
    "science fiction": [
        "science fiction", "sci-fi", "scifi", "space", "alien",
        "robot", "cyborg", "dystopia", "utopia", "cyberpunk",
        "steampunk", "time travel", "parallel universe",
        "extraterrestrial", "interstellar", "galaxy", "starship",
        "future", "post-apocalyptic", "post apocalyptic",
    ],
    "romance": [
        "romance", "love", "passion", "romantic", "relationship",
        "heartfelt", "steamy", "cinderella", "happily ever after",
        "enemies to lovers", "friends to lovers",
    ],
    "thriller": [
        "thriller", "suspense", "mystery", "detective", "crime",
        "noir", "whodunit", "investigation", "conspiracy",
        "psychological thriller", "action thriller",
    ],
    "horror": [
        "horror", "ghost", "haunted", "supernatural", "terror",
        "nightmare", "darkness", "occult", "demonic", "possession",
        "slasher", "zombie", "vampire", "werewolf", "monster",
        "gothic", "creepy", "chilling",
    ],
    "young adult": [
        "young adult", "ya ", "teen", "coming-of-age",
        "coming of age", "adolescent", "high school",
    ],
    "children": [
        "children", "kids", "picture book", "middle grade",
        "juvenile", "young reader",
    ],
    "literary": [
        "literary", "classic", "contemporary", "award-winning",
        "pulitzer", "booker", "nobel",
    ],
}

# Characters that are invalid in Windows filenames.
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
# Additional control characters and other unicode nuisances.
_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')


def sanitize_filename(title: str) -> str:
    """Remove or replace characters that are invalid in filenames.

    * Replaces ``<>:"/\\|?*`` with an underscore.
    * Strips control characters (``\\x00-\\x1f``, ``\\x7f``).
    * Collapses runs of whitespace and leading/trailing dots/spaces.
    * Normalises unicode to NFKC (compatibility composed form).
    * Truncates to 200 characters to avoid ``ENAMETOOLONG`` on most filesystems.
    """
    if not title:
        return "untitled"

    # Normalise unicode
    name = unicodedata.normalize("NFKC", title)

    # Replace path-invalid characters with underscore
    name = _INVALID_FILENAME_CHARS.sub("_", name)

    # Strip control characters
    name = _CONTROL_CHARS.sub("", name)

    # Collapse whitespace (including non-breaking spaces etc.)
    name = re.sub(r"\s+", " ", name).strip()

    # Remove leading/trailing dots and spaces (Windows annoyance)
    name = name.strip(". ")

    # Truncate
    name = name[:200].rstrip(". ")

    return name if name else "untitled"


def generate_output_filename(
    original_title: str,
    language_code: str,
    use_title: bool = False,
) -> str:
    """Generate a safe output filename for a translated EPUB.

    Parameters
    ----------
    original_title : str
        The book title (may contain unsafe characters).
    language_code : str
        ISO 639-1 two-letter language code (e.g. ``"en"``, ``"de"``).
    use_title : bool
        If True, embed the sanitised title in the filename.
        Otherwise only the language code suffix is used (default).

    Returns
    -------
    str
        E.g. ``"book_en.epub"`` or ``"the-hobbit_en.epub"``.

    Notes
    -----
    The extension is hardcoded to ``.epub`` because this module is part of
    an EPUB translator.
    """
    safe = sanitize_filename(original_title)
    slug = safe.lower().replace(" ", "-")

    if use_title and slug:
        stem = slug
    else:
        stem = "book"

    return f"{stem}_{language_code}.epub"


def extract_metadata(epub_book) -> dict:
    """Extract all metadata from an ``ebooklib.epub.EpubBook`` instance.

    Returns a dictionary with the following keys (always present, possibly
    empty strings or empty lists):

    * ``title``
    * ``creator``  (comma-separated if multiple)
    * ``contributors`` (list)
    * ``publisher``
    * ``description``
    * ``identifier``  (the first DC identifier found)
    * ``source``
    * ``rights``
    * ``date``
    * ``language``
    * ``subject``  (first subject, if any)
    * ``subjects`` (list of all subjects)
    * ``format``
    * ``type``
    * ``coverage``
    * ``relation``
    * ``all_metadata``  (raw dict keyed by ``(namespace, element)`` tuples)
    """
    result: dict = {
        "title": "",
        "creator": "",
        "contributors": [],
        "publisher": "",
        "description": "",
        "identifier": "",
        "source": "",
        "rights": "",
        "date": "",
        "language": "",
        "subject": "",
        "subjects": [],
        "format": "",
        "type": "",
        "coverage": "",
        "relation": "",
        "all_metadata": {},
    }

    # ------------------------------------------------------------------
    # Helper to get the text of the first DC element matching a given
    # property name (e.g. "title", "creator").
    # ------------------------------------------------------------------
    def _first(book, dc_name: str) -> str:
        val = book.get_metadata("DC", dc_name)
        if val:
            return val[0][0] if isinstance(val[0], (list, tuple)) else str(val[0])
        return ""

    # ------------------------------------------------------------------
    # Helper to get *all* values for a DC element.
    # ------------------------------------------------------------------
    def _all(book, dc_name: str) -> list[str]:
        values = book.get_metadata("DC", dc_name)
        if not values:
            return []
        out = []
        for v in values:
            if isinstance(v, (list, tuple)):
                out.append(str(v[0]))
            else:
                out.append(str(v))
        return out

    # Standard Dublin Core fields
    result["title"] = _first(epub_book, "title")
    result["creator"] = _first(epub_book, "creator")
    result["contributors"] = _all(epub_book, "contributor")
    result["publisher"] = _first(epub_book, "publisher")
    result["description"] = _first(epub_book, "description")
    result["identifier"] = _first(epub_book, "identifier")
    result["source"] = _first(epub_book, "source")
    result["rights"] = _first(epub_book, "rights")
    result["date"] = _first(epub_book, "date")
    result["language"] = _first(epub_book, "language")
    result["subject"] = _first(epub_book, "subject")
    result["subjects"] = _all(epub_book, "subject")
    result["format"] = _first(epub_book, "format")
    result["type"] = _first(epub_book, "type")
    result["coverage"] = _first(epub_book, "coverage")
    result["relation"] = _first(epub_book, "relation")

    # Provide raw access to all metadata tuples for advanced callers.
    all_md: dict = {}
    for ns in epub_book.metadata:
        for elem, values in epub_book.metadata[ns].items():
            key = (ns, elem)
            all_md[key] = values
    result["all_metadata"] = all_md

    return result


def update_metadata(epub_book, title: str, language: str) -> None:
    """Update *title* and *language* Dublin Core metadata in-place.

    Parameters
    ----------
    epub_book : ebooklib.epub.EpubBook
        The EPUB book object to modify.
    title : str
        New title.
    language : str
        New language code (ISO 639-1, e.g. ``"en"``, ``"de"``, ``"fr"``).

    Notes
    -----
    This method **replaces** existing DC title/language entries rather than
    appending duplicates.  If there are multiple titles or languages only the
    first occurrence is updated and the extras are removed.  The operation is
    performed via ``set_metadata`` from ``ebooklib`` internals when possible;
    otherwise it falls back to manipulating the internal metadata dictionary.
    """
    # --- Title ---------------------------------------------------------
    _set_or_replace_dc(epub_book, "title", title)
    # --- Language ------------------------------------------------------
    _set_or_replace_dc(epub_book, "language", language)


def _set_or_replace_dc(book, element: str, value: str) -> None:
    """Replace all DC *element* entries with a single *value*.

    Uses ``epub.write_metadata`` if available (ebooklib >= 0.18),
    otherwise manipulates the internal dictionary directly.
    """
    # Clear existing entries for this element.
    dc_ns = book.metadata.get("DC", {})
    if element in dc_ns:
        del dc_ns[element]

    # ebooklib internal: book.metadata is a dict of dicts:
    #   {ns: {elem: [(value, attrs_dict), ...]}}
    #
    # We add a single entry with no extra attributes.
    metadata_dict = book.metadata
    if "DC" not in metadata_dict:
        metadata_dict["DC"] = {}
    if element not in metadata_dict["DC"]:
        metadata_dict["DC"][element] = []

    metadata_dict["DC"][element].append((value, {}))

    # Also try to use ebooklib's write_metadata if available.
    try:
        from ebooklib import epub

        epub.write_metadata(book, "DC", element, value)
    except (ImportError, AttributeError):
        pass  # write_metadata not available in older versions – already done above.
    except Exception:
        pass  # Best-effort update; the dict-level change above is sufficient.


def detect_genre(metadata: dict, description: str) -> str:
    """Simple keyword-based genre detection.

    Parameters
    ----------
    metadata : dict
        The dictionary returned by :func:`extract_metadata`.  The keys
        ``subject``, ``subjects`` and ``title`` are consulted.
    description : str
        Book description / blurb text (may be the same as
        ``metadata["description"]``).

    Returns
    -------
    str
        One of the genre keys defined in ``_GENRE_KEYWORDS`` (e.g.
        ``"fiction"``, ``"fantasy"``, ``"science fiction"``) or ``"unknown"``
        if nothing matches.

    Notes
    -----
    Scoring is simple case-insensitive substring matching.  The genre with
    the most keyword hits wins.  A tie is broken by order of definition in
    ``_GENRE_KEYWORDS`` (first wins).
    """
    # Collect all text we can score against.
    texts: list[str] = []

    # Subjects (often contain genre hints)
    subjects = metadata.get("subjects", []) or []
    texts.extend(subjects)
    subj = metadata.get("subject", "")
    if subj:
        texts.append(subj)

    # Title
    title = metadata.get("title", "")
    if title:
        texts.append(title)

    # Description
    if description:
        texts.append(description)

    # Aggregate into a single lowercased corpus.
    corpus = " ".join(texts).lower()

    # Score each genre.
    scores: dict[str, int] = {}
    for genre, keywords in _GENRE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            # Keyword can be a multi-word phrase – check as substring.
            if kw.lower() in corpus:
                score += 1
        if score > 0:
            scores[genre] = score

    if not scores:
        return "unknown"

    # Return the genre with the highest score.  Stable sort respects
    # definition order on ties.
    best = max(scores, key=lambda g: scores[g])
    return best
