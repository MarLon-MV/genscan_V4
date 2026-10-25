"""Render a PDF page, run RapidOCR and prepare the image."""

import cv2
import numpy as np
import pymupdf
from rapidocr import RapidOCR

from . import config
from .normalisatie import herstel_tekst_encoding

# RapidOCR is only initialized on first use
# and reused afterwards.
_OCR = None


def _get_ocr():
    global _OCR
    if _OCR is None:
        _OCR = RapidOCR()
    return _OCR


def render_pdf_pagina(pdf_pagina):
    """Convert a PDF page to JPEG bytes."""
    pixmap = pdf_pagina.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False,
    )

    afbeelding_bytes = pixmap.tobytes("png")

    afbeelding = cv2.imdecode(
        np.frombuffer(afbeelding_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if afbeelding is None:
        raise RuntimeError("De PDF-pagina kon niet worden gerenderd.")

    succes, jpeg = cv2.imencode(
        ".jpg",
        afbeelding,
        [cv2.IMWRITE_JPEG_QUALITY, 90],
    )

    if not succes:
        raise RuntimeError("De PDF-afbeelding kon niet worden gecodeerd.")

    return jpeg.tobytes()


def herken_tekst_en_coordinaten(afbeelding_bytes):
    """Recognize text lines and their coordinates with RapidOCR."""
    afbeelding = cv2.imdecode(
        np.frombuffer(afbeelding_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if afbeelding is None:
        raise RuntimeError("RapidOCR kon de afbeelding niet openen.")

    resultaat = _get_ocr()(afbeelding)

    if resultaat is None or resultaat.txts is None:
        return []

    regels = []

    for index, tekst in enumerate(resultaat.txts):
        box = resultaat.boxes[index]

        score = (
            float(resultaat.scores[index])
            if resultaat.scores is not None
            else None
        )

        regels.append({
            "tekst": herstel_tekst_encoding(str(tekst)),
            "coordinaten": [
                [float(punt[0]), float(punt[1])]
                for punt in box
            ],
            "betrouwbaarheid_ocr": score,
        })

    return regels


def maak_tekst_crop(afbeelding_bytes, ocr_regels):
    """
    Create a crop around all text recognized by OCR and
    shrink it so it doesn't cost too many tokens.
    """
    afbeelding = cv2.imdecode(
        np.frombuffer(afbeelding_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if afbeelding is None:
        raise RuntimeError("Afbeelding kon niet worden geopend.")

    crop = afbeelding

    if ocr_regels:
        hoogte, breedte = afbeelding.shape[:2]

        punten = [
            punt
            for regel in ocr_regels
            for punt in regel["coordinaten"]
        ]

        if punten:
            min_x = min(punt[0] for punt in punten)
            min_y = min(punt[1] for punt in punten)
            max_x = max(punt[0] for punt in punten)
            max_y = max(punt[1] for punt in punten)

            marge_x = int(breedte * 0.04)
            marge_y = int(hoogte * 0.04)

            x1 = max(0, int(min_x - marge_x))
            y1 = max(0, int(min_y - marge_y))
            x2 = min(breedte, int(max_x + marge_x))
            y2 = min(hoogte, int(max_y + marge_y))

            uitsnede = afbeelding[y1:y2, x1:x2]

            if uitsnede.size > 0:
                crop = uitsnede

    # Downscale: fewer tokens, faster, and the OCR text already
    # contains the details.
    h, w = crop.shape[:2]
    schaal = config.MAX_AFBEELDING_ZIJDE / max(h, w)

    if schaal < 1:
        crop = cv2.resize(
            crop,
            (int(w * schaal), int(h * schaal)),
            interpolation=cv2.INTER_AREA,
        )

    succes, jpeg = cv2.imencode(
        ".jpg",
        crop,
        [cv2.IMWRITE_JPEG_QUALITY, 80],
    )

    return jpeg.tobytes() if succes else afbeelding_bytes


def maak_ocr_tekst(ocr_regels):
    """Build readable text from the OCR lines."""
    return "\n".join(
        regel["tekst"]
        for regel in ocr_regels
        if regel.get("tekst")
    )