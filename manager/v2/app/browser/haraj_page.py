"""Haraj navigation and authentication page object."""

import logging
import platform
import random
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.browser.selectors import HarajSelectors
from app.models import Account, AccountStatus, Advertisement


class HarajPageError(RuntimeError):
    """Base error for Haraj page interactions."""


class LoginFailedError(HarajPageError):
    """Raised when normal login cannot be completed."""


class ManualVerificationTimeoutError(HarajPageError):
    """Raised when the user does not complete additional verification in time."""


class UpdateVerificationError(HarajPageError):
    """Raised when no meaningful change can be observed after an update click."""


class PhoneVerificationError(HarajPageError):
    """Raised when the mobile input does not retain the requested value."""


class ImageUploadNotSupportedError(HarajPageError):
    """Raised before publishing when an image is requested."""


class PublishVerificationError(HarajPageError):
    """Raised when a submit click has no observable success evidence."""


class HarajPage:
    BASE_URL = "https://haraj.com.sa/"

    def __init__(
        self,
        driver: Any,
        *,
        headless: bool = False,
        wait_factory: Callable[[Any, float], Any] = WebDriverWait,
        logger: logging.Logger | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.driver = driver
        self.headless = headless
        self._wait_factory = wait_factory
        self.log = logger or logging.getLogger(__name__)
        self._sleep = sleep_func
        self._random_uniform = random_uniform

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
            state = self._wait_factory(self.driver, timeout).until(self._session_state)
            return state == "logged_in"
        except TimeoutException:
            return False

    def _session_state(self, driver: Any) -> str | bool:
        """Resolve the hydrated header without relying on one account-menu selector."""
        if self._has_visible_element(driver, HarajSelectors.USER_MENU):
            return "logged_in"
        if self._has_visible_element(driver, HarajSelectors.LOGIN_LINK):
            return "logged_out"
        if self._has_visible_element(driver, HarajSelectors.ADD_POST_BUTTON):
            return "logged_in"
        return False

    @staticmethod
    def _has_visible_element(driver: Any, locator: tuple[str, str]) -> bool:
        try:
            return any(element.is_displayed() for element in driver.find_elements(*locator))
        except (StaleElementReferenceException, WebDriverException):
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
                lambda driver: self._session_state(driver) == "logged_in"
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
                lambda driver: self._session_state(driver) == "logged_in"
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

    def publish_ad(self, advertisement: Advertisement, *, dry_run: bool = True) -> bool:
        """Fill a service-ad form and submit only when explicitly requested.

        Returns ``False`` after a completed dry-run and ``True`` only after a
        submit action produces observable success evidence.
        """
        if advertisement.image:
            raise ImageUploadNotSupportedError(
                "Image upload is not implemented; clear the image field before publishing"
            )
        if not advertisement.title or not advertisement.body:
            raise ValueError("Advertisement title and body are required")
        if not advertisement.phone:
            raise ValueError("Advertisement phone is required")

        self.open_home()
        self._click_locator(HarajSelectors.ADD_POST_BUTTON)
        self._dismiss_incomplete_post_prompt()
        self._click_locator(HarajSelectors.SERVICE_POST_TYPE)

        agreement = self._wait_factory(self.driver, 25).until(
            EC.presence_of_element_located(HarajSelectors.AGREEMENT_CHECKBOX)
        )
        if not agreement.is_selected():
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                agreement,
            )
            agreement.click()
            self._stability_pause()

        self._click_locator(HarajSelectors.STEP_TWO_CONTINUE)
        self._click_locator(HarajSelectors.STEP_FOUR_CONTINUE)
        self._fill_text(HarajSelectors.POST_TITLE_INPUT, advertisement.title)
        self._fill_phone_field(advertisement.phone)
        self._fill_text(HarajSelectors.POST_BODY_INPUT, advertisement.body)

        if dry_run:
            self.log.info("Dry-run filled publish form for advertisement %s", advertisement.id)
            return False

        submit = self._wait_factory(self.driver, 25).until(
            EC.element_to_be_clickable(HarajSelectors.POST_SUBMIT)
        )
        initial_url = self.driver.current_url
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            submit,
        )
        self._stability_pause(0.2, 0.6)
        try:
            submit.click()
            self._wait_factory(self.driver, 20).until(
                lambda driver: self._publish_state_changed(
                    driver,
                    submit,
                    initial_url,
                )
            )
        except TimeoutException as exc:
            raise PublishVerificationError(
                "Publish was clicked but no page transition or success evidence was detected"
            ) from exc
        except WebDriverException as exc:
            raise HarajPageError("Advertisement submit action failed") from exc
        return True

    def _dismiss_incomplete_post_prompt(self) -> bool:
        """Discard an unfinished Haraj draft when its optional prompt appears."""
        try:
            button = self._wait_factory(self.driver, 5).until(
                EC.element_to_be_clickable(HarajSelectors.INCOMPLETE_POST_DISCARD)
            )
        except TimeoutException:
            return False
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            button,
        )
        button.click()
        self._stability_pause()
        return True

    def _click_locator(self, locator: tuple[str, str]) -> Any:
        element = self._wait_factory(self.driver, 25).until(
            EC.element_to_be_clickable(locator)
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element,
        )
        self._stability_pause(0.2, 0.6)
        element.click()
        self._stability_pause()
        return element

    def _fill_text(self, locator: tuple[str, str], value: str) -> None:
        field = self._wait_factory(self.driver, 25).until(
            EC.element_to_be_clickable(locator)
        )
        field.click()
        field.clear()
        field.send_keys(value)
        self._stability_pause(0.2, 0.7)

    def _fill_phone_field(self, phone: str) -> None:
        field = self._wait_factory(self.driver, 25).until(
            EC.element_to_be_clickable(HarajSelectors.POST_MOBILE_INPUT)
        )
        modifier = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        for attempt in range(2):
            field.click()
            field.send_keys(modifier, "a")
            field.send_keys(Keys.BACKSPACE)
            field.clear()
            self.driver.execute_script(
                """
                const field = arguments[0];
                field.value = '';
                field.dispatchEvent(new Event('input', {bubbles: true}));
                field.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                field,
            )
            field.send_keys(phone)
            actual = self.driver.execute_script("return arguments[0].value;", field)
            if str(actual) == phone:
                self._stability_pause(0.2, 0.7)
                return
            self.log.warning("Phone field verification failed on attempt %s/2", attempt + 1)
        raise PhoneVerificationError(
            "Phone field value did not match the requested number; publish was not clicked"
        )

    def _publish_state_changed(
        self,
        driver: Any,
        submit: Any,
        initial_url: str,
    ) -> bool:
        if driver.current_url != initial_url:
            return True
        try:
            return not submit.is_displayed()
        except StaleElementReferenceException:
            return True

    def _stability_pause(self, low: float = 0.4, high: float = 1.1) -> None:
        self._sleep(self._random_uniform(low, high))
