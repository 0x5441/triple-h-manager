"""Accounts and saved-ad links tab."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from app.models import Account


class AccountsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, callbacks: dict[str, Any]) -> None:
        super().__init__(parent, padding=10)
        self.callbacks = callbacks
        self._accounts: dict[str, Account] = {}
        self._action_buttons: list[ttk.Button] = []
        self._build()

    def _build(self) -> None:
        split = ttk.Panedwindow(self, orient="horizontal")
        split.pack(fill="both", expand=True)
        accounts_box = ttk.LabelFrame(split, text="الحسابات", padding=8)
        ads_box = ttk.LabelFrame(split, text="روابط إعلانات الحساب", padding=8)
        split.add(accounts_box, weight=4)
        split.add(ads_box, weight=2)

        columns = ("name", "username", "active", "session", "status", "last_run")
        self.tree = ttk.Treeview(accounts_box, columns=columns, show="headings", height=18)
        headings = {
            "name": "الاسم",
            "username": "رقم الحساب",
            "active": "التفعيل",
            "session": "حالة الجلسة",
            "status": "آخر حالة",
            "last_run": "آخر تشغيل",
        }
        widths = {"name": 130, "username": 120, "active": 75, "session": 120, "status": 120, "last_run": 150}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        buttons = ttk.Frame(accounts_box)
        buttons.pack(fill="x", pady=(8, 0))
        specs = (
            ("إضافة", "add"),
            ("تعديل", "edit"),
            ("حذف", "delete"),
            ("إيقاف مؤقت", "pause"),
            ("تفعيل", "activate"),
            ("فحص الجلسة", "check_session"),
            ("تجديد الجلسة", "refresh_session"),
            ("فتح البروفايل", "open_profile"),
        )
        for text, action in specs:
            button = ttk.Button(buttons, text=text, command=lambda name=action: self._invoke(name))
            button.pack(side="right", padx=2, pady=2)
            self._action_buttons.append(button)

        self.ads_list = tk.Listbox(ads_box, selectmode="extended", font=("Arial", 11))
        self.ads_list.pack(fill="both", expand=True)
        ad_buttons = ttk.Frame(ads_box)
        ad_buttons.pack(fill="x", pady=(8, 0))
        add_ad = ttk.Button(ad_buttons, text="إضافة رابط", command=self._add_ad)
        delete_ad = ttk.Button(ad_buttons, text="حذف المحدد", command=self._delete_ads)
        add_ad.pack(side="right", padx=3)
        delete_ad.pack(side="right", padx=3)
        self._action_buttons.extend((add_ad, delete_ad))

    def selected_account_id(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def selected_account(self) -> Account | None:
        account_id = self.selected_account_id()
        return self._accounts.get(account_id) if account_id else None

    def set_accounts(self, accounts: list[Account], session_statuses: dict[str, str]) -> None:
        previous = self.selected_account_id()
        self._accounts = {account.id: account for account in accounts}
        self.tree.delete(*self.tree.get_children())
        for account in accounts:
            status_labels = {
                "never_run": "لم يعمل بعد",
                "idle": "جاهز",
                "running": "قيد التشغيل",
                "success": "نجح",
                "partial_success": "نجاح جزئي",
                "failed": "فشل",
                "paused": "متوقف مؤقتًا",
            }
            self.tree.insert(
                "",
                "end",
                iid=account.id,
                values=(
                    account.name,
                    account.username,
                    "متوقف" if account.paused else "مفعّل",
                    session_statuses.get(account.id, "غير مفحوصة"),
                    status_labels.get(account.last_status.value, account.last_status.value),
                    account.last_run_at or "—",
                ),
            )
        if previous in self._accounts:
            self.tree.selection_set(previous)
        elif accounts:
            self.tree.selection_set(accounts[0].id)
        self._selection_changed()

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)

    def ask_account(self, existing: Account | None = None) -> dict[str, str] | None:
        dialog = tk.Toplevel(self)
        dialog.title("تعديل حساب" if existing else "إضافة حساب")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        values = {
            "name": existing.name if existing else "",
            "username": existing.username if existing else "",
            "password": existing.password if existing else "",
        }
        entries: dict[str, ttk.Entry] = {}
        labels = (("name", "الاسم"), ("username", "رقم الحساب"), ("password", "كلمة المرور"))
        for row, (key, label) in enumerate(labels):
            ttk.Label(dialog, text=label).grid(row=row, column=1, padx=12, pady=10, sticky="e")
            entry = ttk.Entry(dialog, width=38, justify="right", show="•" if key == "password" else "")
            entry.grid(row=row, column=0, padx=12, pady=10)
            entry.insert(0, values[key])
            entries[key] = entry
        result: dict[str, str] = {}

        def save() -> None:
            result.update({key: entry.get().strip() for key, entry in entries.items()})
            if not all(result.values()):
                messagebox.showerror("بيانات ناقصة", "أدخل الاسم ورقم الحساب وكلمة المرور", parent=dialog)
                result.clear()
                return
            dialog.destroy()

        ttk.Button(dialog, text="حفظ", command=save).grid(row=4, column=0, columnspan=2, pady=12)
        dialog.wait_window()
        return result or None

    def _selection_changed(self, _event: Any = None) -> None:
        self.ads_list.delete(0, "end")
        account = self.selected_account()
        if account:
            for url in account.ads:
                self.ads_list.insert("end", url)
        callback = self.callbacks.get("selection_changed")
        if callback:
            callback(account.id if account else None)

    def _invoke(self, action: str) -> None:
        callback = self.callbacks.get(action)
        if callback:
            callback()

    def _add_ad(self) -> None:
        account_id = self.selected_account_id()
        if not account_id:
            messagebox.showinfo("تنبيه", "اختر حسابًا أولًا", parent=self)
            return
        url = simpledialog.askstring("إضافة رابط", "رابط إعلان حراج:", parent=self)
        if url and self.callbacks.get("add_ad"):
            self.callbacks["add_ad"](url.strip())

    def _delete_ads(self) -> None:
        selected = list(self.ads_list.curselection())
        if selected and self.callbacks.get("delete_ads"):
            self.callbacks["delete_ads"](selected)
