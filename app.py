import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from bot import HarajBot
from storage import AccountStore


class HarajManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("مدير إعلانات حراج")
        self.geometry("980x650")
        self.minsize(850, 560)
        self.store = AccountStore()
        self.accounts = self.store.load()
        self.events = queue.Queue()
        self.running = False
        self._build_ui()
        self._refresh_accounts()
        self.after(150, self._read_events)

    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("TButton", padding=7)

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="مدير إعلانات حراج", font=("Arial", 18, "bold")).pack(side="right")
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="تشغيل بدون إظهار المتصفح", variable=self.headless_var).pack(side="left")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12)

        accounts_box = ttk.LabelFrame(body, text="الحسابات", padding=8)
        ads_box = ttk.LabelFrame(body, text="روابط إعلانات الحساب", padding=8)
        body.add(accounts_box, weight=2)
        body.add(ads_box, weight=3)

        self.account_tree = ttk.Treeview(accounts_box, columns=("name", "username", "ads"), show="headings", height=15)
        self.account_tree.heading("name", text="اسم الحساب")
        self.account_tree.heading("username", text="رقم الجوال")
        self.account_tree.heading("ads", text="الإعلانات")
        self.account_tree.column("name", width=130, anchor="center")
        self.account_tree.column("username", width=130, anchor="center")
        self.account_tree.column("ads", width=70, anchor="center")
        self.account_tree.pack(fill="both", expand=True)
        self.account_tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_ads())

        account_buttons = ttk.Frame(accounts_box)
        account_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(account_buttons, text="إضافة", command=self._add_account).pack(side="right", padx=2)
        ttk.Button(account_buttons, text="تعديل", command=self._edit_account).pack(side="right", padx=2)
        ttk.Button(account_buttons, text="حذف", command=self._delete_account).pack(side="right", padx=2)

        self.ads_list = tk.Listbox(ads_box, font=("Arial", 11), selectmode="extended")
        self.ads_list.pack(fill="both", expand=True)
        ad_buttons = ttk.Frame(ads_box)
        ad_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(ad_buttons, text="إضافة رابط", command=self._add_ad).pack(side="right", padx=2)
        ttk.Button(ad_buttons, text="حذف المحدد", command=self._delete_ads).pack(side="right", padx=2)

        actions = ttk.Frame(self, padding=12)
        actions.pack(fill="x")
        self.start_all_button = ttk.Button(actions, text="تحديث جميع الحسابات", command=self._start_all)
        self.start_all_button.pack(side="right", padx=3)
        self.start_one_button = ttk.Button(actions, text="تحديث الحساب المحدد", command=self._start_selected)
        self.start_one_button.pack(side="right", padx=3)
        self.status_label = ttk.Label(actions, text="جاهز")
        self.status_label.pack(side="left")

        log_box = ttk.LabelFrame(self, text="سجل التشغيل", padding=6)
        log_box.pack(fill="both", expand=False, padx=12, pady=(0, 12))
        self.log = tk.Text(log_box, height=10, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def _selected_index(self):
        selected = self.account_tree.selection()
        return int(selected[0]) if selected else None

    def _refresh_accounts(self):
        self.account_tree.delete(*self.account_tree.get_children())
        for index, account in enumerate(self.accounts):
            self.account_tree.insert("", "end", iid=str(index), values=(account["name"], account["username"], len(account["ads"])))
        self._refresh_ads()

    def _refresh_ads(self):
        self.ads_list.delete(0, "end")
        index = self._selected_index()
        if index is not None and index < len(self.accounts):
            for url in self.accounts[index]["ads"]:
                self.ads_list.insert("end", url)

    def _account_dialog(self, title, existing=None):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("430x235")
        dialog.transient(self)
        dialog.grab_set()
        values = existing or {"name": "", "username": "", "password": ""}
        entries = {}
        for row, (key, label) in enumerate((("name", "اسم الحساب"), ("username", "رقم الجوال"), ("password", "كلمة المرور"))):
            ttk.Label(dialog, text=label).grid(row=row, column=1, padx=12, pady=10, sticky="e")
            entry = ttk.Entry(dialog, width=36, justify="right", show="•" if key == "password" else "")
            entry.grid(row=row, column=0, padx=12, pady=10)
            entry.insert(0, values.get(key, ""))
            entries[key] = entry
        show = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="إظهار كلمة المرور", variable=show,
                        command=lambda: entries["password"].configure(show="" if show.get() else "•")).grid(row=3, column=0, sticky="e")
        result = {}
        def save():
            for key, entry in entries.items():
                result[key] = entry.get().strip()
            if not all(result.values()):
                messagebox.showerror("بيانات ناقصة", "أدخل اسم الحساب ورقم الجوال وكلمة المرور", parent=dialog)
                return
            dialog.destroy()
        ttk.Button(dialog, text="حفظ", command=save).grid(row=4, column=0, columnspan=2, pady=12)
        dialog.wait_window()
        return result or None

    def _add_account(self):
        data = self._account_dialog("إضافة حساب")
        if data:
            data["ads"] = []
            self.accounts.append(data)
            self._save_refresh()

    def _edit_account(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("تنبيه", "اختر حسابًا أولًا")
            return
        data = self._account_dialog("تعديل الحساب", self.accounts[index])
        if data:
            data["ads"] = self.accounts[index]["ads"]
            self.accounts[index] = data
            self._save_refresh()

    def _delete_account(self):
        index = self._selected_index()
        if index is not None and messagebox.askyesno("تأكيد الحذف", "حذف الحساب وروابطه؟"):
            self.accounts.pop(index)
            self._save_refresh()

    def _add_ad(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("تنبيه", "اختر حسابًا أولًا")
            return
        url = simpledialog.askstring("إضافة إعلان", "ألصق رابط إعلان حراج:", parent=self)
        if url:
            url = url.strip()
            if not url.startswith("https://haraj.com.sa/"):
                messagebox.showerror("رابط غير صحيح", "يجب أن يكون الرابط من haraj.com.sa")
                return
            if url not in self.accounts[index]["ads"]:
                self.accounts[index]["ads"].append(url)
                self._save_refresh(select=index)

    def _delete_ads(self):
        index = self._selected_index()
        selected = list(self.ads_list.curselection())
        if index is None or not selected:
            return
        for ad_index in reversed(selected):
            self.accounts[index]["ads"].pop(ad_index)
        self._save_refresh(select=index)

    def _save_refresh(self, select=None):
        self.store.save(self.accounts)
        self._refresh_accounts()
        if select is not None and select < len(self.accounts):
            self.account_tree.selection_set(str(select))
            self._refresh_ads()

    def _start_selected(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("تنبيه", "اختر حسابًا أولًا")
            return
        self._run([self.accounts[index]])

    def _start_all(self):
        if not self.accounts:
            messagebox.showinfo("تنبيه", "أضف حسابًا أولًا")
            return
        self._run(self.accounts.copy())

    def _run(self, accounts):
        if self.running:
            return
        empty = [a["name"] for a in accounts if not a["ads"]]
        if empty and not messagebox.askyesno("حسابات بلا إعلانات", "بعض الحسابات لا تحتوي روابط وسيتم تخطيها. هل تريد المتابعة؟"):
            return
        self.running = True
        self.start_all_button.configure(state="disabled")
        self.start_one_button.configure(state="disabled")
        self.status_label.configure(text="جاري التشغيل...")
        headless = self.headless_var.get()
        threading.Thread(target=self._worker, args=(accounts, headless), daemon=True).start()

    def _worker(self, accounts, headless):
        def emit(message): self.events.put(("log", message))
        summary = {"success": 0, "failed": 0}
        for account in accounts:
            if not account["ads"]:
                emit(f"تخطي {account['name']}: لا توجد روابط")
                continue
            emit(f"بدء الحساب: {account['name']}")
            try:
                result = HarajBot(headless=headless, logger=emit).run_account(account)
                summary["success"] += result["success"]
                summary["failed"] += result["failed"]
            except Exception as exc:
                summary["failed"] += len(account["ads"])
                emit(f"فشل الحساب {account['name']}: {exc}")
        self.events.put(("done", summary))

    def _read_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", payload + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "done":
                    self.running = False
                    self.start_all_button.configure(state="normal")
                    self.start_one_button.configure(state="normal")
                    self.status_label.configure(text=f"انتهى: {payload['success']} ناجح، {payload['failed']} فاشل")
                    messagebox.showinfo("اكتمل التحديث", f"نجح: {payload['success']}\nفشل: {payload['failed']}")
        except queue.Empty:
            pass
        self.after(150, self._read_events)


if __name__ == "__main__":
    HarajManagerApp().mainloop()
