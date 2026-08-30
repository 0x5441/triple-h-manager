"""Create isolated Chrome drivers through Selenium Manager."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from app.config import PROFILES_DIR


class BrowserLaunchError(RuntimeError):
    """Raised when Chrome cannot be started for an account."""


class ProfileInUseError(BrowserLaunchError):
    """Raised when Chrome reports that an account profile is already open."""


def is_profile_in_use_error(error: BaseException) -> bool:
    message = str(error).casefold()
    indicators = (
        "user data directory is already in use",
        "profile appears to be in use",
        "profile is already in use",
    )
    return any(indicator in message for indicator in indicators)


class BrowserFactory:
    """Build Chrome using only a V2-owned account profile directory."""

    def __init__(
        self,
        profiles_dir: Path | str = PROFILES_DIR,
        driver_builder: Callable[..., Any] = webdriver.Chrome,
    ) -> None:
        self.profiles_dir = Path(profiles_dir)
        self._driver_builder = driver_builder

    def profile_path(self, account_id: str) -> Path:
        normalized_id = str(account_id).strip()
        if not normalized_id or normalized_id in {".", ".."} or Path(normalized_id).name != normalized_id:
            raise ValueError("account_id is not safe for a profile directory")
        return self.profiles_dir / normalized_id

    def create(self, account_id: str, *, headless: bool = False) -> Any:
        profile_path = self.profile_path(account_id)
        profile_path.mkdir(parents=True, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_path.resolve()}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--lang=ar")
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1000")

        try:
            # No Service executable is supplied: Selenium Manager resolves the driver.
            return self._driver_builder(options=options)
        except WebDriverException as exc:
            if is_profile_in_use_error(exc):
                raise ProfileInUseError("The account profile is already open in another Chrome process") from exc
            raise BrowserLaunchError("Chrome could not be started for the account profile") from exc
