"""Coordinate isolated profile checks without exposing WebDriver to callers."""

from dataclasses import dataclass
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
