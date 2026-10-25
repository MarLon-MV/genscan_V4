"""
genscan2: watches the pdfs/ folder and processes each memorial card.

Per PDF:
  1. analyseer_pagina() extracts the name, dates and places
  2. the JSON goes into resultaten/
  3. the PDF is renamed to
     achternaam_voornaam_geboortedatum_overlijdensdatum.pdf
     and moved to pdf_done/ (or pdf_controle/ if the model had
     to guess or data is missing, or pdf_fout/ on an error)

Usage:
    python main.py              # keeps running and waits for new PDFs
    python main.py --eenmalig   # processes what is in pdfs/ now and stops
"""

import argparse
import json
import re
import shutil
import time
import traceback
from pathlib import Path

import pymupdf

from ai_extractor import PDF_CONTROLE_DIR, analyseer_pagina, stel_logging_in

# ============================================================
# SETTINGS
# ============================================================

INVOER_DIR = Path("pdfs")
KLAAR_DIR = Path("pdf_done")
CONTROLE_DIR = PDF_CONTROLE_DIR          # pdf_controle/
FOUT_DIR = Path("pdf_fout")
RESULTATEN_DIR = Path("resultaten")

# Which page of the PDF is the memorial card (0 = first page).
PAGINA_INDEX = 0

# How often (in seconds) to check for new PDFs.
CONTROLE_INTERVAL = 5


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def veilig_deel(tekst):
    """Make a piece of text safe to use in a file name."""
    if not isinstance(tekst, str) or not tekst.strip():
        return "onbekend"

    tekst = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", tekst)
    tekst = re.sub(r"\s+", "_", tekst.strip())
    tekst = tekst.strip("._")

    return tekst or "onbekend"


def maak_bestandsnaam(resultaat):
    """achternaam_voornaam_geboortedatum_overlijdensdatum (without .pdf)."""
    delen = [
        resultaat.get("achternaam"),
        resultaat.get("voornaam"),
        resultaat.get("geboortedatum"),
        resultaat.get("overlijdensdatum"),
    ]
    return "_".join(veilig_deel(deel) for deel in delen)


def uniek_pad(map_, naam, extensie):
    """Avoid overwriting: add _2, _3, ... if the name already exists."""
    pad = map_ / f"{naam}{extensie}"
    teller = 2

    while pad.exists():
        pad = map_ / f"{naam}_{teller}{extensie}"
        teller += 1

    return pad


def is_stabiel(pad):
    """True if the file size no longer changes (copy finished)."""
    try:
        eerste = pad.stat().st_size
        time.sleep(1)
        return eerste > 0 and eerste == pad.stat().st_size
    except OSError:
        return False


def maak_mappen():
    for map_ in (
        INVOER_DIR, KLAAR_DIR, CONTROLE_DIR, FOUT_DIR, RESULTATEN_DIR,
    ):
        map_.mkdir(parents=True, exist_ok=True)


# ============================================================
# PROCESSING
# ============================================================

def verwerk_pdf(pdf_pad):
    """Process one PDF and move it to the right folder."""
    print(f"\n>> {pdf_pad.name}")

    try:
        with pymupdf.open(pdf_pad) as document:
            if document.page_count == 0:
                raise RuntimeError("De PDF heeft geen pagina's.")

            index = min(PAGINA_INDEX, document.page_count - 1)
            resultaat = analyseer_pagina(document[index])

        # The document is closed now, so moving it works on Windows.
        naam = maak_bestandsnaam(resultaat)
        doelmap = CONTROLE_DIR if resultaat.get("controle_nodig") else KLAAR_DIR

        doelpad = uniek_pad(doelmap, naam, ".pdf")
        json_pad = RESULTATEN_DIR / f"{doelpad.stem}.json"

        json_pad.write_text(
            json.dumps(resultaat, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        shutil.move(str(pdf_pad), str(doelpad))

        status = "CONTROLE NODIG" if doelmap == CONTROLE_DIR else "OK"
        print(f"   {status}: {doelpad}")

        if resultaat.get("onzekerheden"):
            for melding in resultaat["onzekerheden"]:
                print(f"   - {melding}")

    except Exception as fout:
        print(f"   FOUT: {fout}")
        traceback.print_exc()

        try:
            doelpad = uniek_pad(FOUT_DIR, pdf_pad.stem, pdf_pad.suffix)
            shutil.move(str(pdf_pad), str(doelpad))
            print(f"   Verplaatst naar {doelpad}")
        except Exception as verplaats_fout:
            print(f"   Kon PDF niet verplaatsen: {verplaats_fout}")


def verwerk_map():
    """Process all PDFs currently in pdfs/. Returns the count."""
    aantal = 0

    for pdf_pad in sorted(INVOER_DIR.glob("*.pdf")):
        if not is_stabiel(pdf_pad):
            continue

        verwerk_pdf(pdf_pad)
        aantal += 1

    return aantal


def main():
    parser = argparse.ArgumentParser(description="Doodsprentjes extractor")
    parser.add_argument(
        "--eenmalig",
        action="store_true",
        help="verwerk de huidige PDF's en stop (niet blijven wachten)",
    )
    args = parser.parse_args()

    stel_logging_in()
    maak_mappen()

    if args.eenmalig:
        aantal = verwerk_map()
        print(f"\nKlaar: {aantal} PDF('s) verwerkt.")
        return

    print(f"Wacht op PDF's in {INVOER_DIR.resolve()} (Ctrl+C om te stoppen)")

    try:
        while True:
            if verwerk_map() == 0:
                time.sleep(CONTROLE_INTERVAL)
    except KeyboardInterrupt:
        print("\nGestopt.")


if __name__ == "__main__":
    main()