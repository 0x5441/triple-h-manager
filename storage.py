import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class AccountStore:
    def __init__(self):
        self.data_dir = Path(__file__).resolve().parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.data_dir / ".secret.key"
        self.accounts_path = self.data_dir / "accounts.enc"
        self.cipher = Fernet(self._load_or_create_key())

    def _load_or_create_key(self):
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key

    def load(self):
        if not self.accounts_path.exists():
            return []
        try:
            decrypted = self.cipher.decrypt(self.accounts_path.read_bytes())
            accounts = json.loads(decrypted.decode("utf-8"))
            return accounts if isinstance(accounts, list) else []
        except (InvalidToken, json.JSONDecodeError) as exc:
            raise RuntimeError("تعذر قراءة بيانات الحسابات المشفرة") from exc

    def save(self, accounts):
        raw = json.dumps(accounts, ensure_ascii=False, indent=2).encode("utf-8")
        temporary = self.accounts_path.with_suffix(".tmp")
        temporary.write_bytes(self.cipher.encrypt(raw))
        temporary.replace(self.accounts_path)
