"""Generate a fully synthetic proposals export (fixed seed, reproducible).

Every name, phone, CPF and id here is invented. CPFs are algorithmically valid
but FICTIONAL, and are written MASKED like the real export (3 leading and 2
trailing digits), including two different clients that share the same masked
value on purpose.

    python generate_demo_data.py [output.csv]
"""
from __future__ import annotations

import csv
import random
import sys
from datetime import datetime, timedelta

from supers_report.cpf import generate_cpf, mask_cpf

SEED = 20260101
CORRESPONDENTS = ["Correspondent A", "Correspondent B", "Correspondent C"]
ANALYSTS = ["Analyst 01", "Analyst 02", "Analyst 03 LANDING"]
STATUSES = ["assinado", "assinado o primeiro", "cancelado", "pago", "pendente",
            "conferência", "banco", "liberado"]
FIRST = ["Alex", "Bruno", "Carla", "Diana", "Edu", "Fabi", "Gil", "Hana"]
LAST = ["Demo", "Sample", "Test", "Example", "Fictional"]
HEADER = ["N° Proposta", "ID Cliente", "Cliente", "CPF", "Celular", "Correspondente", "Analista",
          "Status Admin.", "Solic. Proposta", "Hora Solic. Proposta", "Val. Solic.",
          "Motivo_Cancelamento"]


def generate_rows(n_clients: int = 40) -> list[list[str]]:
    rng = random.Random(SEED)
    base = datetime(2026, 1, 5, 8, 0)
    rows: list[list[str]] = []
    proposal = 100000
    # Two distinct clients forced to share the same masked CPF.
    shared_mask = mask_cpf(generate_cpf(rng))
    for i in range(n_clients):
        client_id = f"C{1000 + i}"
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)} {i:02d}"
        cpf = shared_mask if i < 2 else mask_cpf(generate_cpf(rng))
        phone = f"55 00 9{rng.randint(10000000, 99999999)}"
        corr = rng.choice(CORRESPONDENTS)
        for _ in range(rng.choice([1, 1, 2, 3])):
            proposal += 1
            when = base + timedelta(minutes=rng.randint(0, 60 * 24 * 3))
            status = rng.choice(STATUSES)
            reason = ""
            if status == "cancelado":
                reason = rng.choice(["#N/D", "CUSTOMER GAVE UP", "AVERBATION FAILURE: CET RATE LIMIT"])
            value = f"R$ {rng.randint(500, 9000):,}".replace(",", ".") + f",{rng.randint(0, 99):02d}"
            rows.append([str(proposal), client_id, name, cpf, phone, corr, rng.choice(ANALYSTS),
                         status, when.strftime("%d/%m/%Y"), when.strftime("%H:%M:%S"), value, reason])
    rng.shuffle(rows)
    return rows


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "demo_proposals.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(HEADER)
        w.writerows(generate_rows())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
