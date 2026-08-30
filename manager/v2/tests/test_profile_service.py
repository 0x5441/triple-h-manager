from unittest.mock import Mock

from app.browser import ManualVerificationTimeoutError, ProfileInUseError
from app.models import Account, AccountStatus
from app.services import ProfileService


def make_account() -> Account:
    return Account("account-1", "حساب", "0500000000", "secret")


def test_profile_service_returns_valid_session_and_always_quits() -> None:
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.ensure_logged_in.return_value = AccountStatus.SESSION_VALID
    page_factory = Mock(return_value=page)
    service = ProfileService(browser_factory, page_factory=page_factory)

    result = service.test_profile(make_account())

    assert result.success is True
    assert result.status is AccountStatus.SESSION_VALID
    assert result.test_mode is True
    driver.quit.assert_called_once_with()


def test_profile_service_quits_after_page_failure() -> None:
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.ensure_logged_in.side_effect = RuntimeError("site unavailable")
    service = ProfileService(browser_factory, page_factory=Mock(return_value=page))

    result = service.test_profile(make_account())

    assert result.success is False
    assert result.status is AccountStatus.FAILED
    driver.quit.assert_called_once_with()


def test_profile_service_reports_busy_profile_without_driver() -> None:
    browser_factory = Mock()
    browser_factory.create.side_effect = ProfileInUseError("busy")
    service = ProfileService(browser_factory)

    result = service.test_profile(make_account())

    assert result.success is False
    assert result.status is AccountStatus.PROFILE_BUSY
    assert "another Chrome" in result.message


def test_profile_service_reports_manual_verification_timeout_and_quits() -> None:
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.ensure_logged_in.side_effect = ManualVerificationTimeoutError("manual timeout")
    service = ProfileService(browser_factory, page_factory=Mock(return_value=page))

    result = service.test_profile(make_account())

    assert result.status is AccountStatus.MANUAL_VERIFICATION_REQUIRED
    assert result.success is False
    driver.quit.assert_called_once_with()
