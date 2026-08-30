"""Triple H Manager V2 dependency composition and Tkinter entry point."""

from app.browser import BrowserFactory
from app.config import ensure_runtime_directories
from app.logging_config import configure_logging
from app.services import (
    AccountService,
    GoogleSheetService,
    JobRunner,
    ProfileService,
    PublishService,
    SettingsService,
    UpdateService,
)
from app.storage import AccountStore, ProcessedRowStore, SettingsStore
from app.ui import MainWindow, UiServices


def build_application() -> MainWindow:
    """Compose services once and inject them into the UI."""
    account_service = AccountService(AccountStore())
    browser_factory = BrowserFactory()
    processed_store = ProcessedRowStore()
    services = UiServices(
        accounts=account_service,
        profiles=ProfileService(browser_factory),
        updates=UpdateService(account_service, browser_factory),
        sheets=GoogleSheetService(processed_store),
        publishing=PublishService(
            account_service,
            browser_factory,
            processed_store,
        ),
        settings=SettingsService(SettingsStore()),
        jobs=JobRunner(),
    )
    return MainWindow(services)


def main() -> None:
    """Prepare V2 runtime services and start Tkinter."""
    ensure_runtime_directories()
    configure_logging()
    build_application().mainloop()


if __name__ == "__main__":
    main()
