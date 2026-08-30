"""Google Sheet preview and publish controls."""

import tkinter as tk
from tkinter import ttk

from app.models import Advertisement


class PublishTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, callbacks: dict[str, object]) -> None:
        super().__init__(parent, padding=12)
        self.callbacks = callbacks
        self._advertisements: dict[str, Advertisement] = {}
        safety = ttk.LabelFrame(self, text="أمان النشر", padding=10)
        safety.pack(fill="x")
        self.dry_run_var = tk.BooleanVar(value=True)
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            safety,
            text="تجربة بدون نشر — تعبئة النموذج والتوقف قبل الزر النهائي",
            variable=self.dry_run_var,
        ).pack(side="right", padx=8)
        ttk.Checkbutton(safety, text="Chrome مخفي", variable=self.headless_var).pack(side="left")

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=8)
        self.preview_button = ttk.Button(toolbar, text="معاينة إعلانات الشيت", command=self.callbacks["preview"])
        self.preview_button.pack(side="right")
        self.summary_label = ttk.Label(toolbar, text="لم تُحمّل معاينة بعد")
        self.summary_label.pack(side="left")

        columns = ("account", "title", "phone", "image", "source")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        headings = {
            "account": "الحساب",
            "title": "العنوان",
            "phone": "رقم الجوال",
            "image": "الصورة",
            "source": "مفتاح المصدر",
        }
        widths = {"account": 120, "title": 280, "phone": 120, "image": 100, "source": 180}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center")
        self.tree.pack(fill="both", expand=True)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        self.buttons: list[ttk.Button] = [self.preview_button]
        for text, action in (
            ("نشر المحدد", "selected"),
            ("نشر حساب الإعلان المحدد", "account"),
            ("نشر الجميع", "all"),
        ):
            button = ttk.Button(actions, text=text, command=lambda name=action: self.callbacks[name]())
            button.pack(side="right", padx=4)
            self.buttons.append(button)

    def set_advertisements(self, advertisements: list[Advertisement], account_names: dict[str, str], summary: str) -> None:
        self._advertisements = {advertisement.id: advertisement for advertisement in advertisements}
        self.tree.delete(*self.tree.get_children())
        for advertisement in advertisements:
            self.tree.insert(
                "",
                "end",
                iid=advertisement.id,
                values=(
                    account_names.get(advertisement.account_id, advertisement.account_id),
                    advertisement.title,
                    advertisement.phone or "—",
                    "غير مدعومة" if advertisement.image else "—",
                    advertisement.source_key[:20],
                ),
            )
        self.summary_label.configure(text=summary)

    def selected_advertisements(self) -> list[Advertisement]:
        return [self._advertisements[item_id] for item_id in self.tree.selection() if item_id in self._advertisements]

    def all_advertisements(self) -> list[Advertisement]:
        return list(self._advertisements.values())

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self.buttons:
            button.configure(state=state)

