"""Central filesystem paths for Triple H Manager V2."""

from pathlib import Path


V2_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = V2_ROOT / "app"
DATA_DIR = V2_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
LOGS_DIR = DATA_DIR / "logs"
ERRORS_DIR = DATA_DIR / "errors"
ACCOUNTS_FILE = DATA_DIR / "accounts.enc"
SECRET_KEY_FILE = DATA_DIR / ".secret.key"
SETTINGS_FILE = DATA_DIR / "settings.json"
PUBLISHED_ROWS_FILE = DATA_DIR / "published_rows.json"
APPLICATION_LOG_FILE = LOGS_DIR / "triple_h_manager.log"

RUNTIME_DIRECTORIES = (
    DATA_DIR,
    PROFILES_DIR,
    LOGS_DIR,
    ERRORS_DIR,
)


def ensure_runtime_directories() -> None:
    """Create V2-owned runtime directories without touching legacy data."""
    for directory in RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)

