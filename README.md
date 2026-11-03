# Supers report

[![tests](https://github.com/lksuey/relatorio-supers/actions/workflows/tests.yml/badge.svg)](https://github.com/lksuey/relatorio-supers/actions/workflows/tests.yml)

A desktop tool in Python that turns proposal export files into reviewable Excel reports. Each client is counted once, using the identity of the client and the status of their most recent proposal.

The code was extracted from an internal tool and sanitized for publication with the employer's authorization. All data in this repository is synthetic.

## The problem

Supervisors received a large proposals export (CSV or Excel) where the same client appears in several rows: a client retries a proposal, or one is cancelled and a new one is submitted. Counting rows overstates everything, and reviewing by hand means hunting for the latest row of each client. The report needs to answer: for each client, where did the latest proposal end up, and which ones need follow-up?

## Technical decisions

- **Group by client id, not by CPF.** The CPF column arrives masked (three leading and two trailing digits visible). Different clients collide on that truncated value, and grouping by it silently merges unrelated people and undercounts. The client id is not masked, so it is the key. A test covers two distinct clients sharing the same masked CPF.
- **Most recent proposal wins.** Date and time columns are combined into one timestamp. If no date in a group can be parsed, the last row in file order is used.
- **Algorithmic CPF validator** (`supers_report/cpf.py`): check digits, repeated-digit rejection, masked-value detection and a generator for synthetic numbers. It is used to build demo data and tested on its own. The report grouping does not rely on it, because real input is masked.
- **Logic separated from the GUI.** `core.py` and `report.py` have no GUI imports, so the rules run under pytest. `gui.py` is a thin customtkinter window.
- **Defensive text handling.** NFKC normalization (not NFKD) so accents stay composed and still match the status table; control characters are stripped.
- **Configuration instead of hardcoded values.** The list of accepted correspondents is a constant to edit. The analyst to supervisor roster is optional and read from the path in `SUPERS_ROSTER_PATH`.

## Run it with the synthetic data

```
python -m venv .venv
.venv\Scripts\activate          # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt

python generate_demo_data.py demo_proposals.csv
python -m supers_report demo_proposals.csv --mode geral --output report.xlsx
python -m supers_report --gui   # desktop window

pytest
python scan_sensitive.py        # sensitive-data scan; must report zero findings
```

Modes: `nao_assinados` (latest status per client), `cancelados` (cancellations by reason) and `geral` (both).

The demo generator uses a fixed seed. CPFs in it are algorithmically valid but fictional, and are written masked like the real export.

## Limitations

- No time savings have been measured, and none are claimed here.
- The Excel writer here is a condensed version of the original workbook layout. It does not reproduce every sheet of the internal tool (for example the per channel cancellation breakdown).
- Column names and status values are in Portuguese because they are the schema of the input export. Report text is partly Portuguese for the same reason.
- The correspondent filter and status labels reflect one internal export format. Another format needs changes in `core.py`.
- The GUI is not covered by automated tests, and the packaging step to build a Windows executable was removed.
- Reading large files loads them fully in memory with pandas.

## Notes

## License

No license file is included. The source is published for portfolio review and no permission to reuse it is granted.

Built with AI assistance; design, domain rules and review by the author.
