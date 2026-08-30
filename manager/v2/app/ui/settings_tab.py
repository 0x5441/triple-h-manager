"""Google Sheets and runtime settings controls."""

import tkinter as tk
from tkinter import ttk

from app.models import AppSettings


class SettingsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, callbacks: dict[str, object]) -> None:
        super().__init__(parent, padding=18)
        self.callbacks = callbacks
        self.url_var = tk.StringVar()
        self.worksheet_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.headless_var = tk.BooleanVar(value=False)
        form = ttk.LabelFrame(self, text="إعدادات Google Sheets والتشغيل", padding=14)
        form.pack(fill="x")
        ttk.Label(form, text="رابط Google Sheet العام").grid(row=0, column=1, sticky="e", padx=8, pady=8)
        ttk.Entry(form, textvariable=self.url_var, width=75, justify="right").grid(row=0, column=0, sticky="ew", pady=8)
        ttk.Label(form, text="تبويب الإعلانات").grid(row=1, column=1, sticky="e", padx=8, pady=8)
        self.worksheet_combo = ttk.Combobox(form, textvariable=self.worksheet_var, width=45, justify="right")
        self.worksheet_combo.grid(row=1, column=0, sticky="e", pady=8)
        ttk.Label(form, text="رقم افتراضي عند فراغ الشيت").grid(row=2, column=1, sticky="e", padx=8, pady=8)
        ttk.Entry(form, textvariable=self.phone_var, width=35, justify="right").grid(row=2, column=0, sticky="e", pady=8)
        ttk.Checkbutton(form, text="تشغيل Chrome مخفيًا افتراضيًا", variable=self.headless_var).grid(
            row=3, column=0, sticky="e", pady=8
        )
        form.columnconfigure(0, weight=1)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=12)
        self.fetch_button = ttk.Button(buttons, text="جلب التبويبات", command=self.callbacks["fetch_sheets"])
        self.save_button = ttk.Button(buttons, text="حفظ الإعدادات", command=self.callbacks["save"])
        self.fetch_button.pack(side="right", padx=4)
        self.save_button.pack(side="right", padx=4)

    def set_settings(self, settings: AppSettings) -> None:
        self.url_var.set(settings.spreadsheet_url)
        self.worksheet_var.set(settings.worksheet)
        self.phone_var.set(settings.default_phone)
        self.headless_var.set(settings.headless)

    def values(self) -> dict[str, object]:
        return {
            "spreadsheet_url": self.url_var.get().strip(),
            "worksheet": self.worksheet_var.get().strip(),
            "default_phone": self.phone_var.get().strip(),
            "headless": self.headless_var.get(),
        }

    def set_sheet_names(self, names: list[str]) -> None:
        self.worksheet_combo.configure(values=names, state="readonly")
        if self.worksheet_var.get() not in names and names:
            self.worksheet_var.set(names[0])

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.fetch_button.configure(state=state)
        self.save_button.configure(state=state)
        self.worksheet_combo.configure(state="disabled" if busy else "normal")
