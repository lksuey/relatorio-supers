"""Minimal desktop window (customtkinter). Not covered by automated tests."""
from __future__ import annotations

import os
import threading
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from . import report

MODES = [("Unsigned", "nao_assinados"), ("Cancelled", "cancelados"), ("General", "geral")]


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Supers report")
        self.resizable(False, False)
        self._path = ""
        self._mode = ctk.StringVar(value=MODES[0][1])
        for label, key in MODES:
            ctk.CTkRadioButton(self, text=label, variable=self._mode, value=key).pack(anchor="w", padx=24, pady=4)
        ctk.CTkButton(self, text="Select file", command=self._pick).pack(padx=24, pady=8, fill="x")
        self._status = ctk.CTkLabel(self, text="No file selected")
        self._status.pack(padx=24)
        self._run_btn = ctk.CTkButton(self, text="Generate report", command=self._start, state="disabled")
        self._run_btn.pack(padx=24, pady=16, fill="x")

    def _pick(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Supported", "*.csv *.xlsx *.xlsm")])
        if path:
            self._path = path
            self._status.configure(text=os.path.basename(path))
            self._run_btn.configure(state="normal")

    def _start(self) -> None:
        self._run_btn.configure(state="disabled")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        out = os.path.join(os.path.dirname(self._path), f"report_{self._mode.get()}_{stamp}.xlsx")
        ok, msg = report.run(self._path, out, mode=self._mode.get())
        self.after(0, lambda: (self._status.configure(text=msg), self._run_btn.configure(state="normal")))


def main() -> None:
    App().mainloop()
