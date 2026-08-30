import pytest

from app.models import Advertisement


def test_publishable_advertisement_normalizes_text() -> None:
    advertisement = Advertisement(
        id=" ad-1 ",
        account_id=" account-1 ",
        title=" عنوان الإعلان ",
        body=" نص الإعلان ",
        phone=" 0500000000 ",
    )

    assert advertisement.id == "ad-1"
    assert advertisement.account_id == "account-1"
    assert advertisement.title == "عنوان الإعلان"
    assert advertisement.phone == "0500000000"


def test_existing_advertisement_can_use_url_without_publish_content() -> None:
    advertisement = Advertisement(
        id="ad-1",
        account_id="account-1",
        title="",
        body="",
        existing_url="https://haraj.com.sa/example",
    )

    assert advertisement.existing_url.startswith("https://haraj.com.sa/")


def test_publishable_advertisement_requires_body() -> None:
    with pytest.raises(ValueError, match="body"):
        Advertisement("ad-1", "account-1", "عنوان", "")

