from pathlib import Path

import pytest

from app.models import AccountStatus
from app.services import AccountService
from app.storage import AccountStore, DuplicateAccountError


def make_service(tmp_path: Path) -> AccountService:
    store = AccountStore(tmp_path / "accounts.enc", tmp_path / ".secret.key")
    ids = iter(("account-1", "account-2", "account-3"))
    timestamps = iter(
        (
            "2026-08-30T10:00:00+03:00",
            "2026-08-30T11:00:00+03:00",
            "2026-08-30T12:00:00+03:00",
            "2026-08-30T13:00:00+03:00",
        )
    )
    return AccountService(store, id_factory=lambda: next(ids), timestamp_factory=lambda: next(timestamps))


def test_service_adds_updates_and_deletes_account_with_stable_id(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    created = service.add_account(name="القديم", username="0500000000", password="secret")

    updated = service.update_account(
        created.id,
        name="الجديد",
        username="0500000001",
        password="new-secret",
        ads=["https://haraj.com.sa/example"],
    )

    assert updated.id == created.id
    assert updated.created_at == created.created_at
    assert updated.updated_at != created.updated_at
    assert updated.name == "الجديد"
    assert service.delete_account(created.id).id == created.id
    assert service.list_accounts() == []


def test_service_prevents_duplicate_username(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.add_account(name="الأول", username="0500000000", password="secret")

    with pytest.raises(DuplicateAccountError):
        service.add_account(name="الثاني", username="050-000-0000", password="secret")


def test_service_pauses_and_activates_account(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    account = service.add_account(name="حساب", username="0500000000", password="secret")

    paused = service.pause_account(account.id)
    active = service.activate_account(account.id)

    assert paused.paused is True
    assert paused.last_status is AccountStatus.PAUSED
    assert active.paused is False
    assert active.last_status is AccountStatus.IDLE
