"""Cleaning and validating results (no interpretation)."""

from datetime import date

from .config import PERSOONSVELDEN, VERWACHTE_VELDEN


def herstel_tekst_encoding(tekst):
    """Repair broken UTF-8 encoding where possible."""
    if not isinstance(tekst, str):
        return tekst

    try:
        hersteld = tekst.encode("latin1").decode("utf-8")
        if hersteld:
            return hersteld
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return (
        tekst
        .replace("Ã©", "é")
        .replace("Ã¨", "è")
        .replace("Ã«", "ë")
        .replace("Ã¯", "ï")
        .replace("Ã¢", "â")
        .replace("Ã´", "ô")
        .replace("Ã»", "û")
        .replace("Ã ", "à")
    )


def maak_basis_resultaat():
    """Create a result with all expected fields."""
    return {
        "kandidaten": [],
        "gekozen_overledene": None,
        "voornaam": None,
        "achternaam": None,
        "geboortedatum": None,
        "overlijdensdatum": None,
        "geboorteplaats": None,
        "overlijdensplaats": None,
        "overleden": None,
        "bewijs_overlijden": None,
        "onzekerheden": [],
    }


def is_lege_waarde(waarde):
    """Check whether a field is empty."""
    return (
        waarde is None
        or (
            isinstance(waarde, str)
            and not waarde.strip()
        )
    )


def voeg_onzekerheid_toe(resultaat, tekst):
    """Add an uncertainty only once."""
    if not isinstance(resultaat.get("onzekerheden"), list):
        resultaat["onzekerheden"] = []

    if tekst not in resultaat["onzekerheden"]:
        resultaat["onzekerheden"].append(tekst)


def normaliseer_resultaat(resultaat):
    """Normalize the fields and dates of the AI result."""
    if not isinstance(resultaat, dict):
        resultaat = {}

    genormaliseerd = maak_basis_resultaat()

    for veld in VERWACHTE_VELDEN:
        if veld in resultaat:
            genormaliseerd[veld] = resultaat[veld]

    for veld in (
        "voornaam",
        "achternaam",
        "gekozen_overledene",
        "geboorteplaats",
        "overlijdensplaats",
        "bewijs_overlijden",
    ):
        waarde = genormaliseerd[veld]

        if isinstance(waarde, str):
            waarde = herstel_tekst_encoding(waarde).strip()
            genormaliseerd[veld] = waarde or None
        elif waarde is not None:
            # The model returned e.g. a number or list: not usable.
            genormaliseerd[veld] = None

    # Candidates: only keep a list of dicts that have a name.
    kandidaten = genormaliseerd["kandidaten"]
    if not isinstance(kandidaten, list):
        kandidaten = []
    genormaliseerd["kandidaten"] = [
        item for item in kandidaten
        if isinstance(item, dict) and item.get("naam")
    ]

    for veld in ("geboortedatum", "overlijdensdatum"):
        waarde = genormaliseerd[veld]

        if waarde is None or waarde == "":
            genormaliseerd[veld] = None
            continue

        if isinstance(waarde, str):
            try:
                date.fromisoformat(waarde.strip())
                genormaliseerd[veld] = waarde.strip()
            except ValueError:
                genormaliseerd[veld] = None
                voeg_onzekerheid_toe(
                    genormaliseerd,
                    f"{veld} bevat geen geldige ISO-datum: {waarde}",
                )
        else:
            genormaliseerd[veld] = None

    if not isinstance(genormaliseerd["onzekerheden"], list):
        genormaliseerd["onzekerheden"] = []

    if isinstance(genormaliseerd["overleden"], str):
        waarde = genormaliseerd["overleden"].strip().lower()

        if waarde in ("true", "ja", "yes"):
            genormaliseerd["overleden"] = True
        elif waarde in ("false", "nee", "no"):
            genormaliseerd["overleden"] = False
        else:
            genormaliseerd["overleden"] = None

    if not isinstance(genormaliseerd["overleden"], bool):
        genormaliseerd["overleden"] = None

    # Remove duplicate uncertainties.
    genormaliseerd["onzekerheden"] = list(
        dict.fromkeys(
            str(item)
            for item in genormaliseerd["onzekerheden"]
            if item
        )
    )

    return genormaliseerd


def controleer_ontbrekende_velden(resultaat):
    """Flag missing data without making it up."""
    ontbrekend = [
        veld
        for veld in PERSOONSVELDEN
        if is_lege_waarde(resultaat.get(veld))
    ]

    if ontbrekend:
        voeg_onzekerheid_toe(
            resultaat,
            "Gegevens ontbreken of konden niet betrouwbaar "
            "worden vastgesteld: " + ", ".join(ontbrekend),
        )

    return ontbrekend