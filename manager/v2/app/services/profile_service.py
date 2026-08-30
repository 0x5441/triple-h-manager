"""Coordinate isolated profile checks without exposing WebDriver to callers."""

from dataclasses import dataclass
import threading
from typing import Any

from app.browser import (
    BrowserFactory,
    HarajPage,
    ManualVerificationTimeoutError,
    ProfileInUseError,
)
from app.models import Account, AccountStatus


@dataclass(frozen=True, slots=True)
class ProfileResult:
    account_id: str
    status: AccountStatus
    success: bool
    message: str
    test_mode: bool = True


class ProfileService:
    """Open one account profile, validate login, and always close Chrome."""

    def __init__(
        self,
        browser_factory: BrowserFactory,
        *,
        page_factory: Any = HarajPage,
    ) -> None:
        self._browser_factory = browser_factory
        self._page_factory = page_factory
        self._open_drivers: dict[str, Any] = {}
        self._open_lock = threading.RLock()

    def ensure_session(
        self,
        account: Account,
        *,
        headless: bool = False,
        manual_verification_timeout: float = 300,
        test_mode: bool = True,
    ) -> ProfileResult:
        """Validate or refresh login only; no publish/update action exists here."""
        driver = None
        try:
            driver = self._browser_factory.create(account.id, headless=headless)
            page = self._page_factory(driver, headless=headless)
            status = page.ensure_logged_in(
                account,
                manual_verification_timeout=manual_verification_timeout,
            )
            message = (
                "Saved session is valid"
                if status is AccountStatus.SESSION_VALID
                else "Session was refreshed successfully"
            )
            return ProfileResult(account.id, status, True, message, test_mode)
        except ProfileInUseError:
            return ProfileResult(
                account.id,
                AccountStatus.PROFILE_BUSY,
                False,
                "Profile is already open in another Chrome process",
                test_mode,
            )
        except ManualVerificationTimeoutError as exc:
            return ProfileResult(
                account.id,
                AccountStatus.MANUAL_VERIFICATION_REQUIRED,
                False,
                str(exc),
                test_mode,
            )
        except Exception as exc:
            return ProfileResult(
                account.id,
                AccountStatus.FAILED,
                False,
                str(exc) or "Profile session check failed",
                test_mode,
            )
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def test_profile(
        self,
        account: Account,
        *,
        headless: bool = False,
        manual_verification_timeout: float = 300,
    ) -> ProfileResult:
        """Explicit safe mode that performs authentication checks only."""
        return self.ensure_session(
            account,
            headless=headless,
            manual_verification_timeout=manual_verification_timeout,
            test_mode=True,
        )

    def check_session(self, account: Account, *, headless: bool = False) -> ProfileResult:
        """Check a saved session without attempting automatic login."""
        driver = None
        try:
            driver = self._browser_factory.create(account.id, headless=headless)
            page = self._page_factory(driver, headless=headless)
            page.open_home()
            valid = page.is_logged_in(timeout=8)
            status = AccountStatus.SESSION_VALID if valid else AccountStatus.SESSION_EXPIRED
            message = "Saved session is valid" if valid else "Saved session is expired"
            return ProfileResult(account.id, status, valid, message, True)
        except ProfileInUseError:
            return ProfileResult(
                account.id,
                AccountStatus.PROFILE_BUSY,
                False,
                "Profile is already open in another Chrome process",
                True,
            )
        except Exception as exc:
            return ProfileResult(account.id, AccountStatus.FAILED, False, str(exc), True)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def refresh_session(
        self,
        account: Account,
        *,
        headless: bool = False,
        manual_verification_timeout: float = 300,
    ) -> ProfileResult:
        """Validate the session or perform normal login when it has expired."""
        return self.ensure_session(
            account,
            headless=headless,
            manual_verification_timeout=manual_verification_timeout,
            test_mode=True,
        )

    def open_profile(self, account: Account) -> ProfileResult:
        """Open a visible profile owned by the service for manual use."""
        with self._open_lock:
            if account.id in self._open_drivers:
                return ProfileResult(
                    account.id,
                    AccountStatus.PROFILE_BUSY,
                    False,
                    "Profile is already open from V2",
                    True,
                )
            driver = None
            try:
                driver = self._browser_factory.create(account.id, headless=False)
                page = self._page_factory(driver, headless=False)
                page.open_home()
                self._open_drivers[account.id] = driver
                return ProfileResult(
                    account.id,
                    AccountStatus.IDLE,
                    True,
                    "Profile opened for manual use",
                    True,
                )
            except ProfileInUseError:
                return ProfileResult(
                    account.id,
                    AccountStatus.PROFILE_BUSY,
                    False,
                    "Profile is already open in another Chrome process",
                    True,
                )
            except Exception as exc:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                return ProfileResult(account.id, AccountStatus.FAILED, False, str(exc), True)

    def close_open_profiles(self) -> None:
        """Close every manually opened profile during application shutdown."""
        with self._open_lock:
            drivers = list(self._open_drivers.values())
            self._open_drivers.clear()
        for driver in drivers:
            try:
                driver.quit()
            except Exception:
                pass
