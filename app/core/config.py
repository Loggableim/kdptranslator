from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import os
from dotenv import load_dotenv


@dataclass
class TranslationConfig:
    max_agents: int = 4
    translation_mode: str = "parallel_chunks"  # sequential, parallel_chapters, parallel_chunks
    max_retries: int = 3
    timeout_seconds: int = 120


class AppConfig:
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    INPUT_DIR: Path = PROJECT_ROOT / 'input'
    OUTPUT_DIR: Path = PROJECT_ROOT / 'output'
    LOGS_DIR: Path = PROJECT_ROOT / 'logs'

    _instance: Optional['AppConfig'] = None
    _loaded: bool = False

    def __init__(self) -> None:
        self._ollamacloud_api_key: Optional[str] = None
        self._ollamacloud_base_url: str = "http://localhost:11434"
        self._ollamcloud_model: str = "llama3"
        self._log_level: str = "INFO"
        self._log_file: Path = self.LOGS_DIR / "app.log"

    @staticmethod
    def load() -> 'AppConfig':
        """Load configuration from environment variables / .env file.

        Returns a singleton AppConfig instance populated with values from
        the environment or the first .env file found walking up from
        PROJECT_ROOT.
        """
        if AppConfig._loaded and AppConfig._instance is not None:
            return AppConfig._instance

        # Resolve the .env file path — look in PROJECT_ROOT first, then
        # walk up towards the filesystem root.
        env_path = AppConfig._find_dotenv()
        load_dotenv(dotenv_path=env_path, override=True)

        cfg = AppConfig()

        # --- OllamaCloud / LLM provider settings ---
        cfg._ollamacloud_api_key = os.getenv("OLLAMACLOUD_API_KEY") or os.getenv("OPENAI_API_KEY")
        cfg._ollamacloud_base_url = (
            os.getenv("OLLAMACLOUD_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "http://localhost:11434"
        )
        cfg._ollamcloud_model = (
            os.getenv("OLLAMACLOUD_MODEL")
            or os.getenv("LLM_MODEL")
            or "llama3"
        )

        # --- Logging settings ---
        cfg._log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file_env = os.getenv("LOG_FILE")
        if log_file_env:
            cfg._log_file = Path(log_file_env)
        else:
            cfg._log_file = cfg.LOGS_DIR / "app.log"

        AppConfig._instance = cfg
        AppConfig._loaded = True
        return cfg

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def ollamacloud_api_key(self) -> Optional[str]:
        """API key for the OllamaCloud / OpenAI-compatible provider."""
        return self._ollamacloud_api_key

    @property
    def ollamacloud_base_url(self) -> str:
        """Base URL of the OllamaCloud or OpenAI-compatible API."""
        return self._ollamacloud_base_url

    @property
    def ollamcloud_model(self) -> str:
        """Model identifier used for LLM calls (e.g. llama3, gpt-4)."""
        return self._ollamcloud_model

    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        return self._log_level

    @property
    def log_file(self) -> Path:
        """Path to the application log file."""
        return self._log_file

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_dotenv() -> Optional[Path]:
        """Walk up from PROJECT_ROOT looking for a .env file.

        Returns the first .env found, or None if none exists.
        """
        candidate = AppConfig.PROJECT_ROOT / ".env"
        if candidate.is_file():
            return candidate
        # Fall back to walking up the tree (useful when PROJECT_ROOT is
        # nested inside a monorepo).
        for parent in AppConfig.PROJECT_ROOT.parents:
            candidate = parent / ".env"
            if candidate.is_file():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Convenience factory for TranslationConfig
    # ------------------------------------------------------------------

    @staticmethod
    def translation_config() -> TranslationConfig:
        """Build a TranslationConfig from environment variables.

        Respects the same .env / environment variable sources as load().
        """
        load_dotenv(dotenv_path=AppConfig._find_dotenv(), override=True)

        return TranslationConfig(
            max_agents=int(os.getenv("TRANSLATION_MAX_AGENTS", "4")),
            translation_mode=os.getenv("TRANSLATION_MODE", "parallel_chunks"),
            max_retries=int(os.getenv("TRANSLATION_MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "120")),
        )

    # ------------------------------------------------------------------
    # Ensure required directories exist
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_directories() -> None:
        """Create INPUT_DIR, OUTPUT_DIR and LOGS_DIR if they don't exist."""
        for d in (AppConfig.INPUT_DIR, AppConfig.OUTPUT_DIR, AppConfig.LOGS_DIR):
            d.mkdir(parents=True, exist_ok=True)
