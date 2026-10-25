"""Recovery steps: name splitting, OCR recovery, second AI round and guess round."""

import logging
import re

from .config import PERSOONSVELDEN, TUSSENVOEGSELS
from .normalisatie import (
    herstel_tekst_encoding,
    is_lege_waarde,
    normaliseer_resultaat,
    voeg_onzekerheid_toe,
)
from .ollama_client import vraag_ollama
from .prompts import maak_gokprompt, maak_herstelprompt

logger = logging.getLogger(__name__)


def splits_gekozen_naam(resultaat):
    """
    If the model filled in 'gekozen_overledene' but did not split the
    name, try that here. This only happens with a clear pattern:
    first name(s) in normal letters, last name in CAPITALS
    (possibly preceded by a prefix), such as 'Louise Van MIDDELEM'.
    """
    if not isinstance(resultaat, dict):
        return resultaat

    if resultaat.get("voornaam") and resultaat.get("achternaam"):
        return resultaat

    volledig = resultaat.get("gekozen_overledene")
    if not isinstance(volledig, str) or not volledig.strip():
        return resultaat

    woorden = herstel_tekst_encoding(volledig).split()
    if len(woorden) < 2:
        return resultaat

    begin = len(woorden)
    while begin > 0 and woorden[begin - 1].isupper():
        begin -= 1

    # No uppercase words, or everything in uppercase: unclear where
    # the boundary lies, so don't guess.
    if begin == len(woorden) or begin == 0:
        return resultaat

    while begin > 0 and woorden[begin - 1].casefold() in TUSSENVOEGSELS:
        begin -= 1

    if begin == 0:
        return resultaat

    voornaam = " ".join(woorden[:begin])
    achternaam = " ".join(
        w.capitalize() if w.isupper() else w
        for w in woorden[begin:]
    )

    gewijzigd = False

    if is_lege_waarde(resultaat.get("voornaam")):
        resultaat["voornaam"] = voornaam
        gewijzigd = True

    if is_lege_waarde(resultaat.get("achternaam")):
        resultaat["achternaam"] = achternaam
        gewijzigd = True

    if gewijzigd:
        logger.info(
            "Naam gesplitst uit gekozen_overledene: %s | %s",
            voornaam,
            achternaam,
        )
        voeg_onzekerheid_toe(
            resultaat,
            "Voor- en achternaam zijn afgeleid uit "
            f"gekozen_overledene: {volledig}",
        )

    return resultaat


def herstel_naam_via_ocr(resultaat: dict, ocr_tekst: str) -> dict:
    """Fill in a missing first name using explicit OCR evidence."""

    if not isinstance(resultaat, dict):
        return resultaat

    if resultaat.get("voornaam"):
        return resultaat

    achternaam = resultaat.get("achternaam")
    if not isinstance(achternaam, str) or not achternaam.strip():
        return resultaat

    def normaliseer(tekst):
        return " ".join(
            re.findall(r"[^\W\d_]+(?:['’.-][^\W\d_]+)*", tekst.casefold())
        )

    doel = normaliseer(achternaam)
    titels = {
        "de", "heer", "mevrouw", "meneer", "mw", "dhr",
        "juffrouw", "juf", "weduwe", "weduwnaar",
    }

    for regel in ocr_tekst.splitlines():
        regel = regel.strip()

        if not regel or not any(c.isalpha() for c in regel):
            continue

        # Only use lines that are entirely in uppercase.
        letters = [c for c in regel if c.isalpha()]
        if not letters or not all(c.isupper() for c in letters):
            continue

        woorden = re.findall(
            r"[^\W\d_]+(?:['’.-][^\W\d_]+)*",
            regel,
            flags=re.UNICODE,
        )

        # Look for the known last name at the end of the line.
        for begin in range(len(woorden)):
            kandidaat_achternaam = " ".join(woorden[begin:])

            if normaliseer(kandidaat_achternaam) != doel:
                continue

            voornaam_woorden = woorden[:begin]

            while voornaam_woorden and (
                voornaam_woorden[0].casefold() in titels
            ):
                voornaam_woorden = voornaam_woorden[1:]

            if not voornaam_woorden or len(voornaam_woorden) > 4:
                break

            voornaam = " ".join(voornaam_woorden).title()
            resultaat["voornaam"] = voornaam

            onzekerheden = resultaat.get("onzekerheden", [])
            if isinstance(onzekerheden, list):
                resultaat["onzekerheden"] = [
                    melding for melding in onzekerheden
                    if not (
                        isinstance(melding, str)
                        and "voornaam" in melding.casefold()
                    )
                ]

            logger.info(
                "Voornaam hersteld via expliciet OCR-bewijs: %s",
                voornaam,
            )
            return resultaat

    return resultaat


def herstel_ontbrekende_gegevens(
    resultaat,
    ocr_tekst,
    afbeelding_base64=None,
):
    """
    Have the model re-examine missing fields.

    No fixed death-related words or new regex exceptions are
    added. The AI gets the context again.
    """
    ontbrekend = [
        veld
        for veld in PERSOONSVELDEN
        if is_lege_waarde(resultaat.get(veld))
    ]

    if not ontbrekend:
        return resultaat

    logger.info(
        "Tweede AI-analyse voor ontbrekende velden: %s",
        ", ".join(ontbrekend),
    )

    prompt = maak_herstelprompt(resultaat, ocr_tekst)

    try:
        herstel = vraag_ollama(
            prompt=prompt,
            afbeelding_base64=afbeelding_base64,
        )

        herstel = normaliseer_resultaat(herstel)

        # The first analysis is kept for all fields that already had
        # a value. The second analysis only fills in gaps.
        for veld in PERSOONSVELDEN:
            if is_lege_waarde(resultaat.get(veld)):
                nieuwe_waarde = herstel.get(veld)
                if not is_lege_waarde(nieuwe_waarde):
                    resultaat[veld] = nieuwe_waarde

        if is_lege_waarde(resultaat.get("gekozen_overledene")):
            resultaat["gekozen_overledene"] = herstel.get(
                "gekozen_overledene"
            )

        if not resultaat.get("kandidaten"):
            resultaat["kandidaten"] = herstel.get("kandidaten", [])

        if is_lege_waarde(resultaat.get("bewijs_overlijden")):
            bewijs = herstel.get("bewijs_overlijden")
            if not is_lege_waarde(bewijs):
                resultaat["bewijs_overlijden"] = bewijs

        if resultaat.get("overleden") is None:
            resultaat["overleden"] = herstel.get("overleden")

        for onzekerheid in herstel.get("onzekerheden", []):
            voeg_onzekerheid_toe(resultaat, onzekerheid)

    except Exception:
        # The original analysis is preserved.
        logger.exception("Tweede AI-analyse is mislukt.")

        voeg_onzekerheid_toe(
            resultaat,
            "De tweede AI-analyse kon ontbrekende gegevens "
            "niet opnieuw beoordelen.",
        )

    resultaat = splits_gekozen_naam(resultaat)
    resultaat = herstel_naam_via_ocr(resultaat, ocr_tekst)
    return resultaat


def gok_ontbrekende_gegevens(
    resultaat,
    ocr_tekst,
    afbeelding_base64=None,
):
    """
    Final round: fill still-empty person fields with the model's best
    estimate, instead of leaving them empty/unknown.

    Guessed fields are tracked in 'gegokt_velden' and the flag
    'controle_nodig' is set, so main.py can move the PDF to
    pdf_controle/ for manual review.
    """
    resultaat["gegokt_velden"] = []
    resultaat["controle_nodig"] = False

    ontbrekend = [
        veld
        for veld in PERSOONSVELDEN
        if is_lege_waarde(resultaat.get(veld))
    ]

    if not ontbrekend:
        return resultaat

    logger.info(
        "Gokronde voor ontbrekende velden: %s",
        ", ".join(ontbrekend),
    )

    try:
        gok = vraag_ollama(
            prompt=maak_gokprompt(resultaat, ocr_tekst, ontbrekend),
            afbeelding_base64=afbeelding_base64,
        )
        gok = normaliseer_resultaat(gok)
    except Exception:
        logger.exception("Gokronde is mislukt.")
        resultaat["controle_nodig"] = True
        voeg_onzekerheid_toe(
            resultaat,
            "De gokronde is mislukt; handmatige controle nodig.",
        )
        return resultaat

    for veld in ontbrekend:
        waarde = gok.get(veld)
        if not is_lege_waarde(waarde):
            resultaat[veld] = waarde
            resultaat["gegokt_velden"].append(veld)

    if resultaat["gegokt_velden"]:
        voeg_onzekerheid_toe(
            resultaat,
            "Beste inschatting van het model (niet zeker), "
            "handmatig controleren: "
            + ", ".join(resultaat["gegokt_velden"]),
        )

        logger.info(
            "Gegokte velden: %s",
            ", ".join(resultaat["gegokt_velden"]),
        )

    # Anything that was guessed or is still empty must be reviewed.
    resultaat["controle_nodig"] = bool(resultaat["gegokt_velden"]) or any(
        is_lege_waarde(resultaat.get(veld))
        for veld in PERSOONSVELDEN
    )

    return resultaat