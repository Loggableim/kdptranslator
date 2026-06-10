"""Validation rules for the title selection workflow.

Provides functions to check whether titles for selected languages have been
confirmed, which languages are still missing, and whether the project is
ready for translation.
"""

from typing import Dict, List, Tuple

from app.services.title_generator import TitleConfirmation


def are_all_titles_confirmed(
    confirmations: Dict[str, TitleConfirmation],
    selected_languages: List[str],
) -> bool:
    """Return True only if every selected language has a confirmed title.

    A language is considered confirmed when it exists in *confirmations* and
    its :attr:`TitleConfirmation.confirmed` flag is ``True``.

    Args:
        confirmations: Mapping of language code → TitleConfirmation.
        selected_languages: Language codes the user has selected for
            translation.

    Returns:
        ``True`` when every language in *selected_languages* has a confirmed
        title; ``False`` otherwise.
    """
    return all(
        lang in confirmations and confirmations[lang].confirmed
        for lang in selected_languages
    )


def get_missing_languages(
    confirmations: Dict[str, TitleConfirmation],
    selected_languages: List[str],
) -> List[str]:
    """Return languages in *selected_languages* that still need confirmation.

    A language is considered missing if it is either absent from
    *confirmations* or its :attr:`TitleConfirmation.confirmed` flag is
    ``False``.

    Args:
        confirmations: Mapping of language code → TitleConfirmation.
        selected_languages: Language codes the user has selected for
            translation.

    Returns:
        A list of language codes (preserving the order they appear in
        *selected_languages*) that are not yet confirmed.
    """
    return [
        lang
        for lang in selected_languages
        if lang not in confirmations or not confirmations[lang].confirmed
    ]


def is_translation_ready(
    confirmations: Dict[str, TitleConfirmation],
    selected_languages: List[str],
    epub_loaded: bool,
) -> Tuple[bool, str]:
    """Return whether the project is ready for translation, plus a message.

    Readiness requires **all** of the following:

    1. An EPUB file has been loaded (``epub_loaded is True``).
    2. At least one language has been selected.
    3. Every selected language has a confirmed title.

    Args:
        confirmations: Mapping of language code → TitleConfirmation.
        selected_languages: Language codes the user has selected for
            translation.
        epub_loaded: Whether an EPUB file has been loaded into the project.

    Returns:
        A tuple ``(ready, message)`` where:

        - ``ready`` is ``True`` when translation can proceed.
        - ``message`` is a human-readable string explaining the current
          state (empty when ``ready`` is ``True``).
    """
    if not epub_loaded:
        return False, "No EPUB file loaded. Please load an EPUB file first."

    if not selected_languages:
        return False, "No languages selected. Please select at least one target language."

    missing = get_missing_languages(confirmations, selected_languages)
    if missing:
        lang_list = ", ".join(missing)
        return (
            False,
            f"Titles not yet confirmed for: {lang_list}. "
            f"Please confirm titles for all selected languages.",
        )

    return True, ""
