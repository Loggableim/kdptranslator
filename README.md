# KDP Translator

**A local desktop application for KDP publishers that translates complete EPUB books into multiple languages using AI language models.**

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Status](https://img.shields.io/badge/status-alpha-orange)

---

## One-Line Install

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/Loggableim/kdptranslator/master/install.ps1 | iex"
```

---

## Overview

KDP Translator is a desktop GUI tool built with [Flet](https://flet.dev/) that helps Kindle Direct Publishing authors and publishers localize their eBooks. Load an EPUB, pick one or more target languages, let AI generate localized title suggestions, and translate the full book content — all from a local Windows application.

The application supports multiple translation modes, concurrent agent-based translation for speed, and preserves EPUB structure including covers, CSS, fonts, and navigation.

---

## Features

- **EPUB Import & Analysis** — Load any EPUB file; extract chapters, metadata, cover image, and text nodes with full structure preservation.
- **Multi-Language Translation** — Translate into 15+ languages including German, French, Spanish, Italian, Portuguese, Dutch, Polish, Russian, Japanese, Chinese, Arabic, Turkish, Swedish, and Danish.
- **AI Title Localization** — For each target language, the AI generates three title variants:
  - **Literal** — Direct translation of the original title.
  - **Market** — Culturally adapted for the target audience.
  - **SEO** — Optimised for search discoverability.
  - Each variant includes an AI-generated reasoning explanation.
- **Multi-Agent Translation** — Concurrent translation via a thread-safe agent pool. Configurable number of parallel agents, retry logic, and timeout settings.
- **Translation Modes** — Choose from sequential, parallel chapters, or parallel chunks processing strategies.
- **Mock Provider** — Built-in mock provider lets you test the UI workflow without any API key.
- **OllamaCloud / OpenAI Compatible** — Plug in any OpenAI-compatible API (OllamaCloud, OpenAI, local LLMs via Ollama, etc.).
- **Structure Preservation** — Cover images, CSS stylesheets, embedded fonts, media files, and TOC/NCX navigation are all preserved in the output EPUB.
- **Local Desktop Application** — Runs entirely on your Windows machine. No cloud dependency beyond the optional LLM API.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **GUI Framework** | [Flet](https://flet.dev/) (Python → Flutter) |
| **EPUB Handling** | [ebooklib](https://github.com/aerkalov/ebooklib) |
| **HTML Parsing** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [lxml](https://lxml.de/) |
| **LLM Provider** | OpenAI-compatible API (OllamaCloud, OpenAI, Ollama, etc.) via [httpx](https://www.python-httpx.org/) |
| **Configuration** | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Testing** | [pytest](https://docs.pytest.org/) |
| **Packaging** | Python 3.12+, `venv` |

---

## Screenshots

![KDP Translator Screenshot](https://via.placeholder.com/800x500?text=KDP+Translator+Screenshot)

*Screenshot placeholder — replace with an actual image of the application in action.*

---

## Installation

### Prerequisites

- **Windows 11** (or Windows 10)
- **Python 3.12+** installed and available on `PATH`

### Quick Install (PowerShell)

```powershell
# Clone the repository
git clone https://github.com/yourusername/kdptranslator.git
cd kdptranslator

# Run the installer
.\install.ps1
```

The installer will:
1. Verify Python 3.12+ is installed.
2. Create a virtual environment (`.venv`).
3. Install all dependencies from `requirements.txt`.
4. Copy `.env.example` to `.env` if it doesn't already exist.
5. Create `run.bat` for easy launching.

### Manual Install

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/Scripts/activate   # Git Bash
# or
.venv\Scripts\activate          # PowerShell / cmd

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env          # cmd
# or
cp .env.example .env            # PowerShell / bash
```

---

## Configuration

Edit the `.env` file in the project root to configure your LLM provider:

```ini
# Required: Your API key for OllamaCloud or any OpenAI-compatible provider
OLLAMACLOUD_API_KEY=sk-...

# Optional: Override the API base URL (default: https://api.ollama.cloud)
OLLAMACLOUD_BASE_URL=https://api.ollama.cloud

# Optional: Model to use (default: llama3.1:70b)
OLLAMACLOUD_MODEL=llama3.1:70b

# Translation settings
DEFAULT_MAX_AGENTS=4
DEFAULT_TRANSLATION_MODE=parallel_chunks
DEFAULT_MAX_RETRIES=3
DEFAULT_TIMEOUT_SECONDS=120

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/translate.log
```

> **Tip:** Leave `OLLAMACLOUD_API_KEY` empty and the app will use the built-in `MockTranslationProvider` for testing the UI without any API key.

---

## Usage

### Starting the Application

```bash
# Option A — Using the batch file (after install)
run.bat

# Option B — Direct Flet launch (with venv activated)
flet run app/main.py

# Option C — Python module (with venv activated)
python -m app.main
```

### Workflow

1. **Launch** the application — the KDP Translator window opens.
2. **Load an EPUB** — Click "Open EPUB" and select your `.epub` file.
3. **Select Target Languages** — Choose one or more languages from the list.
4. **Generate Title Suggestions** — For each target language, review the AI-generated title variants (Literal, Market, SEO) and confirm your choice.
5. **Configure Translation** — Adjust agent count, translation mode, and provider settings if needed.
6. **Start Translation** — Click "Translate" — watch progress in real-time via the agent status panel and log view.
7. **Save Translated EPUB** — Each translated language is saved as a separate EPUB file (e.g., `mybook.de.epub`, `mybook.fr.epub`).

---

## Project Structure

```
C:\projekte\kdptranslator\
├── app/
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # App & translation configuration (.env loader)
│   │   ├── chunker.py           # Text chunking strategies
│   │   ├── epub_processor.py    # EPUB read/analyse/write
│   │   ├── html_translator.py   # HTML-aware translation helpers
│   │   ├── language.py          # Supported languages definitions
│   │   ├── logger.py            # Logging setup
│   │   ├── metadata.py          # EPUB metadata utilities
│   │   └── validation.py        # Input validation helpers
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract TranslationProvider interface
│   │   ├── mock.py              # Mock provider for testing
│   │   └── ollamacloud.py       # OllamaCloud / OpenAI-compatible provider
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent_pool.py        # Thread-safe concurrent agent pool
│   │   ├── title_generator.py   # AI title suggestion generation
│   │   ├── translation_scheduler.py  # Translation job scheduling
│   │   └── translation_service.py    # High-level orchestration
│   └── ui/
│       ├── __init__.py
│       ├── agent_settings.py    # Agent configuration panel
│       ├── app_view.py          # Main application window
│       ├── language_selector.py # Language selection UI
│       ├── log_view.py          # Live log display
│       ├── progress_view.py     # Translation progress panel
│       └── title_selector.py    # Title suggestion & confirmation UI
├── tests/
│   └── __init__.py
├── input/                       # Drop EPUB files here (auto-created)
├── output/                      # Translated EPUBs appear here (auto-created)
├── logs/                        # Application logs (auto-created)
├── .env.example                 # Environment variable template
├── .env                         # Your local configuration (not tracked)
├── requirements.txt             # Python dependencies
├── install.ps1                  # Windows PowerShell installer
├── run.bat                      # Quick-launch batch file
├── README.md                    # This file
└── DIGITAL_BOOK_BLOCK.epub      # Sample EPUB for testing
```

---

## Testing

```bash
# Activate virtual environment first, then:
pytest
```

Tests are located in the `tests/` directory. The project uses `pytest` as its test framework.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to open a pull request or an issue on GitHub.

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## Acknowledgements

- Built with [Flet](https://flet.dev/) — Python UI framework powered by Flutter.
- EPUB handling via [ebooklib](https://github.com/aerkalov/ebooklib).
- Powered by OpenAI-compatible LLM APIs.
