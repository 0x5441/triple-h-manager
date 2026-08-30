"""Advertisement domain model."""

from dataclasses import dataclass


@dataclass(slots=True)
class Advertisement:
    id: str
    account_id: str
    title: str
    body: str
    phone: str = ""
    image: str = ""
    source_key: str = ""
    existing_url: str = ""

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.account_id = self.account_id.strip()
        self.title = self.title.strip()
        self.body = self.body.strip()
        self.phone = self.phone.strip()
        self.image = self.image.strip()
        self.source_key = self.source_key.strip()
        self.existing_url = self.existing_url.strip()
        if not self.id:
            raise ValueError("Advertisement id must not be empty")
        if not self.account_id:
            raise ValueError("Advertisement account_id must not be empty")
        if not self.title and not self.existing_url:
            raise ValueError("Advertisement requires a title or an existing URL")
        if self.title and not self.body:
            raise ValueError("A publishable advertisement requires a body")

