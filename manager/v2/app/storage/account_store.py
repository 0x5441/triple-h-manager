"""Encrypted account persistence isolated from UI and business services."""

import json
import os
import threading
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import ACCOUNTS_FILE, SECRET_KEY_FILE
from app.models import Account


SCHEMA_VERSION = 1


class AccountStoreError(RuntimeError):
    """Base error for account persistence failures."""


class AccountStoreCorruptedError(AccountStoreError):
    """Raised when encrypted data or its key cannot be decoded safely."""


class AccountNotFoundError(AccountStoreError):
    """Raised when an account id does not exist."""


class DuplicateAccountError(AccountStoreError):
    """Raised when an id or normalized username is already stored."""


def normalize_username(username: str) -> str:
    """Normalize an account number for equality without assuming a country code."""
    value = str(username).strip()
    digits = "".join(character for character in value if character.isdigit())
    return digits or value.casefold()


class AccountStore:
    """Atomically persist complete account records as one Fernet token."""

    def __init__(
        self,
        accounts_path: Path | str = ACCOUNTS_FILE,
        key_path: Path | str = SECRET_KEY_FILE,
    ) -> None:
        self.accounts_path = Path(accounts_path)
        self.key_path = Path(key_path)
        self._lock = threading.RLock()

    def list_accounts(self) -> list[Account]:
        with self._lock:
            return self._load_unlocked()

    def get_account(self, account_id: str) -> Account:
        with self._lock:
            for account in self._load_unlocked():
                if account.id == account_id:
                    return account
        raise AccountNotFoundError(f"Account not found: {account_id}")

    def add_account(self, account: Account) -> Account:
        with self._lock:
            accounts = self._load_unlocked()
            self._ensure_unique(accounts, account)
            accounts.append(account)
            self._save_unlocked(accounts)
        return account

    def update_account(self, account: Account) -> Account:
        with self._lock:
            accounts = self._load_unlocked()
            index = next((i for i, item in enumerate(accounts) if item.id == account.id), None)
            if index is None:
                raise AccountNotFoundError(f"Account not found: {account.id}")
            self._ensure_unique(accounts, account, exclude_id=account.id)
            accounts[index] = account
            self._save_unlocked(accounts)
        return account

    def delete_account(self, account_id: str) -> Account:
        with self._lock:
            accounts = self._load_unlocked()
            index = next((i for i, item in enumerate(accounts) if item.id == account_id), None)
            if index is None:
                raise AccountNotFoundError(f"Account not found: {account_id}")
            deleted = accounts.pop(index)
            self._save_unlocked(accounts)
        return deleted

    def _ensure_unique(
        self,
        accounts: list[Account],
        candidate: Account,
        exclude_id: str | None = None,
    ) -> None:
        normalized = normalize_username(candidate.username)
        for account in accounts:
            if account.id == exclude_id:
                continue
            if account.id == candidate.id:
                raise DuplicateAccountError(f"Account id already exists: {candidate.id}")
            if normalize_username(account.username) == normalized:
                raise DuplicateAccountError("Account username already exists")

    def _load_unlocked(self) -> list[Account]:
        if not self.accounts_path.exists():
            return []
        if not self.key_path.exists():
            raise AccountStoreCorruptedError("Account key is missing")
        try:
            cipher = Fernet(self.key_path.read_bytes())
            decrypted = cipher.decrypt(self.accounts_path.read_bytes())
            payload: Any = json.loads(decrypted.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Storage root must be an object")
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("Unsupported account storage schema")
            records = payload.get("accounts")
            if not isinstance(records, list):
                raise ValueError("Accounts must be a list")
            accounts = [Account.from_dict(record) for record in records]
            self._ensure_collection_unique(accounts)
            return accounts
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError, OSError) as exc:
            raise AccountStoreCorruptedError("Encrypted account data could not be read") from exc

    def _save_unlocked(self, accounts: list[Account]) -> None:
        self._ensure_collection_unique(accounts)
        cipher = Fernet(self._load_or_create_key())
        payload = {
            "schema_version": SCHEMA_VERSION,
            "accounts": [account.to_dict() for account in accounts],
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encrypted = cipher.encrypt(raw)
        self.accounts_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.accounts_path.with_name(f".{self.accounts_path.name}.tmp")
        try:
            temporary.write_bytes(encrypted)
            self._restrict_permissions(temporary)
            temporary.replace(self.accounts_path)
            self._restrict_permissions(self.accounts_path)
        except OSError as exc:
            raise AccountStoreError("Encrypted account data could not be saved") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_or_create_key(self) -> bytes:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            try:
                Fernet(key)
            except (ValueError, TypeError) as exc:
                raise AccountStoreCorruptedError("Account key is invalid") from exc
            return key
        if self.accounts_path.exists():
            raise AccountStoreCorruptedError("Account key is missing")
        key = Fernet.generate_key()
        try:
            with self.key_path.open("xb") as key_file:
                key_file.write(key)
            self._restrict_permissions(self.key_path)
            return key
        except FileExistsError:
            return self.key_path.read_bytes()
        except OSError as exc:
            raise AccountStoreError("Account key could not be created") from exc

    def _ensure_collection_unique(self, accounts: list[Account]) -> None:
        ids: set[str] = set()
        usernames: set[str] = set()
        for account in accounts:
            username = normalize_username(account.username)
            if account.id in ids or username in usernames:
                raise DuplicateAccountError("Stored accounts contain duplicate ids or usernames")
            ids.add(account.id)
            usernames.add(username)

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
