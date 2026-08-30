"""Account domain model and its serialized representation."""

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import AccountStatus


@dataclass(slots=True)
class Account:
    id: str
    name: str
    username: str
    password: str
    paused: bool = False
    last_status: AccountStatus = AccountStatus.NEVER_RUN
    last_run_at: str = ""
    ads: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.name = self.name.strip()
        self.username = self.username.strip()
        self.last_run_at = self.last_run_at.strip()
        self.created_at = self.created_at.strip()
        self.updated_at = self.updated_at.strip()
        self.ads = [str(ad).strip() for ad in self.ads if str(ad).strip()]
        if not isinstance(self.last_status, AccountStatus):
            self.last_status = AccountStatus(self.last_status)
        if not self.id:
            raise ValueError("Account id must not be empty")
        if not self.name:
            raise ValueError("Account name must not be empty")
        if not self.username:
            raise ValueError("Account username must not be empty")
        if not self.password:
            raise ValueError("Account password must not be empty")
        if self.paused:
            self.last_status = AccountStatus.PAUSED

    @property
    def status(self) -> AccountStatus:
        """Compatibility alias for callers that refer to the current status."""
        return self.last_status

    def to_dict(self) -> dict[str, Any]:
        """Return the complete persistable account record."""
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password": self.password,
            "paused": self.paused,
            "last_status": self.last_status.value,
            "last_run_at": self.last_run_at,
            "ads": list(self.ads),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        """Build an account from a V2 storage record."""
        if not isinstance(data, dict):
            raise ValueError("Account record must be an object")
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            paused=bool(data.get("paused", False)),
            last_status=AccountStatus(data.get("last_status", AccountStatus.NEVER_RUN.value)),
            last_run_at=str(data.get("last_run_at", "")),
            ads=list(data.get("ads", [])),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )
