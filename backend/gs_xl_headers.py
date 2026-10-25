"""
Dictionary to holding Excel workbook header configuration

Columns are A, B, C, etc as listed below.
For every column, add one or more of following attributes:
    "header": Cell content
    "note": Note text
    "color": Cell color
    "width": Column width
    "hidden": Visibility of column, True or False

"""

############################
# Standard XL index
############################

headers = [
    {
        "header": "Soort bericht",
        "width": 16,
        "note": """RB = Rouwbrief
OB = Overlijdensbericht
BP = Bidprentje
KB = Krantenbericht
KO = Krantenoverlijdensbericht""",
        "color": "FFD966",
    },
    {"header": "Bestandsnaam", "width": 30, "color": "FFD966"},
    {
        "header": "Voorna(a)m(en) overledene",
        "width": 25,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "FFD966",
    },
    {
        "header": "Achternaam overledene",
        "width": 25,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "FFD966",
    },
    {
        "header": "Geslacht",
        "width": 12,
        "note": "M, V, X of ? Invullen in hoofletter aub",
        "color": "FFD966",
    },
    {
        "header": "Foto",
        "width": 8,
        "note": "x = Foto overledene aanwezig !",
        "color": "FFD966",
    },
    {
        "header": "Geboorte datum",
        "width": 18,
        "color": "FFD966",
    },
    {
        "header": "Geboorte plaats",
        "width": 18,
        "color": "FFD966",
    },
    {
        "header": "Datum overlijden",
        "width": 18,
        "color": "FFD966",
    },
    {
        "header": "Overlijden plaats",
        "width": 18,
        "color": "FFD966",
    },
    {
        "header": "Opmerkingen / extra info",
        "width": 40,
        "color": "FFD966",
    },
    {
        "header": "Persoon leeftijd",
        "width": 20,
        "note": "ouderdom in volle jaren, zonder 'j'",
        "color": "FFD966",
        "hidden": True,
    },
    {
        "header": "Partner_Echtg_Wed",
        "width": 20,
        "note": """E echtgeno(o)t(e)
W weduwe(naar)
L levensgezel(lin)
P partner
V vriend(in)
""",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner_Voornaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner_Achternaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner2_Echtg_Wed",
        "width": 20,
        "note": """E echtgeno(o)t(e)
W weduwe(naar)
L levensgezel(lin)
P partner
V vriend(in)
""",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner2_Voornaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner2_Achternaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner3_Echtg_Wed",
        "width": 20,
        "note": """E echtgeno(o)t(e)
W weduwe(naar)
L levensgezel(lin)
P partner
V vriend(in)
""",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner3_Voornaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Partner3_Achternaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": " GDPR_Info ",
        "width": 20,
        "color": "FFFF00",
        "hidden": True,
    },
    {
        "header": "Vader_voornaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "8EA9DB",
        "hidden": True,
    },
    {
        "header": "Moeder_voornaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "F4B084",
        "hidden": True,
    },
    {
        "header": "Moeder_achternaam",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "F4B084",
        "hidden": True,
    },
    {
        "header": "OS14_18",
        "width": 20,
        "note": "x = aangevinkt = Ja",
        "color": "C6E0B4",
        "hidden": True,
    },
    {
        "header": "OS40_45",
        "width": 20,
        "note": "x = aangevinkt = Ja",
        "color": "C6E0B4",
        "hidden": True,
    },
    {
        "header": "Beroep",
        "width": 20,
        "color": "FFD966",
        "hidden": True,
    },
    {
        "header": "Families",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "FFC000",
        "hidden": True,
    },
    {
        "header": "Persoon info",
        "width": 20,
        "note": "Kleine letters, maar elk woord beginnend met een hoofdletter",
        "color": "FFFF00",
        "hidden": True,
    },
    {
        "header": "Begrafenis datum",
        "width": 20,
        "color": "FFF2CC",
        "hidden": True,
    },
    {
        "header": "Begrafenis plaats",
        "width": 20,
        "color": "FFF2CC",
        "hidden": True,
    },
    {
        "header": "Crematie",
        "width": 20,
        "note": "x = aangevinkt = Ja",
        "color": "FFF2CC",
        "hidden": True,
    },
    {
        "header": "Reeks",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Bidprentje_Rouwbrief",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "dubbel",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "enkel",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Waasland_geb",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Waasland_ovl",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Naam_Indexeerder",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
    {
        "header": "Volgnr2",
        "width": 20,
        "color": "C00000",
        "font_color": "FFFFFF",
        "hidden": True,
    },
]
