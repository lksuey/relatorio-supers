import random

import pandas as pd
import pytest

from supers_report import core, report
from supers_report.cpf import generate_cpf, is_masked_cpf, is_valid_cpf, mask_cpf, normalize_cpf
from generate_demo_data import HEADER, generate_rows


def make_df(rows):
    cols = ["ID Cliente", "Cliente", "CPF", "Correspondente", "Status Admin.",
            "Solic. Proposta", "Hora Solic. Proposta"]
    return pd.DataFrame(rows, columns=cols)


def test_generated_cpfs_are_valid_and_deterministic():
    a = [generate_cpf(random.Random(1)) for _ in range(3)]
    b = [generate_cpf(random.Random(1)) for _ in range(3)]
    assert a == b
    assert all(is_valid_cpf(c) for c in a)


def test_cpf_rejects_wrong_check_digit_length_and_repeats():
    cpf = generate_cpf(random.Random(7))
    wrong = cpf[:-1] + str((int(cpf[-1]) + 1) % 10)
    assert not is_valid_cpf(wrong)
    assert not is_valid_cpf(cpf[:-1])
    assert not is_valid_cpf("1" * 11)
    assert not is_valid_cpf("")


def test_cpf_accepts_punctuation():
    cpf = generate_cpf(random.Random(3))
    punct = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    assert is_valid_cpf(punct)
    assert normalize_cpf(punct) == cpf


def test_masked_cpf_is_detected_and_not_valid():
    masked = mask_cpf(generate_cpf(random.Random(5)))
    assert is_masked_cpf(masked)
    assert not is_valid_cpf(masked)


def test_groups_by_client_and_uses_most_recent_proposal():
    df = make_df([
        ["C1", "Ana Demo", "123.XXX.XXX-45", "Correspondent A", "pendente", "01/02/2026", "09:00:00"],
        ["C1", "Ana Demo", "123.XXX.XXX-45", "Correspondent A", "pago", "03/02/2026", "08:00:00"],
        ["C1", "Ana Demo", "123.XXX.XXX-45", "Correspondent A", "cancelado", "02/02/2026", "23:59:00"],
    ])
    pivot = core.summarize_status(df)
    assert pivot.to_dict("records") == [{"VALIDAÇÃO": "PAGO", "QTD": 1}]


def test_time_breaks_ties_on_same_day():
    df = make_df([
        ["C1", "Ana Demo", "x", "Correspondent A", "pendente", "01/02/2026", "10:00:00"],
        ["C1", "Ana Demo", "x", "Correspondent A", "banco", "01/02/2026", "10:30"],
    ])
    assert core.summarize_status(df)["VALIDAÇÃO"].tolist() == ["BANCO"]


def test_unparseable_dates_fall_back_to_last_row_in_file_order():
    df = make_df([
        ["C1", "Ana Demo", "x", "Correspondent A", "pendente", "???", ""],
        ["C1", "Ana Demo", "x", "Correspondent A", "liberado", "???", ""],
    ])
    assert core.summarize_status(df)["VALIDAÇÃO"].tolist() == ["LIBERADO"]


def test_distinct_clients_with_same_masked_cpf_are_not_merged():
    same_mask = "281.XXX.XXX-80"
    df = make_df([
        ["C1", "Ana Demo", same_mask, "Correspondent A", "pago", "01/02/2026", "09:00:00"],
        ["C2", "Bia Demo", same_mask, "Correspondent B", "cancelado", "01/02/2026", "09:00:00"],
        ["C3", "Caio Demo", same_mask, "Correspondent C", "pago", "01/02/2026", "09:00:00"],
    ])
    pivot = core.summarize_status(df).set_index("VALIDAÇÃO")["QTD"].to_dict()
    assert pivot == {"PAGO": 2, "CANCELADO": 1}
    assert core.summarize_status(df)["QTD"].sum() == 3


def test_missing_columns_raise_friendly_error():
    with pytest.raises(core.MissingColumnsError) as exc:
        core.summarize_status(pd.DataFrame({"Cliente": ["a"]}))
    assert "ID Cliente" in exc.value.columns


def test_correspondent_filter_keeps_only_configured_keywords():
    df = make_df([
        ["C1", "a", "x", "Correspondent A", "pago", "01/02/2026", ""],
        ["C2", "b", "x", "Someone Else", "pago", "01/02/2026", ""],
    ])
    kept = core.filter_valid_correspondents(df)
    assert kept["ID Cliente"].tolist() == ["C1"]


@pytest.mark.parametrize("raw,expected", [("R$ 1.234,56", 1234.56), ("1,234.56", 1234.56), ("500", 500.0)])
def test_money_parsing(raw, expected):
    assert core.convert_monetary_to_float(raw) == expected


def test_money_parsing_invalid_is_nan():
    assert pd.isna(core.convert_monetary_to_float("abc"))


def test_suffix_singular_plural():
    assert core.get_suffix_for_status("PAGO", 1).endswith("pago")
    assert core.get_suffix_for_status("PAGO", 2).endswith("pagos")


def test_demo_data_is_reproducible_and_has_no_real_looking_cpf():
    assert generate_rows() == generate_rows()
    cpf_col = HEADER.index("CPF")
    assert all(is_masked_cpf(r[cpf_col]) for r in generate_rows())


def test_end_to_end_general_report(tmp_path):
    import csv
    src = tmp_path / "demo.csv"
    with open(src, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(HEADER)
        w.writerows(generate_rows())
    out = tmp_path / "out.xlsx"
    ok, msg = report.run(str(src), str(out), mode="geral", roster={})
    assert ok, msg
    import openpyxl
    wb = openpyxl.load_workbook(out)
    assert {"Não assinados", "Cancelados"} <= set(wb.sheetnames)
    ws = wb["Não assinados"]
    total = ws.cell(row=ws.max_row, column=2).value
    clients = len({r[HEADER.index("ID Cliente")] for r in generate_rows()})
    assert total == clients
