"""Tkinter V2 shell; all heavy work is delegated through services and JobRunner."""

import tkinter as tk
from collections import defaultdict
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any, Callable

from app.models import Account, AccountStatus, Advertisement
from app.services import (
    AccountService,
    GoogleSheetService,
    JobEvent,
    JobEventType,
    JobRunner,
    ProfileResult,
    ProfileService,
    PublishService,
    SettingsService,
    TaskOutcome,
    UpdateService,
)
from app.ui.accounts_tab import AccountsTab
from app.ui.operations_tab import OperationsTab
from app.ui.publish_tab import PublishTab
from app.ui.settings_tab import SettingsTab
from app.ui.update_tab import UpdateTab


@dataclass(frozen=True, slots=True)
class UiServices:
    accounts: AccountService
    profiles: ProfileService
    updates: UpdateService
    sheets: GoogleSheetService
    publishing: PublishService
    settings: SettingsService
    jobs: JobRunner


STATUS_AR = {
    AccountStatus.NEVER_RUN: "لم يعمل بعد",
    AccountStatus.IDLE: "جاهز",
    AccountStatus.RUNNING: "قيد التشغيل",
    AccountStatus.SUCCESS: "نجح",
    AccountStatus.PARTIAL_SUCCESS: "نجاح جزئي",
    AccountStatus.FAILED: "فشل",
    AccountStatus.PAUSED: "متوقف مؤقتًا",
    AccountStatus.SESSION_VALID: "الجلسة صالحة",
    AccountStatus.SESSION_EXPIRED: "الجلسة منتهية",
    AccountStatus.SESSION_REFRESHED: "تم تجديد الجلسة",
    AccountStatus.PROFILE_BUSY: "البروفايل مستخدم",
    AccountStatus.MANUAL_VERIFICATION_REQUIRED: "يتطلب تحققًا يدويًا",
}


class MainWindow(tk.Tk):
    def __init__(self, services: UiServices) -> None:
        super().__init__()
        self.services = services
        self.title("Triple H Manager V2 — مدير إعلانات حراج")
        self.geometry("1220x780")
        self.minsize(980, 650)
        self._session_statuses: dict[str, str] = {}
        self._active_result_handler: Callable[[Any], None] | None = None
        self._close_when_done = False
        self._build_ui()
        self._load_initial_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_job_events)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Triple H Manager V2", font=("Arial", 20, "bold")).pack(side="right")
        ttk.Label(header, text="إدارة الحسابات • تحديث • نشر آمن", foreground="#4b5563").pack(side="left")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.accounts_tab = AccountsTab(
            notebook,
            {
                "add": self._add_account,
                "edit": self._edit_account,
                "delete": self._delete_account,
                "pause": lambda: self._set_paused(True),
                "activate": lambda: self._set_paused(False),
                "check_session": lambda: self._profile_action("فحص الجلسة", "check"),
                "refresh_session": lambda: self._profile_action("تجديد الجلسة", "refresh"),
                "open_profile": lambda: self._profile_action("فتح البروفايل", "open"),
                "add_ad": self._add_ad,
                "delete_ads": self._delete_ads,
                "selection_changed": lambda _account_id: None,
            },
        )
        self.update_tab = UpdateTab(
            notebook,
            {
                "selected": self._update_selected,
                "account": self._update_account,
                "all": self._update_all,
            },
        )
        self.publish_tab = PublishTab(
            notebook,
            {
                "preview": self._preview_sheet,
                "selected": self._publish_selected,
                "account": self._publish_account,
                "all": self._publish_all,
            },
        )
        self.operations_tab = OperationsTab(notebook, self._stop_job)
        self.settings_tab = SettingsTab(
            notebook,
            {"fetch_sheets": self._fetch_sheets, "save": self._save_settings},
        )
        for tab, title in (
            (self.accounts_tab, "الحسابات"),
            (self.update_tab, "تحديث الإعلانات"),
            (self.publish_tab, "نشر الإعلانات"),
            (self.operations_tab, "التشغيل والسجل"),
            (self.settings_tab, "الإعدادات"),
        ):
            notebook.add(tab, text=title)
        self.notebook = notebook

    def _load_initial_state(self) -> None:
        try:
            settings = self.services.settings.load()
            self.settings_tab.set_settings(settings)
            self.update_tab.headless_var.set(settings.headless)
            self.publish_tab.headless_var.set(settings.headless)
            self._refresh_accounts()
        except Exception as exc:
            messagebox.showerror("خطأ في التشغيل", f"تعذر تحميل بيانات V2:\n{exc}", parent=self)

    def _refresh_accounts(self) -> None:
        accounts = self.services.accounts.list_accounts()
        display_sessions = {account_id: value for account_id, value in self._session_statuses.items()}
        self.accounts_tab.set_accounts(accounts, display_sessions)
        self.update_tab.set_accounts(accounts)

    def _selected_account(self) -> Account | None:
        account = self.accounts_tab.selected_account()
        if not account:
            messagebox.showinfo("تنبيه", "اختر حسابًا أولًا", parent=self)
        return account

    def _add_account(self) -> None:
        values = self.accounts_tab.ask_account()
        if not values:
            return
        try:
            self.services.accounts.add_account(**values)
            self._refresh_accounts()
            self.operations_tab.log("تمت إضافة الحساب")
        except Exception as exc:
            self._show_error("تعذر إضافة الحساب", exc)

    def _edit_account(self) -> None:
        account = self._selected_account()
        if not account:
            return
        values = self.accounts_tab.ask_account(account)
        if not values:
            return
        try:
            self.services.accounts.update_account(account.id, **values)
            self._refresh_accounts()
            self.operations_tab.log(f"تم تعديل الحساب: {account.name}")
        except Exception as exc:
            self._show_error("تعذر تعديل الحساب", exc)

    def _delete_account(self) -> None:
        account = self._selected_account()
        if not account:
            return
        if not messagebox.askyesno(
            "تأكيد الحذف",
            "سيُحذف سجل الحساب فقط، ولن يُحذف Chrome profile. هل تريد المتابعة؟",
            parent=self,
        ):
            return
        try:
            self.services.accounts.delete_account(account.id)
            self._refresh_accounts()
            self.operations_tab.log(f"تم حذف سجل الحساب: {account.name}")
        except Exception as exc:
            self._show_error("تعذر حذف الحساب", exc)

    def _set_paused(self, paused: bool) -> None:
        account = self._selected_account()
        if not account:
            return
        try:
            if paused:
                self.services.accounts.pause_account(account.id)
            else:
                self.services.accounts.activate_account(account.id)
            self._refresh_accounts()
        except Exception as exc:
            self._show_error("تعذر تغيير حالة الحساب", exc)

    def _add_ad(self, url: str) -> None:
        account = self._selected_account()
        if not account:
            return
        try:
            self.services.accounts.add_ad_url(account.id, url)
            self._refresh_accounts()
        except Exception as exc:
            self._show_error("تعذر إضافة الرابط", exc)

    def _delete_ads(self, indexes: list[int]) -> None:
        account = self._selected_account()
        if not account:
            return
        try:
            self.services.accounts.remove_ad_indexes(account.id, indexes)
            self._refresh_accounts()
        except Exception as exc:
            self._show_error("تعذر حذف الروابط", exc)

    def _profile_action(self, title: str, action: str) -> None:
        account = self._selected_account()
        if not account:
            return
        settings = self.services.settings.load()

        def worker(account_id: str) -> TaskOutcome:
            current = self.services.accounts.get_account(account_id)
            if action == "check":
                result = self.services.profiles.check_session(current, headless=settings.headless)
            elif action == "refresh":
                result = self.services.profiles.refresh_session(current, headless=settings.headless)
            else:
                result = self.services.profiles.open_profile(current)
            return TaskOutcome(result.success, result, self._profile_message(result))

        self._start_job(title, [account.id], worker, self._handle_profile_result)

    def _update_selected(self) -> None:
        account_id = self.update_tab.selected_account_id()
        urls = self.update_tab.selected_urls()
        if not account_id or not urls:
            messagebox.showinfo("تنبيه", "اختر حسابًا ورابطًا واحدًا على الأقل", parent=self)
            return
        headless = self.update_tab.headless_var.get()
        self._start_job(
            "تحديث الإعلانات المحددة",
            urls,
            lambda url: self._outcome_from_result(
                self.services.updates.update_ad(account_id, url, headless=headless),
                f"تحديث: {url}",
            ),
        )

    def _update_account(self) -> None:
        account_id = self.update_tab.selected_account_id()
        if not account_id:
            messagebox.showinfo("تنبيه", "اختر حسابًا", parent=self)
            return
        headless = self.update_tab.headless_var.get()
        self._start_job(
            "تحديث حساب",
            [account_id],
            lambda item: self._outcome_from_result(
                self.services.updates.update_account(item, headless=headless),
                "تحديث الحساب",
            ),
        )

    def _update_all(self) -> None:
        account_ids = [account.id for account in self.services.accounts.list_accounts()]
        headless = self.update_tab.headless_var.get()
        self._start_job(
            "تحديث جميع الحسابات",
            account_ids,
            lambda item: self._outcome_from_result(
                self.services.updates.update_account(item, headless=headless),
                f"الحساب {item}",
            ),
        )

    def _fetch_sheets(self) -> None:
        url = str(self.settings_tab.values()["spreadsheet_url"])
        if not url:
            messagebox.showerror("رابط ناقص", "أدخل رابط Google Sheet العام", parent=self)
            return
        self._start_job(
            "جلب تبويبات Google Sheets",
            [url],
            lambda value: TaskOutcome(True, self.services.sheets.get_sheet_names(value), "تم جلب التبويبات"),
            lambda names: self.settings_tab.set_sheet_names(names),
        )

    def _save_settings(self) -> None:
        try:
            values = self.settings_tab.values()
            settings = self.services.settings.save(**values)
            self.update_tab.headless_var.set(settings.headless)
            self.publish_tab.headless_var.set(settings.headless)
            self.operations_tab.log("تم حفظ الإعدادات")
        except Exception as exc:
            self._show_error("تعذر حفظ الإعدادات", exc)

    def _preview_sheet(self) -> None:
        settings = self.services.settings.load()
        if not settings.spreadsheet_url or not settings.worksheet:
            messagebox.showerror("إعدادات ناقصة", "احفظ رابط الشيت والتبويب أولًا", parent=self)
            return
        accounts = self.services.accounts.list_accounts()

        def worker(_item: None) -> TaskOutcome:
            result = self.services.sheets.read_worksheet(
                settings.spreadsheet_url,
                settings.worksheet,
                accounts,
            )
            if settings.default_phone:
                for advertisement in result.advertisements:
                    if not advertisement.phone:
                        advertisement.phone = settings.default_phone
            return TaskOutcome(True, result, f"تمت قراءة {len(result.advertisements)} إعلان")

        self._start_job("معاينة إعلانات الشيت", [None], worker, self._handle_sheet_preview)

    def _publish_selected(self) -> None:
        self._start_publish(self.publish_tab.selected_advertisements(), "نشر الإعلانات المحددة")

    def _publish_account(self) -> None:
        selected = self.publish_tab.selected_advertisements()
        if not selected:
            messagebox.showinfo("تنبيه", "اختر إعلانًا لتحديد الحساب", parent=self)
            return
        account_id = selected[0].account_id
        ads = [ad for ad in self.publish_tab.all_advertisements() if ad.account_id == account_id]
        self._start_publish(ads, "نشر إعلانات الحساب")

    def _publish_all(self) -> None:
        self._start_publish(self.publish_tab.all_advertisements(), "نشر جميع الإعلانات")

    def _start_publish(self, advertisements: list[Advertisement], title: str) -> None:
        if not advertisements:
            messagebox.showinfo("تنبيه", "لا توجد إعلانات جاهزة في المعاينة", parent=self)
            return
        grouped: dict[str, list[Advertisement]] = defaultdict(list)
        for advertisement in advertisements:
            grouped[advertisement.account_id].append(advertisement)
        items = list(grouped.items())
        dry_run = self.publish_tab.dry_run_var.get()
        headless = self.publish_tab.headless_var.get()

        def worker(item: tuple[str, list[Advertisement]]) -> TaskOutcome:
            account_id, ads = item
            result = self.services.publishing.publish_account(
                account_id,
                ads,
                headless=headless,
                dry_run=dry_run,
            )
            mode = "Dry Run" if dry_run else "نشر حي"
            return self._outcome_from_result(result, f"{mode}: الحساب {account_id}")

        self._start_job(title, items, worker)

    def _start_job(
        self,
        name: str,
        items: list[Any],
        worker: Callable[[Any], TaskOutcome],
        result_handler: Callable[[Any], None] | None = None,
    ) -> None:
        if not items:
            messagebox.showinfo("تنبيه", "لا توجد عناصر لتنفيذ العملية", parent=self)
            return
        if not self.services.jobs.start(name, items, worker):
            messagebox.showwarning("عملية جارية", "انتظر انتهاء العملية الحالية", parent=self)
            return
        self._active_result_handler = result_handler
        self._set_busy(True)
        self.operations_tab.begin(name)
        self.operations_tab.log(f"بدأت العملية: {name}")

    def _poll_job_events(self) -> None:
        for event in self.services.jobs.poll_events():
            self._handle_job_event(event)
        self.after(100, self._poll_job_events)

    def _handle_job_event(self, event: JobEvent) -> None:
        if event.message:
            self.operations_tab.log(event.message)
        if event.progress:
            self.operations_tab.set_progress(event.progress)
        if event.type is JobEventType.ITEM_RESULT and self._active_result_handler and event.payload is not None:
            try:
                self._active_result_handler(event.payload)
            except Exception as exc:
                self.operations_tab.log(f"تعذر عرض نتيجة الخطوة: {exc}")
        if event.type in {JobEventType.COMPLETED, JobEventType.CANCELLED}:
            self._set_busy(False)
            self.operations_tab.finish(event.message or "انتهت العملية")
            self._active_result_handler = None
            try:
                self._refresh_accounts()
            except Exception as exc:
                self.operations_tab.log(f"تعذر تحديث جدول الحسابات: {exc}")
            if self._close_when_done:
                self._shutdown_now()

    def _stop_job(self) -> None:
        if self.services.jobs.cancel():
            self.operations_tab.log("تم طلب الإيقاف؛ ستتوقف العملية بعد الخطوة الحالية")
            self.operations_tab.stop_button.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self.accounts_tab.set_busy(busy)
        self.update_tab.set_busy(busy)
        self.publish_tab.set_busy(busy)
        self.settings_tab.set_busy(busy)

    def _handle_profile_result(self, result: ProfileResult) -> None:
        self._session_statuses[result.account_id] = STATUS_AR.get(result.status, result.status.value)

    def _handle_sheet_preview(self, result: Any) -> None:
        accounts = {account.id: account.name for account in self.services.accounts.list_accounts()}
        summary = (
            f"جاهز: {len(result.advertisements)} | مكتمل: {result.ignored_completed} | "
            f"مكرر: {result.ignored_processed} | غير مطابق: {result.unmatched_rows}"
        )
        self.publish_tab.set_advertisements(result.advertisements, accounts, summary)

    @staticmethod
    def _profile_message(result: ProfileResult) -> str:
        label = STATUS_AR.get(result.status, result.status.value)
        return f"{label}: الحساب {result.account_id}"

    @staticmethod
    def _outcome_from_result(result: Any, prefix: str) -> TaskOutcome:
        failed = int(getattr(result, "failed", 0))
        succeeded = int(getattr(result, "succeeded", 0))
        return TaskOutcome(
            failed == 0,
            result,
            f"{prefix} — ناجح: {succeeded}، فاشل: {failed}",
        )

    def _show_error(self, title: str, error: Exception) -> None:
        messagebox.showerror(title, f"{title}:\n{error}", parent=self)

    def _on_close(self) -> None:
        if self.services.jobs.running:
            if messagebox.askyesno(
                "عملية جارية",
                "سيتم الإيقاف بأمان بعد الخطوة الحالية ثم إغلاق البرنامج. متابعة؟",
                parent=self,
            ):
                self._close_when_done = True
                self._stop_job()
            return
        self._shutdown_now()

    def _shutdown_now(self) -> None:
        self.services.profiles.close_open_profiles()
        self.destroy()
