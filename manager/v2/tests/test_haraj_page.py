from unittest.mock import Mock

from selenium.common.exceptions import TimeoutException

import pytest

from app.browser import HarajPage, ManualVerificationTimeoutError, UpdateVerificationError
from app.models import Account, AccountStatus


def make_account() -> Account:
    return Account("account-1", "حساب", "0500000000", "secret")


def test_ensure_logged_in_skips_login_for_valid_saved_session() -> None:
    page = HarajPage(Mock())
    page.open_home = Mock()
    page.is_logged_in = Mock(return_value=True)
    page.login = Mock()

    status = page.ensure_logged_in(make_account())

    assert status is AccountStatus.SESSION_VALID
    page.open_home.assert_called_once_with()
    page.login.assert_not_called()


def test_ensure_logged_in_refreshes_expired_session() -> None:
    page = HarajPage(Mock())
    page.open_home = Mock()
    page.is_logged_in = Mock(return_value=False)
    page.login = Mock()

    status = page.ensure_logged_in(make_account(), manual_verification_timeout=90)

    assert status is AccountStatus.SESSION_REFRESHED
    page.login.assert_called_once_with(make_account(), manual_verification_timeout=90)


def test_login_waits_for_visible_manual_verification() -> None:
    login_link = Mock()
    username = Mock()
    username_continue = Mock()
    password = Mock()
    submit = Mock()
    form_wait = Mock()
    form_wait.until.side_effect = [login_link, username, username_continue, password, submit]
    initial_session_wait = Mock()
    initial_session_wait.until.side_effect = TimeoutException()
    manual_wait = Mock()
    manual_wait.until.return_value = Mock()

    waits = {25: form_wait, 15: initial_session_wait, 120: manual_wait}
    page = HarajPage(Mock(), wait_factory=lambda _driver, timeout: waits[timeout])

    page.login(make_account(), manual_verification_timeout=120)

    username.send_keys.assert_called_once_with("0500000000")
    password.send_keys.assert_called_once_with("secret")
    manual_wait.until.assert_called_once()


def test_headless_login_reports_that_manual_verification_needs_visible_browser() -> None:
    form_wait = Mock()
    form_wait.until.side_effect = [Mock(), Mock(), Mock(), Mock(), Mock()]
    initial_session_wait = Mock()
    initial_session_wait.until.side_effect = TimeoutException()
    waits = {25: form_wait, 15: initial_session_wait}
    page = HarajPage(Mock(), headless=True, wait_factory=lambda _driver, timeout: waits[timeout])

    with pytest.raises(ManualVerificationTimeoutError, match="visible browser"):
        page.login(make_account())


def test_update_ad_dry_run_finds_button_without_clicking() -> None:
    driver = Mock()
    navigation_wait = Mock()
    navigation_wait.until.return_value = True
    button = Mock()
    button_wait = Mock()
    button_wait.until.return_value = button
    waits = iter((navigation_wait, button_wait))
    page = HarajPage(driver, wait_factory=lambda _driver, _timeout: next(waits))

    executed = page.update_ad("https://haraj.com.sa/example", dry_run=True)

    assert executed is False
    button.click.assert_not_called()


def test_update_ad_does_not_treat_unverified_click_as_success() -> None:
    driver = Mock()
    driver.current_url = "https://haraj.com.sa/example"
    navigation_wait = Mock()
    navigation_wait.until.return_value = True
    button = Mock()
    button.text = "تحديث"
    button.get_attribute.return_value = None
    button.is_enabled.return_value = True
    button.is_displayed.return_value = True
    button_wait = Mock()
    button_wait.until.return_value = button
    verification_wait = Mock()
    verification_wait.until.side_effect = TimeoutException()
    waits = iter((navigation_wait, button_wait, verification_wait))
    page = HarajPage(driver, wait_factory=lambda _driver, _timeout: next(waits))

    with pytest.raises(UpdateVerificationError, match="no observable"):
        page.update_ad("https://haraj.com.sa/example")

    button.click.assert_called_once_with()


def test_update_ad_accepts_changed_button_state_as_verification() -> None:
    driver = Mock()
    driver.current_url = "https://haraj.com.sa/example"
    navigation_wait = Mock()
    navigation_wait.until.return_value = True
    button = Mock()
    button.text = "تحديث"
    button.get_attribute.return_value = None
    button.is_enabled.side_effect = [True, False]
    button.is_displayed.return_value = True
    button_wait = Mock()
    button_wait.until.return_value = button
    verification_wait = Mock()
    verification_wait.until.side_effect = lambda predicate: predicate(driver)
    waits = iter((navigation_wait, button_wait, verification_wait))
    page = HarajPage(driver, wait_factory=lambda _driver, _timeout: next(waits))

    assert page.update_ad("https://haraj.com.sa/example") is True
