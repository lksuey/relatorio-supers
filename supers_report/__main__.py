"""Command line entry point.

    python -m supers_report INPUT.csv|xlsx [--mode nao_assinados|cancelados|geral]
                                           [--output report.xlsx] [--gui]
"""
from __future__ import annotations

import argparse
import sys

from . import report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="supers_report")
    p.add_argument("input", nargs="?", help="proposals export (.csv, .xlsx, .xlsm)")
    p.add_argument("--mode", choices=["nao_assinados", "cancelados", "geral"], default="nao_assinados")
    p.add_argument("--output", default="report.xlsx")
    p.add_argument("--gui", action="store_true", help="open the desktop window (needs customtkinter)")
    args = p.parse_args(argv)
    if args.gui:
        from .gui import main as gui_main
        gui_main()
        return 0
    if not args.input:
        p.error("input is required unless --gui is used")
    ok, msg = report.run(args.input, args.output, mode=args.mode)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
