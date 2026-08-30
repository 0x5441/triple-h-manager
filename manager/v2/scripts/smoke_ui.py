"""Open the composed V2 UI briefly without running browser or network jobs."""

import argparse

from app.config import ensure_runtime_directories
from app.logging_config import configure_logging
from main import build_application


def main() -> int:
    parser = argparse.ArgumentParser(description="V2 Tkinter smoke test")
    parser.add_argument("--auto-close-ms", type=int, default=1500)
    args = parser.parse_args()
    ensure_runtime_directories()
    configure_logging()
    window = build_application()
    window.after(max(100, args.auto_close_ms), window._shutdown_now)
    window.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
