"""Configuration, logging and constants. Imports nothing from the package.

The values below are defaults. The backend (gsw.py) overrides them from
the [AI] section of the config file via configureer(). Other modules must
read them as `config.MODEL` (not `from .config import MODEL`), otherwise
they keep the old value.
"""

import logging
import os
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b")

# Context and maximum answer length. The image and OCR text
# cost a lot of tokens; 4096 was too tight and truncated the prompt.
NUM_CTX = 8192
NUM_PREDICT = 800

# Longest side (in pixels) of the image sent to the model.
MAX_AFBEELDING_ZIJDE = 1280

OUTPUT_DIR = Path("test_output")
LOG_DIR = Path("logs")

# Named logger for the whole package (ai_extractor.*). It does not touch
# the root logger, so it does not interfere with the gsw_logger of the
# backend.
LOGGER_NAAM = "ai_extractor"


def stel_logging_in(log_bestand=None, niveau=logging.INFO):
    """
    Send the logs of the ai_extractor package to a file.

    Called by main.py / test_pdf.py (logs/ai_extractor.log) and by the
    backend (<logs_folder>/ai_extractor.log). Calling it again replaces
    the previous file.
    """
    if log_bestand is None:
        log_bestand = LOG_DIR / "ai_extractor.log"

    log_bestand = Path(log_bestand)
    log_bestand.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAAM)
    logger.setLevel(niveau)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(str(log_bestand), encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)

    return logger


def ollama_basis_url():
    """http://host:port of Ollama, derived from OLLAMA_URL."""
    url = OLLAMA_URL.rstrip("/")
    for einde in ("/api/chat", "/api/generate", "/api"):
        if url.endswith(einde):
            return url[: -len(einde)]
    return url


def configureer(model=None, ollama_url=None, num_ctx=None, num_predict=None,
                max_afbeelding_zijde=None):
    """Override settings at runtime (used by the backend)."""
    global MODEL, OLLAMA_URL, NUM_CTX, NUM_PREDICT, MAX_AFBEELDING_ZIJDE

    if model:
        MODEL = model
    if ollama_url:
        url = ollama_url.rstrip("/")
        if not url.endswith("/api/chat"):
            url += "/api/chat"
        OLLAMA_URL = url
    if num_ctx:
        NUM_CTX = int(num_ctx)
    if num_predict:
        NUM_PREDICT = int(num_predict)
    if max_afbeelding_zijde:
        MAX_AFBEELDING_ZIJDE = int(max_afbeelding_zijde)


VERWACHTE_VELDEN = [
    "kandidaten",
    "gekozen_overledene",
    "voornaam",
    "achternaam",
    "geboortedatum",
    "overlijdensdatum",
    "geboorteplaats",
    "overlijdensplaats",
    "overleden",
    "bewijs_overlijden",
    "onzekerheden",
]

PERSOONSVELDEN = [
    "voornaam",
    "achternaam",
    "geboortedatum",
    "overlijdensdatum",
    "geboorteplaats",
    "overlijdensplaats",
]

TUSSENVOEGSELS = {
    "van", "de", "den", "der", "te", "ten", "ter",
    "vande", "vander", "vanden", "du", "le", "la", "het",
}
