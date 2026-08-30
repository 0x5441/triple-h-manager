from unittest.mock import Mock

import pytest
from selenium.common.exceptions import TimeoutException

from app.browser import (
    HarajPage,
    HarajSelectors,
    ImageUploadNotSupportedError,
    PhoneVerificationError,
    PublishVerificationError,
)
from app.models import Advertisement


def make_advertisement(**changes) -> Advertisement:
    values = {
        "id": "ad-1",
        "account_id": "account-1",
        "title": "عنوان",
        "body": "نص الإعلان",
        "phone": "0500000000",
    }
    values.update(changes)
    return Advertisement(**values)


def test_publish_dry_run_fills_in_required_order_and_never_requests_submit() -> None:
    driver = Mock()
    agreement = Mock()
    agreement.is_selected.return_value = True
    wait = Mock()
    wait.until.return_value = agreement
    page = HarajPage(driver, wait_factory=lambda _driver, _timeout: wait, sleep_func=lambda _delay: None)
    page.open_home = Mock()
    events: list[object] = []
    page._click_locator = Mock(side_effect=lambda locator: events.append(("click", locator)))
    page._dismiss_incomplete_post_prompt = Mock(side_effect=lambda: events.append(("dismiss-draft",)))
    page._fill_text = Mock(side_effect=lambda locator, value: events.append(("text", locator, value)))
    page._fill_phone_field = Mock(side_effect=lambda value: events.append(("phone", value)))

    executed = page.publish_ad(make_advertisement())

    assert executed is False
    assert events == [
        ("click", HarajSelectors.ADD_POST_BUTTON),
        ("dismiss-draft",),
        ("click", HarajSelectors.SERVICE_POST_TYPE),
        ("click", HarajSelectors.STEP_TWO_CONTINUE),
        ("click", HarajSelectors.STEP_FOUR_CONTINUE),
        ("text", HarajSelectors.POST_TITLE_INPUT, "عنوان"),
        ("phone", "0500000000"),
        ("text", HarajSelectors.POST_BODY_INPUT, "نص الإعلان"),
    ]


def test_incomplete_post_prompt_clicks_no_and_continues() -> None:
    driver = Mock()
    button = Mock()
    wait = Mock()
    wait.until.return_value = button
    page = HarajPage(
        driver,
        wait_factory=lambda _driver, timeout: wait if timeout == 5 else Mock(),
        sleep_func=lambda _delay: None,
    )

    assert page._dismiss_incomplete_post_prompt() is True
    button.click.assert_called_once_with()


def test_missing_incomplete_post_prompt_does_not_stop_publish_flow() -> None:
    wait = Mock()
    wait.until.side_effect = TimeoutException()
    page = HarajPage(Mock(), wait_factory=lambda _driver, _timeout: wait)

    assert page._dismiss_incomplete_post_prompt() is False


def test_phone_field_is_cleared_twice_and_failure_prevents_publish() -> None:
    driver = Mock()
    driver.execute_script.side_effect = [None, "wrong", None, "still-wrong"]
    field = Mock()
    wait = Mock()
    wait.until.return_value = field
    page = HarajPage(driver, wait_factory=lambda _driver, _timeout: wait, sleep_func=lambda _delay: None)

    with pytest.raises(PhoneVerificationError, match="not clicked"):
        page._fill_phone_field("0500000000")

    assert field.clear.call_count == 2
    assert field.send_keys.call_count == 6


def test_non_empty_image_fails_before_opening_page() -> None:
    page = HarajPage(Mock(), sleep_func=lambda _delay: None)
    page.open_home = Mock()

    with pytest.raises(ImageUploadNotSupportedError, match="not implemented"):
        page.publish_ad(make_advertisement(image="image.jpg"))

    page.open_home.assert_not_called()


def test_submit_click_without_observable_change_is_not_success() -> None:
    driver = Mock()
    driver.current_url = "https://haraj.com.sa/add"
    agreement = Mock()
    agreement.is_selected.return_value = True
    agreement_wait = Mock()
    agreement_wait.until.return_value = agreement
    submit = Mock()
    submit.text = "نشر"
    submit.get_attribute.return_value = None
    submit.is_enabled.return_value = True
    submit.is_displayed.return_value = True
    submit_wait = Mock()
    submit_wait.until.return_value = submit
    verification_wait = Mock()
    verification_wait.until.side_effect = TimeoutException()
    waits = iter((agreement_wait, submit_wait, verification_wait))
    page = HarajPage(
        driver,
        wait_factory=lambda _driver, _timeout: next(waits),
        sleep_func=lambda _delay: None,
    )
    page.open_home = Mock()
    page._click_locator = Mock()
    page._dismiss_incomplete_post_prompt = Mock(return_value=False)
    page._fill_text = Mock()
    page._fill_phone_field = Mock()

    with pytest.raises(PublishVerificationError, match="no page transition"):
        page.publish_ad(make_advertisement(), dry_run=False)

    submit.click.assert_called_once_with()
