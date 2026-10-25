"""
Test a single PDF without moving or renaming anything.

Usage:
    python tools/test_pdf.py scan.pdf
The result goes to test_output/resultaat.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf

from ai_extractor import analyseer_pagina, sla_resultaten_op, stel_logging_in


def main():
    if len(sys.argv) < 2:
        print("Gebruik: python test_pdf.py <pad naar pdf>")
        sys.exit(1)

    stel_logging_in()

    with pymupdf.open(sys.argv[1]) as document:
        resultaat = analyseer_pagina(document[0])

    pad = sla_resultaten_op(resultaat)

    for veld in (
        "voornaam", "achternaam", "geboortedatum", "overlijdensdatum",
        "geboorteplaats", "overlijdensplaats", "controle_nodig",
    ):
        print(f"{veld:18}: {resultaat.get(veld)}")

    print(f"\nVolledig resultaat: {pad}")


if __name__ == "__main__":
    main()