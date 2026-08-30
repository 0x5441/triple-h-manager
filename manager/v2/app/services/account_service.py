"""Account business operations independent from encrypted file details."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from urllib.parse import urlparse

from app.models import Account, AccountStatus
from app.storage import AccountStore


def _current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class AccountService:
    def __init__(
        self,
        store: AccountStore,
        *,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        timestamp_factory: Callable[[], str] = _current_timestamp,
    ) -> None:
        self._store = store
        self._id_factory = id_factory
        self._timestamp_factory = timestamp_factory

    def list_accounts(self) -> list[Account]:
        return self._store.list_accounts()

    def get_account(self, account_id: str) -> Account:
        return self._store.get_account(account_id)

    def add_account(
        self,
        *,
        name: str,
        username: str,
        password: str,
        ads: list[str] | None = None,
    ) -> Account:
        timestamp = self._timestamp_factory()
        account = Account(
            id=self._id_factory(),
            name=name,
            username=username,
            password=password,
            ads=list(ads or []),
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self._store.add_account(account)

    def update_account(
        self,
        account_id: str,
        *,
        name: str | None = None,
        username: str | None = None,
        password: str | None = None,
        ads: list[str] | None = None,
    ) -> Account:
        current = self._store.get_account(account_id)
        updated = replace(
            current,
            name=current.name if name is None else name,
            username=current.username if username is None else username,
            password=current.password if password is None else password,
            ads=list(current.ads if ads is None else ads),
            updated_at=self._timestamp_factory(),
        )
        return self._store.update_account(updated)

    def delete_account(self, account_id: str) -> Account:
        return self._store.delete_account(account_id)

    def set_paused(self, account_id: str, paused: bool) -> Account:
        current = self._store.get_account(account_id)
        updated = replace(
            current,
            paused=paused,
            last_status=AccountStatus.PAUSED if paused else AccountStatus.IDLE,
            updated_at=self._timestamp_factory(),
        )
        return self._store.update_account(updated)

    def pause_account(self, account_id: str) -> Account:
        return self.set_paused(account_id, True)

    def activate_account(self, account_id: str) -> Account:
        return self.set_paused(account_id, False)

    def record_run(self, account_id: str, status: AccountStatus) -> Account:
        """Persist the latest operational status and timestamp."""
        current = self._store.get_account(account_id)
        timestamp = self._timestamp_factory()
        updated = replace(
            current,
            last_status=status,
            last_run_at=timestamp,
            updated_at=timestamp,
        )
        return self._store.update_account(updated)

    def add_ad_url(self, account_id: str, url: str) -> Account:
        normalized = str(url).strip()
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not (host == "haraj.com.sa" or host.endswith(".haraj.com.sa")):
            raise ValueError("رابط الإعلان يجب أن يكون رابط حراج HTTPS")
        current = self._store.get_account(account_id)
        if normalized in current.ads:
            return current
        return self.update_account(account_id, ads=[*current.ads, normalized])

    def remove_ad_indexes(self, account_id: str, indexes: list[int]) -> Account:
        current = self._store.get_account(account_id)
        selected = set(indexes)
        ads = [url for index, url in enumerate(current.ads) if index not in selected]
        return self.update_account(account_id, ads=ads)
