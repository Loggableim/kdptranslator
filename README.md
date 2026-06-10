# KDP Translator

**A local desktop application for KDP publishers that translates complete EPUB books into multiple languages using AI language models.**

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Status](https://img.shields.io/badge/status-pre--release-orange)

---

## One-Line Install

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/Loggableim/kdptranslator/master/install.ps1 | iex"
```

---

## Overview

KDP Translator is a desktop GUI application built with [Flet](https://flet.dev/) that helps Kindle Direct Publishing authors and publishers localize their eBooks. Load an EPUB, pick one or more target languages, let AI generate localized title suggestions, and translate the full book content — all from a local Windows application.

It runs as a **local GUI application** (not a CLI tool) — all interaction happens through a visual Flet interface. No command-line proficiency required beyond the initial setup.

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
- **OllamaCloud / OpenAI Compatible** — Plug in any OpenAI-compatible API (OllamaCloud, OpenRouter, OpenAI, local LLMs via Ollama, etc.).
- **Structure Preservation** — Cover images, CSS stylesheets, embedded fonts, media files, and TOC/NCX navigation are all preserved in the output EPUB.
- **Local Desktop Application** — Runs entirely on your Windows machine. No cloud dependency beyond the optional LLM API.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **GUI Framework** | [Flet](https://flet.dev/) (Python → Flutter) |
| **EPUB Handling** | [ebooklib](https://github.com/aerkalov/ebooklib) |
| **HTML Parsing** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [lxml](https://lxml.de/) |
| **LLM Provider** | OpenAI-compatible API (OllamaCloud, OpenRouter, OpenAI, Ollama, etc.) via [httpx](https://www.python-httpx.org/) |
| **Configuration** | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Testing** | [pytest](https://docs.pytest.org/) |
| **Packaging** | Python 3.12+, `venv` |

---

## Installation

### Prerequisites

- **Windows 11** (or Windows 10)
- **Python 3.12+** installed and available on `PATH`

### Quick Install (PowerShell)

```powershell
# Clone the repository
git clone https://github.com/Loggableim/kdptranslator.git
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

Edit the `.env` file in the project root to configure your LLM provider. The application supports multiple providers:

### OllamaCloud

```ini
OLLAMACLOUD_API_KEY=sk-your-key-here
OLLAMACLOUD_BASE_URL=https://api.ollama.cloud
OLLAMACLOUD_MODEL=llama3.1:70b
```

### OpenRouter

```ini
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
```

### OpenAI / Any OpenAI-Compatible API

You can use any provider that offers an OpenAI-compatible endpoint by setting the appropriate `*_API_KEY`, `*_BASE_URL`, and `*_MODEL` environment variables. The provider system is designed to work with any OpenAI-compatible API.

### Mock Provider (No API Key Required)

**Leave `OLLAMACLOUD_API_KEY` and `OPENROUTER_API_KEY` empty**, and the application will automatically fall back to the built-in `MockTranslationProvider`. This lets you explore the full UI, load EPUBs, select languages, and walk through the translation workflow — all without any API key or internet connection. Mock translations return placeholder text so you can verify the pipeline end-to-end.

### Translation Settings (Optional)

```ini
DEFAULT_MAX_AGENTS=4
DEFAULT_TRANSLATION_MODE=parallel_chunks
DEFAULT_MAX_RETRIES=3
DEFAULT_TIMEOUT_SECONDS=120

LOG_LEVEL=INFO
LOG_FILE=logs/translate.log
```

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

## Troubleshooting

### "Python is not installed or not found on PATH"

Download Python 3.12+ from [python.org](https://www.python.org/downloads/) and ensure you check **"Add Python to PATH"** during installation. After installing, restart your terminal and try again.

### Virtual environment creation fails

- Ensure Python 3.12+ is fully installed (try `python --version`).
- If you have multiple Python versions, the installer tries `python` first, then `python3`.
- Run `python -m venv .venv` manually to see the exact error.

### pip install fails

- Try upgrading pip first: `python -m pip install --upgrade pip`
- If a specific package fails to build, ensure you have the [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) installed.
- Check your internet connection and firewall settings.

### "Flet not found" or "No module named app"

- Ensure the virtual environment is activated: `.venv\Scripts\activate`
- Re-run `pip install -r requirements.txt` inside the activated venv.
- Make sure you are in the project root directory (`C:\projekte\kdptranslator\`).

### The app starts but shows errors about API keys

- Leave API keys empty to use the **MockProvider** (placeholder translations, no API needed).
- For real translations, set `OLLAMACLOUD_API_KEY` or `OPENROUTER_API_KEY` in `.env`.
- Check that the provider base URL is correct (see Configuration section above).

### How do I reset or reinstall?

Delete the `.venv` folder and re-run `install.ps1`. Your `.env` settings will be preserved.

---

## Known Limitations

- **Windows Only** — Currently tested only on Windows 10/11. Linux and macOS are not yet supported.
- **Flet-Based GUI** — The UI is rendered via Flet/Flutter, which means the window appearance may differ slightly from native Windows applications.
- **Large EPUB Files** — Very large EPUBs (10,000+ pages) may take significant time and memory during processing. The chunk-based translation mode helps mitigate this.
- **API Dependency** — Real translations require an active API key and internet connection to an LLM provider. Translations are only as good as the underlying model.
- **Mock Provider Limitations** — The mock provider returns placeholder text, not real translations. It is intended for UI testing and workflow validation only.
- **No Incremental Translation** — If a translation is interrupted, it must be restarted from the beginning. There is no checkpoint/resume feature yet.
- **Single Format Output** — Only EPUB output is supported. PDF, DOCX, or MOBI export are not available.
- **Pre-Release Software** — This project is in **pre-release** stage. APIs, features, and configuration may change without notice. Not yet recommended for production use without testing.

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
