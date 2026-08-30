"""Triple H Manager V2 entry point for the current foundation phase."""

from app.config import ensure_runtime_directories
from app.logging_config import configure_logging, get_logger


def main() -> None:
    """Prepare V2 runtime directories and logging."""
    ensure_runtime_directories()
    configure_logging()
    get_logger(__name__).info("Triple H Manager V2 foundation initialized")


if __name__ == "__main__":
    main()

