"""Live job log, progress, counters, and safe stop control."""

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from app.services.job_runner import JobProgress


class OperationsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, stop_callback) -> None:
        super().__init__(parent, padding=12)
        status = ttk.Frame(self)
        status.pack(fill="x")
        self.status_label = ttk.Label(status, text="جاهز", font=("Arial", 11, "bold"))
        self.status_label.pack(side="right")
        self.stop_button = ttk.Button(status, text="إيقاف بعد الخطوة الحالية", command=stop_callback, state="disabled")
        self.stop_button.pack(side="left")

        self.progress = ttk.Progressbar(self, maximum=100, mode="determinate")
        self.progress.pack(fill="x", pady=10)
        counters = ttk.Frame(self)
        counters.pack(fill="x")
        self.success_label = ttk.Label(counters, text="الناجح: 0")
        self.failed_label = ttk.Label(counters, text="الفاشل: 0")
        self.remaining_label = ttk.Label(counters, text="المتبقي: 0")
        self.percent_label = ttk.Label(counters, text="0%")
        for label in (self.success_label, self.failed_label, self.remaining_label, self.percent_label):
            label.pack(side="right", padx=14)

        log_box = ttk.LabelFrame(self, text="سجل التشغيل المباشر", padding=6)
        log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.log_widget = tk.Text(log_box, state="disabled", wrap="word", font=("Menlo", 10))
        scrollbar = ttk.Scrollbar(log_box, orient="vertical", command=self.log_widget.yview)
        self.log_widget.configure(yscrollcommand=scrollbar.set)
        self.log_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def begin(self, name: str) -> None:
        self.status_label.configure(text=f"قيد التشغيل: {name}")
        self.stop_button.configure(state="normal")
        self.set_progress(JobProgress(0, 0, 0, 0))

    def finish(self, message: str) -> None:
        self.status_label.configure(text=message)
        self.stop_button.configure(state="disabled")

    def set_progress(self, progress: JobProgress) -> None:
        self.progress.configure(value=progress.percent)
        self.success_label.configure(text=f"الناجح: {progress.succeeded}")
        self.failed_label.configure(text=f"الفاشل: {progress.failed}")
        self.remaining_label.configure(text=f"المتبقي: {progress.remaining}")
        self.percent_label.configure(text=f"{progress.percent:.0f}%")

    def log(self, message: str) -> None:
        if not message:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", f"[{timestamp}] {message}\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

