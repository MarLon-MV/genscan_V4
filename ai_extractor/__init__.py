"""
ai_extractor: extraction of data from memorial cards.

By keeping the package name the same as the old file,
`from ai_extractor import analyseer_pagina` in main.py keeps working.
The backend (gs_ai_tools.py) uses analyseer_afbeeldingen().
"""

from .config import (  # noqa: F401
    MODEL,
    OUTPUT_DIR,
    PDF_CONTROLE_DIR,
    configureer,
    stel_logging_in,
)
from .ollama_client import controleer_ollama  # noqa: F401
from .pipeline import (  # noqa: F401
    analyseer_afbeelding,
    analyseer_afbeeldingen,
    analyseer_pagina,
    sla_resultaten_op,
)

__all__ = [
    "analyseer_pagina",
    "analyseer_afbeelding",
    "analyseer_afbeeldingen",
    "sla_resultaten_op",
    "controleer_ollama",
    "configureer",
    "stel_logging_in",
    "MODEL",
    "OUTPUT_DIR",
    "PDF_CONTROLE_DIR",
]
