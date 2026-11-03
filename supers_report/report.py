"""Excel output and the three report modes (unsigned, cancelled, general)."""
from __future__ import annotations

import os
import random

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import core

FONT = "Arial"
HEADER_COLORS = ["D1E8FF", "D4F1D9", "FFF5BA", "D5C6E0", "FFE5B4", "C9E4DE",
                 "355070", "3D5A80", "588157", "6A4C93"]
MONEY = "R$ #,##0.00"


def _font_color(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return "FFFFFF" if 0.299 * r + 0.587 * g + 0.114 * b < 140 else "000000"


def _border() -> Border:
    s = Side(style="thin", color="000000")
    return Border(left=s, right=s, top=s, bottom=s)


def _write_table(ws, headers: list[str], rows: list[list], color: str,
                 widths: list[int], money_cols: tuple[int, ...] = ()) -> None:
    fill = PatternFill("solid", fgColor=color)
    font_color = _font_color(color)
    border = _border()
    for c, title in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=title)
        cell.fill, cell.border = fill, border
        cell.font = Font(name=FONT, bold=True, color=font_color)
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            if isinstance(value, float) and pd.isna(value):
                value = None
            cell = ws.cell(row=r, column=c, value=value)
            cell.font, cell.border = Font(name=FONT), border
            if c in money_cols and value is not None:
                cell.number_format = MONEY
                cell.alignment = Alignment(horizontal="right")
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"


def _status_sheet(wb, pivot: pd.DataFrame, color: str, index: int) -> None:
    ws = wb.create_sheet("Não assinados", index)
    rows = [[r["VALIDAÇÃO"], f'{int(r["QTD"])} - {core.get_suffix_for_status(r["VALIDAÇÃO"], int(r["QTD"]))}']
            for _, r in pivot.iterrows()]
    rows.append(["Total Geral", int(pivot["QTD"].sum())])
    _write_table(ws, ["VALIDAÇÃO", "QUANTIDADE"], rows, color, [70, 60])


def _review_sheet(wb, title: str, df: pd.DataFrame, color: str, index: int) -> None:
    ws = wb.create_sheet(title, index)
    headers = list(df.columns)
    _write_table(ws, headers, df.values.tolist(), color,
                 [45, 15, 25, 18, 18, 20, 15, 18], money_cols=(headers.index("VALOR") + 1,))


def _cancelled_sheet(wb, pivot: pd.DataFrame, color: str, index: int) -> None:
    ws = wb.create_sheet("Cancelados", index)
    rows = [[r["MOTIVO_CANCELAMENTO"], int(r["QTD"]), r["VALOR"]] for _, r in pivot.iterrows()]
    rows.append(["Total Geral", int(pivot["QTD"].sum()), float(pivot["VALOR"].sum())])
    _write_table(ws, ["MOTIVO_CANCELAMENTO", "QTD", "VALOR"], rows, color, [70, 8, 18], money_cols=(3,))


def build_workbook(mode: str, df: pd.DataFrame, roster: dict[str, str] | None = None,
                   rng: random.Random | None = None) -> openpyxl.Workbook:
    """Build the workbook for ``mode`` in {"nao_assinados", "cancelados", "geral"}."""
    rng = rng or random.Random()
    c1, c2 = rng.choice(HEADER_COLORS), rng.choice(HEADER_COLORS)
    wb = openpyxl.Workbook()
    del wb["Sheet"]
    if mode in ("nao_assinados", "geral"):
        pivot = core.summarize_status(df)
        if pivot.empty:
            raise ValueError("No clients to report.")
        _status_sheet(wb, pivot, c1, len(wb.sheetnames))
        review = core.build_review_rows(df, roster)
        _review_sheet(wb, "Apuração Não assinados", review, c2, len(wb.sheetnames))
        _review_sheet(wb, "Apuração Parou na bio",
                      review[review["VALIDAÇÃO"] == "PAROU NA BIO"], c2, len(wb.sheetnames))
    if mode in ("cancelados", "geral"):
        cancelled = core.process_cancelled(df)
        if cancelled.empty:
            raise ValueError("No cancelled records.")
        _cancelled_sheet(wb, cancelled, c1, len(wb.sheetnames))
    return wb


def run(input_file: str, output_file: str, mode: str = "nao_assinados",
        roster: dict[str, str] | None = None, progress: core.Progress = None) -> tuple[bool, str]:
    """Returns (ok, output path or friendly error message)."""
    if not os.path.exists(input_file):
        return False, "Input file not found."
    try:
        if progress:
            progress(0.2, "Reading file...")
        df = core.load_dataframe(input_file)
        if progress:
            progress(0.6, "Building report...")
        wb = build_workbook(mode, df, roster if roster is not None else core.load_roster())
        wb.save(output_file)
        if progress:
            progress(1.0, "Report written.")
        return True, output_file
    except core.MissingColumnsError as exc:
        return False, f"The file lacks required columns: {', '.join(exc.columns)}."
    except PermissionError:
        return False, "Could not save the report. Close the output file in Excel and retry."
    except ValueError as exc:
        return False, str(exc)
