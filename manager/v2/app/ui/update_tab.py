"""Existing-ad update controls."""

import tkinter as tk
from tkinter import ttk

from app.models import Account


class UpdateTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, callbacks: dict[str, object]) -> None:
        super().__init__(parent, padding=12)
        self.callbacks = callbacks
        self._display_to_id: dict[str, str] = {}
        self._accounts: dict[str, Account] = {}
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="الحساب:").pack(side="right", padx=5)
        self.account_combo = ttk.Combobox(top, state="readonly", width=35, justify="right")
        self.account_combo.pack(side="right", padx=5)
        self.account_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_ads())
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="تشغيل بدون إظهار Chrome", variable=self.headless_var).pack(side="left")

        box = ttk.LabelFrame(self, text="روابط الإعلانات", padding=8)
        box.pack(fill="both", expand=True, pady=10)
        self.ads_list = tk.Listbox(box, selectmode="extended", font=("Arial", 11))
        self.ads_list.pack(fill="both", expand=True)
        actions = ttk.Frame(self)
        actions.pack(fill="x")
        self.buttons: list[ttk.Button] = []
        for text, action in (
            ("تحديث المحدد", "selected"),
            ("تحديث الحساب", "account"),
            ("تحديث الجميع", "all"),
        ):
            button = ttk.Button(actions, text=text, command=lambda name=action: self.callbacks[name]())
            button.pack(side="right", padx=4)
            self.buttons.append(button)

    def set_accounts(self, accounts: list[Account]) -> None:
        current_id = self.selected_account_id()
        self._accounts = {account.id: account for account in accounts}
        self._display_to_id = {f"{account.name} — {account.username}": account.id for account in accounts}
        values = list(self._display_to_id)
        self.account_combo.configure(values=values)
        selected_display = next((label for label, value in self._display_to_id.items() if value == current_id), "")
        self.account_combo.set(selected_display or (values[0] if values else ""))
        self._refresh_ads()

    def selected_account_id(self) -> str | None:
        return self._display_to_id.get(self.account_combo.get())

    def selected_urls(self) -> list[str]:
        return [self.ads_list.get(index) for index in self.ads_list.curselection()]

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self.buttons:
            button.configure(state=state)
        self.account_combo.configure(state="disabled" if busy else "readonly")

    def _refresh_ads(self) -> None:
        self.ads_list.delete(0, "end")
        account_id = self.selected_account_id()
        account = self._accounts.get(account_id or "")
        if account:
            for url in account.ads:
                self.ads_list.insert("end", url)
