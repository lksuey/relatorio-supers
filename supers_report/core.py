"""Processing rules. No GUI imports, so everything here is testable.

Input columns follow the proposals export: "ID Cliente", "Status Admin.",
"Solic. Proposta", "Hora Solic. Proposta", "Correspondente", "Analista",
"Cliente", "Celular", "N° Proposta", "Val. Solic.", "Motivo_Cancelamento".
Column names and status values stay in Portuguese because they are the
schema of the input data.
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime

import pandas as pd

Progress = Callable[[float, str], None] | None

# A row is kept only if its "Correspondente" contains one of these (case
# insensitive). The real list is deployment configuration, not code.
CORRESPONDENT_KEYWORDS: tuple[str, ...] = ("correspondent",)

STATUS_LABEL = {
    "cancelado": "CANCELADO",
    "banco": "BANCO",
    "assinado o primeiro": "PAROU NA BIO",
    "assinado": "ASSINADO",
    "conferência": "CONFERÊNCIA",
    "conferencia": "CONFERÊNCIA",
    "conferência de fraude": "CONF DE FRAUDE",
    "conferencia de fraude": "CONF DE FRAUDE",
    "pago": "PAGO",
    "conferido": "CONFERIDO",
    "pendente regularização": "PENDENTE REGULARIZAÇÃO",
    "liberado": "LIBERADO",
    "pendente": "PENDENTE",
    "pendente antifraude": "PENDENTE ANTIFRAUDE",
    "recompra": "RECOMPRA",
    "reenviando": "REENVIANDO",
    "reliberado": "RELIBERADO",
    "corrigido": "CORRIGIDO",
}

# (needle, singular text, plural text); first match wins, order matters.
_SUFFIXES = [
    ("não redigitou", "Cliente Não Redigitado", "Clientes Não Redigitados"),
    ("pago", "Cliente Redigitado e está pago", "Clientes Redigitados e estão pagos"),
    ("cancelado", "Cliente Redigitado, mas foi cancelado", "Clientes Redigitados, mas foram cancelados"),
    ("conf de fraude", "Cliente Redigitado e está em conferência de fraude",
     "Clientes Redigitados e estão em conferência de fraude"),
    ("conferência", "Cliente Redigitado e está em conferência", "Clientes Redigitados e estão em conferência"),
    ("conferencia", "Cliente Redigitado e está em conferência", "Clientes Redigitados e estão em conferência"),
    ("parou na bio", "Cliente Redigitado e parou na bio", "Clientes Redigitados e pararam na bio"),
    ("conferido", "Cliente Redigitado e foi conferido", "Clientes Redigitados e foram conferidos"),
    ("pendente regulariza", "Cliente Redigitado e está pendente de regularização",
     "Clientes Redigitados e estão pendentes de regularização"),
    ("liberado", "Cliente Redigitado e foi liberado", "Clientes Redigitados e foram liberados"),
    ("assinado", "Cliente Redigitado e foi assinado", "Clientes Redigitados e foram assinados"),
    ("banco", "Cliente Redigitado e foi para banco", "Clientes Redigitados e foram para banco"),
    ("pendente antifraude", "Cliente Redigitado e está em pendência antifraude",
     "Clientes Redigitados e estão em pendência antifraude"),
    ("pendente", "Cliente Redigitado e está pendente", "Clientes Redigitados e estão pendentes"),
    ("recompra", "Cliente Redigitado e está em recompra", "Clientes Redigitados e estão em recompra"),
    ("reenviando", "Cliente Redigitado e está sendo reenviado", "Clientes Redigitados e estão sendo reenviados"),
    ("reliberado", "Cliente Redigitado e foi reliberado", "Clientes Redigitados e foram reliberados"),
    ("corrigido", "Cliente Redigitado e foi corrigido", "Clientes Redigitados e foram corrigidos"),
]

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d")

# A long vendor error text is shortened in the report.
CANCEL_REASON_LONG = ("AVERBATION FAILURE: monthly interest rate is invalid, "
                      "value must be lower than or equal to the CET rate")
CANCEL_REASON_SHORT = "AVERBATION FAILURE: CET RATE LIMIT"


class MissingColumnsError(Exception):
    """The input file lacks columns required for the report."""

    def __init__(self, columns: list[str]):
        self.columns = columns
        super().__init__(f"Missing columns: {', '.join(columns)}")


def clean_text(text: object) -> str:
    """Strip control/invisible characters and normalise. NFKC (not NFKD) so
    accents are recomposed and still match STATUS_LABEL keys."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def convert_monetary_to_float(value: object) -> float:
    """Parse "R$ 1.234,56" or "1,234.56" using the last separator as decimal."""
    if not isinstance(value, str) or not value.strip():
        return float("nan")
    clean = value.replace("R$", "").replace(" ", "").strip()
    if not clean:
        return float("nan")
    idx = max(clean.rfind(","), clean.rfind("."))
    try:
        if idx == -1:
            return float(clean)
        return float(clean[:idx].replace(".", "").replace(",", "") + "." + clean[idx + 1:])
    except ValueError:
        return float("nan")


def get_status_label(status: str) -> str:
    norm = status.strip().lower()
    return STATUS_LABEL.get(norm, norm.upper())


def get_suffix_for_status(status: str, qty: int) -> str:
    lowered = status.lower()
    for needle, singular, plural in _SUFFIXES:
        if needle in lowered:
            return singular if qty == 1 else plural
    return f"Clientes - {status}"


def _find(df: pd.DataFrame, predicate) -> str | None:
    for col in df.columns:
        if predicate(str(col).strip().lower()):
            return col
    return None


def filter_valid_correspondents(df: pd.DataFrame,
                                keywords: tuple[str, ...] | None = None) -> pd.DataFrame:
    col = _find(df, lambda n: n == "correspondente")
    if col is None:
        return df
    pattern = "|".join(re.escape(k) for k in (keywords or CORRESPONDENT_KEYWORDS))
    return df[df[col].astype(str).str.contains(pattern, case=False, na=False, regex=True)]


def load_dataframe(filepath: str) -> pd.DataFrame:
    if os.path.splitext(filepath)[1].lower() == ".csv":
        with open(filepath, encoding="utf-8-sig", errors="replace") as fh:
            first = fh.readline()
        sep = ";" if first.count(";") > first.count(",") else ","
        df = pd.read_csv(filepath, dtype=str, encoding="utf-8-sig", sep=sep, header=0)
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df = pd.read_excel(filepath, dtype=str, engine="openpyxl")
    return filter_valid_correspondents(df).copy()


def find_columns(df: pd.DataFrame) -> tuple[str, str]:
    """Return (client id column, status column).

    Grouping is by "ID Cliente", NOT by CPF. The CPF column arrives masked
    (e.g. "281.XXX.XXX-80", only 5 real digits), so different clients collide
    on the truncated value and a groupby would merge unrelated people and
    undercount the report. The client id is not masked and is the right key.
    """
    id_col = _find(df, lambda n: n == "id cliente")
    status_col = _find(df, lambda n: n.startswith("status admin"))
    missing = []
    if not id_col:
        missing.append("ID Cliente")
    if not status_col:
        missing.append("Status Admin.")
    if missing:
        raise MissingColumnsError(missing)
    return id_col, status_col


def find_datetime_columns(df: pd.DataFrame) -> tuple[str, str]:
    date_col = _find(df, lambda n: n == "solic. proposta")
    time_col = _find(df, lambda n: n == "hora solic. proposta")
    missing = []
    if not date_col:
        missing.append("Solic. Proposta")
    if not time_col:
        missing.append("Hora Solic. Proposta")
    if missing:
        raise MissingColumnsError(missing)
    return date_col, time_col


def parse_proposal_datetime(date_str: object, time_str: object):
    """Combine date and time columns; ``pd.NaT`` if the date is unreadable."""
    if not isinstance(date_str, str) or not date_str.strip():
        return pd.NaT
    date_str = date_str.strip()[:10]
    time_str = time_str.strip() if isinstance(time_str, str) and time_str.strip() else "00:00:00"
    base = None
    for fmt in DATE_FORMATS:
        try:
            base = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    if base is None:
        parsed = pd.to_datetime(date_str, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return pd.NaT
        base = parsed.date()
    clock = datetime.min.time()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            clock = datetime.strptime(time_str, fmt).time()
            break
        except ValueError:
            continue
    return datetime.combine(base, clock)


def pick_most_recent_row(group: pd.DataFrame, date_col: str, time_col: str) -> pd.Series:
    """Latest proposal of one client by date+time; falls back to the last row
    in file order when no date can be parsed."""
    if len(group) == 1:
        return group.iloc[0]
    stamps = group.apply(lambda r: parse_proposal_datetime(r[date_col], r[time_col]), axis=1)
    if stamps.notna().any():
        return group.loc[stamps.idxmax()]
    return group.iloc[-1]


def latest_per_client(df: pd.DataFrame) -> pd.DataFrame:
    """One row per client id: the most recent proposal, with a normalised
    lowercase status in the status column and a ``_key`` column."""
    id_col, status_col = find_columns(df)
    date_col, time_col = find_datetime_columns(df)
    df = df.copy()
    df["_key"] = df[id_col].astype(str).apply(clean_text)
    df = df[df["_key"] != ""]
    df[status_col] = df[status_col].astype(str).apply(clean_text).str.lower()
    rows = [pick_most_recent_row(g, date_col, time_col) for _, g in df.groupby("_key", sort=False)]
    if not rows:
        return df.iloc[0:0]
    out = pd.DataFrame(rows)
    return out[out[status_col] != ""]


def summarize_status(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot of latest status per client: columns VALIDAÇÃO, QTD."""
    latest = latest_per_client(df)
    if latest.empty:
        return pd.DataFrame(columns=["VALIDAÇÃO", "QTD"])
    _, status_col = find_columns(latest)
    labels = latest[status_col].map(get_status_label)
    pivot = labels.value_counts().reset_index()
    pivot.columns = ["VALIDAÇÃO", "QTD"]
    return pivot.sort_values("QTD", ascending=False, kind="stable").reset_index(drop=True)


def process(filepath: str, progress: Progress = None) -> pd.DataFrame:
    if progress:
        progress(0.1, "Reading file...")
    pivot = summarize_status(load_dataframe(filepath))
    if progress:
        progress(0.9, "Done")
    return pivot


def load_roster(path: str | None = None) -> dict[str, str]:
    """Analyst to supervisor map from an optional spreadsheet.

    The path comes from the argument or the SUPERS_ROSTER_PATH environment
    variable; with neither, supervisors stay empty.
    """
    path = path or os.environ.get("SUPERS_ROSTER_PATH")
    if not path or not os.path.exists(path):
        return {}
    try:
        df = pd.read_excel(path, dtype=str, engine="openpyxl")
    except Exception:
        return {}
    df.columns = [str(c).strip().lower() for c in df.columns]
    a = next((c for c in df.columns if "analista" in c), None)
    s = next((c for c in df.columns if "supervisor" in c), None)
    if not a or not s:
        return {}
    df = df.dropna(subset=[a])
    return {str(r[a]).strip(): (str(r[s]).strip() if pd.notna(r[s]) else "")
            for _, r in df.iterrows() if str(r[a]).strip().lower() != "nan"}


def build_review_rows(df: pd.DataFrame, roster: dict[str, str] | None = None) -> pd.DataFrame:
    """Detail rows (latest proposal per client) for manual review."""
    roster = roster or {}
    latest = latest_per_client(df)
    cols = ["VALIDAÇÃO", "N° Proposta", "Cliente", "Celular", "Analista", "Correspondente", "VALOR", "Supervisor"]
    if latest.empty:
        return pd.DataFrame(columns=cols)
    _, status_col = find_columns(latest)

    def pick(*names):
        return _find(latest, lambda n: n in names)

    num, cli, cel = pick("n° proposta", "n proposta", "proposta"), pick("cliente", "nome cliente"), pick("celular")
    ana, cor, val = pick("analista"), pick("correspondente"), pick("val. solic.")
    out = pd.DataFrame({
        "VALIDAÇÃO": latest[status_col].map(get_status_label),
        "N° Proposta": latest[num] if num else "",
        "Cliente": latest[cli] if cli else "",
        "Celular": latest[cel] if cel else "",
        "Analista": latest[ana].fillna("").str.strip() if ana else "",
        "Correspondente": latest[cor] if cor else "",
        "VALOR": latest[val].astype(str).map(convert_monetary_to_float) if val else None,
    })
    out["Supervisor"] = out["Analista"].map(lambda a: roster.get(a, "") if a else "")
    return out[cols].reset_index(drop=True)


def process_cancelled(df: pd.DataFrame) -> pd.DataFrame:
    """Cancelled rows grouped by reason: MOTIVO_CANCELAMENTO, QTD, VALOR."""
    empty = pd.DataFrame(columns=["MOTIVO_CANCELAMENTO", "QTD", "VALOR"])
    status_col = _find(df, lambda n: n.startswith("status admin"))
    reason_col = _find(df, lambda n: n == "motivo_cancelamento")
    value_col = _find(df, lambda n: n == "val. solic.")
    missing = [n for n, c in (("Status Admin.", status_col), ("Motivo_Cancelamento", reason_col)) if not c]
    if missing:
        raise MissingColumnsError(missing)
    df = df.copy()
    df[status_col] = df[status_col].astype(str).apply(clean_text)
    df[reason_col] = df[reason_col].astype(str).apply(clean_text)
    df = df[df[status_col].str.lower() == "cancelado"]
    df = df[(df[reason_col].str.upper() != "#N/D") & (df[reason_col] != "")].copy()
    if df.empty:
        return empty
    df["_valor"] = df[value_col].astype(str).map(convert_monetary_to_float) if value_col else float("nan")
    df[reason_col] = df[reason_col].replace(CANCEL_REASON_LONG, CANCEL_REASON_SHORT)
    return (df.groupby(reason_col, sort=False)
            .agg(QTD=("_valor", "count"), VALOR=("_valor", "sum"))
            .reset_index().rename(columns={reason_col: "MOTIVO_CANCELAMENTO"})
            .sort_values("QTD", ascending=False, kind="stable").reset_index(drop=True))
