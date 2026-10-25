"""Main function per document and storage of results."""

import base64
import json
import logging
from pathlib import Path

from . import config
from .herstel import (
    gok_ontbrekende_gegevens,
    herstel_ontbrekende_gegevens,
    splits_gekozen_naam,
)
from .normalisatie import (
    controleer_ontbrekende_velden,
    normaliseer_resultaat,
)
from .ocr import (
    herken_tekst_en_coordinaten,
    maak_ocr_tekst,
    maak_tekst_crop,
    render_pdf_pagina,
)
from .ollama_client import vraag_ollama
from .prompts import maak_eerste_prompt

logger = logging.getLogger(__name__)


def analyseer_pagina(pdf_pagina):
    """
    Analyze a single PyMuPDF page (used by main.py and test_pdf.py).

    The result contains 'controle_nodig' (bool) and 'gegokt_velden'
    (list). main.py can use these to move the PDF to pdf_controle/.
    """
    return analyseer_afbeeldingen([render_pdf_pagina(pdf_pagina)])


def analyseer_afbeelding(afbeelding_bytes):
    """Analyze one image (JPEG/PNG bytes)."""
    return analyseer_afbeeldingen([afbeelding_bytes])


def analyseer_afbeeldingen(afbeeldingen_bytes):
    """
    Analyze one document that consists of one or more page images
    (JPEG/PNG bytes), e.g. front and back of a memorial card.

    OCR runs on every page and the OCR text of all pages goes to the
    model. The image sent to the model is the page with the most text.
    """
    if not afbeeldingen_bytes:
        raise ValueError("Geen afbeeldingen om te analyseren.")

    logger.info(
        "Analyse gestart (model: %s, %s pagina('s)).",
        config.MODEL,
        len(afbeeldingen_bytes),
    )

    # 1. OCR on every page.
    paginas = []
    for index, afbeelding_bytes in enumerate(afbeeldingen_bytes):
        regels = herken_tekst_en_coordinaten(afbeelding_bytes)
        for regel in regels:
            regel["pagina"] = index
        paginas.append((afbeelding_bytes, regels, maak_ocr_tekst(regels)))
        logger.info(
            "RapidOCR herkende %s tekstregels op pagina %s.",
            len(regels),
            index + 1,
        )

    ocr_tekst = "\n\n".join(tekst for _, _, tekst in paginas if tekst)
    ocr_regels = [regel for _, regels, _ in paginas for regel in regels]

    # 2. The page with the most text is shown to the model.
    hoofd_bytes, hoofd_regels, _ = max(paginas, key=lambda p: len(p[2]))

    # 3. Make the crop, downscale it and convert to base64.
    crop_bytes = maak_tekst_crop(hoofd_bytes, hoofd_regels)
    afbeelding_base64 = base64.b64encode(crop_bytes).decode("ascii")

    # 4. First AI analysis.
    eerste_prompt = maak_eerste_prompt(ocr_tekst)

    try:
        ai_resultaat = vraag_ollama(
            prompt=eerste_prompt,
            afbeelding_base64=afbeelding_base64,
        )
    except Exception as fout:
        logger.exception("Eerste AI-analyse is mislukt.")

        # A technical error is not presented as a successful
        # extraction.
        raise RuntimeError(
            "De eerste AI-analyse is mislukt. "
            "Er is geen betrouwbaar resultaat voor dit document."
        ) from fout

    resultaat = normaliseer_resultaat(ai_resultaat)

    # In case the model chose the name but did not split it.
    resultaat = splits_gekozen_naam(resultaat)

    # 5. Second AI analysis for missing fields.
    resultaat = herstel_ontbrekende_gegevens(
        resultaat=resultaat,
        ocr_tekst=ocr_tekst,
        afbeelding_base64=afbeelding_base64,
    )

    # 6. Final normalization.
    resultaat = normaliseer_resultaat(resultaat)

    # 6b. Guess round: still make a best estimate for empty fields.
    # This must come AFTER normaliseer_resultaat, because that function
    # removes unknown keys such as 'gegokt_velden' and 'controle_nodig'.
    resultaat = gok_ontbrekende_gegevens(
        resultaat,
        ocr_tekst,
        afbeelding_base64,
    )

    # 6c. Validation.
    ontbrekend = controleer_ontbrekende_velden(resultaat)

    if ontbrekend:
        logger.warning(
            "Analyse onvolledig. Ontbrekend: %s",
            ", ".join(ontbrekend),
        )
        resultaat["controle_nodig"] = True
    else:
        logger.info("Alle verplichte persoonsvelden zijn ingevuld.")

    if resultaat.get("controle_nodig"):
        logger.info("Dit document moet handmatig gecontroleerd worden.")

    # 7. Keep the OCR evidence for later review.
    resultaat["rapidocr_tekst"] = ocr_tekst
    resultaat["rapidocr_regels"] = ocr_regels

    logger.info("Analyse afgerond.")

    return resultaat


def sla_resultaten_op(resultaten, uitvoerbestand=None):
    """
    Save results as UTF-8 JSON.

    Pass a path or use the default test_output/resultaat.json.
    """
    if uitvoerbestand is None:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        uitvoerbestand = config.OUTPUT_DIR / "resultaat.json"
    else:
        uitvoerbestand = Path(uitvoerbestand)
        uitvoerbestand.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    with uitvoerbestand.open(
        "w",
        encoding="utf-8",
    ) as bestand:
        json.dump(
            resultaten,
            bestand,
            ensure_ascii=False,
            indent=2,
        )

    logger.info(
        "Resultaten opgeslagen in %s",
        uitvoerbestand.resolve(),
    )

    return uitvoerbestand
