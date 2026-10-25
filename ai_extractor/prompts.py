"""All AI prompts. Adjust the instructions for the model here."""

import json

from .config import PERSOONSVELDEN
from .normalisatie import is_lege_waarde

BASISPROMPT = r"""
Je bent een nauwkeurige onderzoeker van historische Belgische
doodsprentjes en overlijdensberichten.

Onderzoek de volledige afbeelding en de meegeleverde OCR-tekst.
Begrijp de betekenis en context van de tekst. Je bent NIET beperkt
tot bepaalde woorden, vaste zinsconstructies of vooraf bepaalde
formuleringen.

DOEL
Bepaal de identiteit van de overledene en extraheer diens gegevens.

WERKWIJZE (volg deze stappen in volgorde)

Stap 1. Zoek ALLE personen die in de tekst genoemd worden en
        geef elk een rol: overledene, echtgenoot, ouder, kind,
        familie, drukker of andere.
Stap 2. Kies de persoon over wie het doodsprentje gaat: de
        persoon voor wie gebeden wordt, die "overleed", "stierf",
        "verscheen voor God", "is ingeslapen" of iets dergelijks.
Stap 3. Bepaal pas daarna de voornaam en achternaam van die
        persoon, en vervolgens de overige gegevens.

BELANGRIJKE REGELS

1. Bepaal eerst wie daadwerkelijk de overledene is.
2. Onderscheid de overledene van echtgenoten, ouders, kinderen,
   andere familieleden, drukkers en begrafenisondernemers.
3. Een naam in hoofdletters kan de naam van de overledene zijn.
   Gebruik de titel, grammaticale context en de rest van de tekst
   om dit te beoordelen.
4. Bepaal geboorte- en overlijdensdatum op basis van hun betekenis
   in de volledige context.
5. Herken ook historische, religieuze, indirecte of ongebruikelijke
   formuleringen voor een overlijden.
6. Verwar een begrafenisdatum, gebedsdienst of herdenkingsdatum
   niet met de overlijdensdatum.
7. Verwar de geboorteplaats niet met de woonplaats, kerk,
   begraafplaats, ziekenhuis of plaats van de begrafenis.
8. Een OCR-regel kan midden in een woord of zin afgebroken zijn.
   Lees de omliggende regels samen.
9. De OCR-tekst kan fouten bevatten. Vergelijk met de afbeelding
   en gebruik de context.
10. Verzin nooit gegevens. Als een gegeven niet voldoende
    onderbouwd is, gebruik null.
11. Als er meerdere mogelijke interpretaties zijn, beschrijf
    de twijfel in onzekerheden.
12. Gebruik datums in YYYY-MM-DD-formaat.
13. Behoud de volledige achternaam, inclusief tussenvoegsels
    zoals "Van", "Van de", "Van den" en "De".
14. Geef uitsluitend één geldig JSON-object terug.
15. Voeg geen Markdown, uitleg buiten de JSON of codeblokken toe.

VEREISTE JSON-STRUCTUUR (houd deze volgorde exact aan)

{
  "kandidaten": [
    {
      "naam": "volledige naam zoals gedrukt",
      "rol": "overledene | echtgenoot | ouder | kind | familie | drukker | andere",
      "reden": "korte reden voor deze rol"
    }
  ],
  "gekozen_overledene": null,
  "voornaam": null,
  "achternaam": null,
  "geboortedatum": null,
  "overlijdensdatum": null,
  "geboorteplaats": null,
  "overlijdensplaats": null,
  "overleden": null,
  "bewijs_overlijden": null,
  "onzekerheden": []
}

Veldbetekenissen:
- kandidaten: alle genoemde personen met hun rol (stap 1).
- gekozen_overledene: de volledige naam van de overledene zoals
  die gedrukt staat (stap 2).
- voornaam: voornaam of voornamen van de overledene, afgeleid
  uit gekozen_overledene.
- achternaam: achternaam van de overledene, afgeleid uit
  gekozen_overledene.
- Bij "Bid God voor de ziel van" volgt vaak de naam van de
  overledene.
- Een naam na "weduwe van", "weduwnaar van" of "echtgenote van"
  behoort aan de partner, niet automatisch aan de persoon over
  wie het doodsprentje gaat.
- Als de eigen volledige naam van de overledene vermeld staat,
  gebruik die naam en niet de achternaam van de partner.
- Behoud alle onderdelen van de eigen achternaam, inclusief
  tussenvoegsels zoals Van, Van de, Van den.
- Voorbeeld (ENKEL ter illustratie, NIET overnemen): bij
  "MEVROUW MARIA VAN DEN BERGE, weduwe van de Heer Jozef PEETERS"
  is de overledene Maria Van den Berge (voornaam "Maria",
  achternaam "Van den Berge") en Jozef Peeters is de echtgenoot.
- geboortedatum: geboortedatum in YYYY-MM-DD.
- overlijdensdatum: datum waarop de persoon overleed.
- geboorteplaats: plaats waar de persoon geboren werd.
- overlijdensplaats: plaats waar de persoon overleed.
- overleden: true wanneer uit de bron blijkt dat het document
  over een overleden persoon gaat; anders null als dit onzeker is.
- bewijs_overlijden: kort letterlijk tekstfragment dat de
  identificatie als overlijdensbericht ondersteunt.
- onzekerheden: lijst met concrete twijfels of ontbrekende
  gegevens.

De afbeelding en OCR-tekst kunnen aanvullende of tegenstrijdige
informatie bevatten. Geef voorrang aan duidelijk leesbare
broninformatie en vermeld onopgeloste tegenstrijdigheden.
"""


def maak_eerste_prompt(ocr_tekst):
    """Build the first full analysis prompt."""
    return (
        BASISPROMPT
        + "\n\nOCR-TEKST VAN DE VOLLEDIGE PAGINA:\n"
        + ocr_tekst
        + "\n\nAnalyseer de overledene en geef het JSON-object."
    )


def maak_herstelprompt(resultaat, ocr_tekst):
    """Build a second prompt for missing data."""
    ontbrekend = [
        veld
        for veld in PERSOONSVELDEN
        if is_lege_waarde(resultaat.get(veld))
    ]

    # The rapidocr fields don't belong in the prompt.
    zonder_ocr = {
        sleutel: waarde
        for sleutel, waarde in resultaat.items()
        if not sleutel.startswith("rapidocr")
    }

    return f"""
{BASISPROMPT}

DIT IS EEN TWEEDE, ONAFHANKELIJKE CONTROLE.

De eerste analyse heeft niet alle gegevens kunnen bepalen.
Onderzoek de bron opnieuw. Probeer de betekenis en context
zelfstandig opnieuw te interpreteren. Doorloop opnieuw stap 1,
2 en 3, en vul "kandidaten" en "gekozen_overledene" opnieuw in.

Velden die nog ontbreken:
{json.dumps(ontbrekend, ensure_ascii=False)}

Resultaat van de eerste analyse:
{json.dumps(zonder_ocr, ensure_ascii=False)}

Volledige OCR-tekst:
{ocr_tekst}

Let vooral op de identiteit van de persoon die centraal staat
in het bericht. Namen van partners en familieleden zijn niet
automatisch de naam van de overledene.

Geef opnieuw uitsluitend het volledige JSON-object terug.
Vul een gegeven alleen in als de bron het ondersteunt.
"""


def maak_gokprompt(resultaat, ocr_tekst, ontbrekend):
    """Build the final prompt: best estimate for empty fields."""
    zonder_ocr = {
        sleutel: waarde
        for sleutel, waarde in resultaat.items()
        if not sleutel.startswith("rapidocr")
        and sleutel not in ("gegokt_velden", "controle_nodig")
    }

    return f"""
{BASISPROMPT}

DIT IS DE LAATSTE RONDE: BESTE INSCHATTING.

Regel 10 (nooit gegevens verzinnen) geldt NIET meer voor de
onderstaande ontbrekende velden. Je hoeft er niet 100% zeker van
te zijn. Geef voor elk ontbrekend veld je meest waarschijnlijke
waarde op basis van de afbeelding, de OCR-tekst en de context.
Gebruik null alleen als er echt niets in de bron naar wijst.
Datums blijven in YYYY-MM-DD-formaat (bij een onbekende dag of
maand: geef je beste schatting en beschrijf de twijfel in
"onzekerheden").

Ontbrekende velden:
{json.dumps(ontbrekend, ensure_ascii=False)}

Resultaat tot nu toe:
{json.dumps(zonder_ocr, ensure_ascii=False)}

Volledige OCR-tekst:
{ocr_tekst}

Let vooral op de identiteit van de persoon die centraal staat
in het bericht. Namen van partners en familieleden zijn niet
automatisch de naam van de overledene.

Geef opnieuw uitsluitend het volledige JSON-object terug.
"""