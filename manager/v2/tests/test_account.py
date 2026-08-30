import pytest

from app.models import Account, AccountStatus


def test_account_normalizes_values_and_uses_independent_advertisement_lists() -> None:
    first = Account(" account-1 ", " الحساب الأول ", " 0500000000 ", "secret")
    second = Account("account-2", "الحساب الثاني", "0500000001", "secret")

    first.ads.append("ad-1")

    assert first.id == "account-1"
    assert first.status is AccountStatus.NEVER_RUN
    assert second.ads == []


def test_account_requires_a_stable_id() -> None:
    with pytest.raises(ValueError, match="id"):
        Account("", "حساب", "0500000000", "secret")


def test_paused_account_uses_paused_status() -> None:
    account = Account("account-1", "حساب", "0500000000", "secret", paused=True)

    assert account.status is AccountStatus.PAUSED
