from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Language:
    code: str  # ISO 639-1
    name: str  # English name
    native_name: str  # Name in the language itself


SUPPORTED_LANGUAGES: Dict[str, Language] = {
    'en': Language('en', 'English', 'English'),
    'de': Language('de', 'German', 'Deutsch'),
    'fr': Language('fr', 'French', 'Français'),
    'es': Language('es', 'Spanish', 'Español'),
    'it': Language('it', 'Italian', 'Italiano'),
    'pt': Language('pt', 'Portuguese', 'Português'),
    'nl': Language('nl', 'Dutch', 'Nederlands'),
    'pl': Language('pl', 'Polish', 'Polski'),
    'ru': Language('ru', 'Russian', 'Русский'),
    'ja': Language('ja', 'Japanese', '日本語'),
    'zh': Language('zh', 'Chinese', '中文'),
    'ar': Language('ar', 'Arabic', 'العربية'),
    'tr': Language('tr', 'Turkish', 'Türkçe'),
    'sv': Language('sv', 'Swedish', 'Svenska'),
    'da': Language('da', 'Danish', 'Dansk'),
}


def get_language(code: str) -> Language:
    """Return the Language object for the given ISO 639-1 code.

    Args:
        code: ISO 639-1 language code (e.g. 'en', 'de').

    Returns:
        The matching Language dataclass instance.

    Raises:
        KeyError: If the code is not in SUPPORTED_LANGUAGES.
    """
    if code not in SUPPORTED_LANGUAGES:
        raise KeyError(f"Unsupported language code: {code!r}")
    return SUPPORTED_LANGUAGES[code]


def get_supported_languages() -> List[Language]:
    """Return a list of all supported languages."""
    return list(SUPPORTED_LANGUAGES.values())
