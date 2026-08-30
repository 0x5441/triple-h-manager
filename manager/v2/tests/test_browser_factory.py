from pathlib import Path

import pytest
from selenium.common.exceptions import WebDriverException

from app.browser import BrowserFactory, ProfileInUseError


class CapturingDriverBuilder:
    def __init__(self) -> None:
        self.options = None
        self.driver = object()

    def __call__(self, *, options):
        self.options = options
        return self.driver


def test_browser_factory_uses_only_account_profile_and_selenium_manager_shape(tmp_path: Path) -> None:
    builder = CapturingDriverBuilder()
    factory = BrowserFactory(tmp_path / "profiles", driver_builder=builder)

    driver = factory.create("stable-account-id", headless=True)

    expected_profile = (tmp_path / "profiles" / "stable-account-id").resolve()
    assert driver is builder.driver
    assert expected_profile.is_dir()
    assert f"--user-data-dir={expected_profile}" in builder.options.arguments
    assert "--profile-directory=Default" in builder.options.arguments
    assert "--headless=new" in builder.options.arguments


def test_browser_factory_rejects_account_id_path_traversal(tmp_path: Path) -> None:
    factory = BrowserFactory(tmp_path / "profiles", driver_builder=CapturingDriverBuilder())

    with pytest.raises(ValueError, match="account_id"):
        factory.create("../personal-profile")


def test_browser_factory_reports_profile_in_use(tmp_path: Path) -> None:
    def busy_driver_builder(*, options):
        raise WebDriverException("user data directory is already in use")

    factory = BrowserFactory(tmp_path / "profiles", driver_builder=busy_driver_builder)

    with pytest.raises(ProfileInUseError, match="already open"):
        factory.create("account-1")
