"""Haraj navigation and authentication page object."""

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.browser.selectors import HarajSelectors
from app.models import Account, AccountStatus


class HarajPageError(RuntimeError):
    """Base error for Haraj page interactions."""


class LoginFailedError(HarajPageError):
    """Raised when normal login cannot be completed."""


class ManualVerificationTimeoutError(HarajPageError):
    """Raised when the user does not complete additional verification in time."""


class UpdateVerificationError(HarajPageError):
    """Raised when no meaningful change can be observed after an update click."""


class HarajPage:
    BASE_URL = "https://haraj.com.sa/"

    def __init__(
        self,
        driver: Any,
        *,
        headless: bool = False,
        wait_factory: Callable[[Any, float], Any] = WebDriverWait,
        logger: logging.Logger | None = None,
    ) -> None:
        self.driver = driver
        self.headless = headless
        self._wait_factory = wait_factory
        self.log = logger or logging.getLogger(__name__)

    def open_home(self) -> None:
        try:
            self.driver.get(self.BASE_URL)
            self._wait_factory(self.driver, 25).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
        except WebDriverException as exc:
            raise HarajPageError("Haraj home page could not be opened") from exc

    def is_logged_in(self, timeout: float = 5) -> bool:
        try:
            self._wait_factory(self.driver, timeout).until(
                EC.presence_of_element_located(HarajSelectors.USER_MENU)
            )
            return True
        except TimeoutException:
            return False

    def login(self, account: Account, *, manual_verification_timeout: float = 300) -> None:
        try:
            wait = self._wait_factory(self.driver, 25)
            wait.until(EC.element_to_be_clickable(HarajSelectors.LOGIN_LINK)).click()

            username = wait.until(EC.element_to_be_clickable(HarajSelectors.USERNAME_INPUT))
            username.clear()
            username.send_keys(account.username)
            wait.until(EC.element_to_be_clickable(HarajSelectors.USERNAME_CONTINUE)).click()

            password = wait.until(EC.element_to_be_clickable(HarajSelectors.PASSWORD_INPUT))
            password.clear()
            password.send_keys(account.password)
            wait.until(EC.element_to_be_clickable(HarajSelectors.LOGIN_SUBMIT)).click()
        except (TimeoutException, WebDriverException) as exc:
            raise LoginFailedError("Haraj login form could not be completed") from exc

        try:
            self._wait_factory(self.driver, 15).until(
                EC.presence_of_element_located(HarajSelectors.USER_MENU)
            )
            return
        except TimeoutException:
            if self.headless:
                raise ManualVerificationTimeoutError(
                    "Additional verification requires a visible browser"
                )

        self.log.warning(
            "Additional verification detected; waiting up to %s seconds for the user",
            manual_verification_timeout,
        )
        try:
            self._wait_factory(self.driver, manual_verification_timeout).until(
                EC.presence_of_element_located(HarajSelectors.USER_MENU)
            )
        except TimeoutException as exc:
            raise ManualVerificationTimeoutError(
                "Manual verification was not completed before the timeout"
            ) from exc

    def ensure_logged_in(
        self,
        account: Account,
        *,
        manual_verification_timeout: float = 300,
    ) -> AccountStatus:
        self.open_home()
        if self.is_logged_in():
            self.log.info("Saved Haraj session is valid for account %s", account.id)
            return AccountStatus.SESSION_VALID
        self.login(account, manual_verification_timeout=manual_verification_timeout)
        self.log.info("Haraj session was refreshed for account %s", account.id)
        return AccountStatus.SESSION_REFRESHED

    def update_ad(self, url: str, *, dry_run: bool = False) -> bool:
        """Update one existing ad and verify an observable post-click change.

        Returns ``True`` after a verified click, or ``False`` in dry-run mode.
        """
        self._validate_haraj_url(url)
        try:
            self.driver.get(url)
            self._wait_factory(self.driver, 25).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            button = self._wait_factory(self.driver, 25).until(
                EC.element_to_be_clickable(HarajSelectors.UPDATE_BUTTON)
            )
        except (TimeoutException, WebDriverException) as exc:
            raise HarajPageError("The advertisement update button could not be opened") from exc

        if dry_run:
            self.log.info("Dry-run verified the update button for %s", url)
            return False

        initial_url = self.driver.current_url
        initial_signature = self._element_signature(button)
        try:
            button.click()
            self._wait_factory(self.driver, 20).until(
                lambda driver: self._update_state_changed(
                    driver,
                    button,
                    initial_url,
                    initial_signature,
                )
            )
        except TimeoutException as exc:
            raise UpdateVerificationError(
                "The update button was clicked but no observable success change was detected"
            ) from exc
        except WebDriverException as exc:
            raise HarajPageError("The advertisement update action failed") from exc
        return True

    @staticmethod
    def _validate_haraj_url(url: str) -> None:
        parsed = urlparse(str(url).strip())
        hostname = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not (
            hostname == "haraj.com.sa" or hostname.endswith(".haraj.com.sa")
        ):
            raise ValueError("Advertisement URL must be an HTTPS Haraj URL")

    @staticmethod
    def _element_signature(element: Any) -> tuple[str, str | None, str | None, bool, bool]:
        return (
            str(element.text),
            element.get_attribute("class"),
            element.get_attribute("aria-disabled"),
            bool(element.is_enabled()),
            bool(element.is_displayed()),
        )

    def _update_state_changed(
        self,
        driver: Any,
        button: Any,
        initial_url: str,
        initial_signature: tuple[str, str | None, str | None, bool, bool],
    ) -> bool:
        if driver.current_url != initial_url:
            return True
        try:
            current = self._element_signature(button)
            return current != initial_signature or not current[3] or not current[4]
        except StaleElementReferenceException:
            return True
