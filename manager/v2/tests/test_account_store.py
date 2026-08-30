import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.models import Account
from app.storage import AccountStore, AccountStoreCorruptedError, DuplicateAccountError


def make_store(tmp_path: Path) -> AccountStore:
    return AccountStore(tmp_path / "accounts.enc", tmp_path / ".secret.key")


def make_account(account_id: str = "account-1", username: str = "0500000000") -> Account:
    return Account(
        id=account_id,
        name="حساب تجريبي",
        username=username,
        password="secret",
        ads=["https://haraj.com.sa/example"],
        created_at="2026-08-30T10:00:00+03:00",
        updated_at="2026-08-30T10:00:00+03:00",
    )


def test_store_saves_and_reads_complete_account(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    original = make_account()

    store.add_account(original)

    assert store.list_accounts() == [original]
    assert store.get_account(original.id).ads == original.ads


def test_accounts_file_is_encrypted_and_key_is_separate(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_account(make_account())

    encrypted = store.accounts_path.read_bytes()

    assert b"0500000000" not in encrypted
    assert b"secret" not in encrypted
    decrypted = Fernet(store.key_path.read_bytes()).decrypt(encrypted)
    payload = json.loads(decrypted)
    assert payload["schema_version"] == 1
    assert payload["accounts"][0]["username"] == "0500000000"


def test_store_prevents_duplicate_normalized_username(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_account(make_account())

    with pytest.raises(DuplicateAccountError, match="username"):
        store.add_account(make_account("account-2", "050 000 0000"))


def test_store_rejects_tampered_ciphertext(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_account(make_account())
    store.accounts_path.write_bytes(b"not-a-fernet-token")

    with pytest.raises(AccountStoreCorruptedError):
        store.list_accounts()


def test_store_rejects_wrong_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_account(make_account())
    store.key_path.write_bytes(Fernet.generate_key())

    with pytest.raises(AccountStoreCorruptedError):
        store.list_accounts()


def test_raw_file_cannot_be_decrypted_with_unrelated_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_account(make_account())

    with pytest.raises(InvalidToken):
        Fernet(Fernet.generate_key()).decrypt(store.accounts_path.read_bytes())
