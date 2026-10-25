"""
AI extraction for the GenScan backend.

Replaces only the Tesseract + regex step of the upload flow
(extract_ocr_data, get_name, find_life_info). Everything else (web image,
face, note, gender, division, priority, WordPress upload, downloads, Excel
index, database) stays the old code, so inputs and outputs are the same.

Mapping AI result -> Obituary (-> acf on WordPress):
  voornaam / achternaam   first_name / last_name   voornaam / familienaam
  geboortedatum (ISO)     birth_year/month/day     geboortedatum{...}
  overlijdensdatum (ISO)  death_year/month/day     overlijdensdatum{...}
  geboorteplaats          birth_place              geboorteplaats
  overlijdensplaats       death_place              overlijdensplaats
  RapidOCR / embedded     content + ocr_text       content

Rules (same as the old code):
  - Data from the file name has priority: only EMPTY fields are filled.
  - Dates are checked with validate_year / validate_month / validate_day.
  - Unknown date parts are None, unknown places are "".
"""

import io
import json
import logging
import os
from datetime import date

import ai_extractor
import gs_config
from gs_file_tools import move_file
from gs_helpers import clean_city_names, clean_up_text, join_data, validate_day, \
    validate_month, validate_year

logger = logging.getLogger("gsw_logger")

# Longest side of each page image given to RapidOCR.
MAX_OCR_ZIJDE = 2000


class AIServiceError(RuntimeError):
    """Ollama is not reachable or the model is missing (not the document's fault)."""


def ai_enabled():
    """True if the AI replaces Tesseract (config [AI] enabled)."""
    return bool(gs_config.APP_CONFIG.get("ai_enabled", False))


def init_ai():
    """Apply the [AI] settings and send the AI logs to the logs folder."""
    ai_extractor.configureer(
        model=gs_config.APP_CONFIG.get("ai_model"),
        ollama_url=gs_config.APP_CONFIG.get("ai_ollama_url"),
    )

    level = logging.DEBUG if logger.level == logging.DEBUG else logging.INFO
    ai_extractor.stel_logging_in(
        os.path.join(gs_config.APP_CONFIG["logs_folder"], "ai_extractor.log"),
        level,
    )


def check_ai_service():
    """
    Check once that Ollama answers and the model exists.

    Return:
      (ok, message)
    """
    ok, message = ai_extractor.controleer_ollama()
    if ok:
        logger.info("%s", message)
    else:
        logger.error("%s", message)
    return ok, message


# ------------------------------------------------------------------
# Images
# ------------------------------------------------------------------

def _pil_to_jpeg_bytes(pil_image, max_side=MAX_OCR_ZIJDE):
    """PIL image -> JPEG bytes (RGB, longest side at most max_side)."""
    image = pil_image.convert("RGB")
    width, height = image.size
    scale = max_side / max(width, height)
    if scale < 1:
        image = image.resize((int(width * scale), int(height * scale)))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


# ------------------------------------------------------------------
# Mapping
# ------------------------------------------------------------------

def _is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _split_iso_date(value):
    """'1923-02-06' -> (1923, 2, 6) validated, unknown parts None."""
    if _is_empty(value):
        return None, None, None
    try:
        parsed = date.fromisoformat(str(value).strip())
    except ValueError:
        return None, None, None
    year = validate_year(parsed.year)
    if year is None:
        # An impossible year (e.g. 2099) makes the whole date unreliable.
        return None, None, None
    return year, validate_month(parsed.month), validate_day(parsed.day)


def _fill_date(obituary, prefix, iso_value):
    """Fill <prefix>_year/month/day if they are still empty."""
    year, month, day = _split_iso_date(iso_value)
    for part, value in (("year", year), ("month", month), ("day", day)):
        attribute = f"{prefix}_{part}"
        if _is_empty(getattr(obituary, attribute)):
            # Same as the old find_birth_info/find_death_info:
            # a number, or None when unknown.
            setattr(obituary, attribute, value)


def _fill_place(obituary, attribute, place):
    if not _is_empty(getattr(obituary, attribute)):
        return
    setattr(obituary, attribute, clean_city_names(place) if place else "")


def apply_ai_result(obituary, result, upload_guesses=False):
    """
    Copy the AI result onto the Obituary object.

    Guessed fields (result['gegokt_velden']) are only used when
    upload_guesses is True.
    """
    guessed = set(result.get("gegokt_velden") or [])

    def value(field):
        if field in guessed and not upload_guesses:
            return None
        return result.get(field)

    if _is_empty(obituary.first_name) and not _is_empty(value("voornaam")):
        obituary.first_name = value("voornaam").strip()
        logger.debug("Using first name from AI")
    if _is_empty(obituary.last_name) and not _is_empty(value("achternaam")):
        obituary.last_name = value("achternaam").strip()
        logger.debug("Using last name from AI")

    # Names stay "" when unknown (old get_name also returns strings).
    obituary.first_name = obituary.first_name or ""
    obituary.last_name = obituary.last_name or ""

    _fill_date(obituary, "birth", value("geboortedatum"))
    _fill_date(obituary, "death", value("overlijdensdatum"))
    _fill_place(obituary, "birth_place", value("geboorteplaats"))
    _fill_place(obituary, "death_place", value("overlijdensplaats"))

    return obituary


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def extract_with_ai(obituary, pil_images, embedded_text=None):
    """
    Fill name, dates, places, content and ocr_text of the Obituary with the AI.

    Parameters:
      obituary (Obituary): document being processed
      pil_images (list): page images (PIL) of the original document
      embedded_text (str|None): text embedded in the PDF, if any

    Raises:
      AIServiceError: Ollama is down or the model is missing
      Exception: the document itself could not be analysed

    Return:
      result (dict): the full AI result
    """
    max_pages = max(1, int(gs_config.APP_CONFIG.get("ai_max_pages", 2)))
    pages = [_pil_to_jpeg_bytes(image) for image in pil_images[:max_pages]]

    logger.info("AI analysis of %s (%s page(s))", obituary.file_name, len(pages))

    try:
        result = ai_extractor.analyseer_afbeeldingen(pages)
    except Exception as error:
        ok, message = ai_extractor.controleer_ollama()
        if not ok:
            raise AIServiceError(message) from error
        raise

    # Text for the post (content) and for the note search (ocr_text),
    # embedded text has priority, as in the old code.
    if embedded_text:
        obituary.content = clean_up_text(embedded_text)
    else:
        obituary.content = result.get("rapidocr_tekst") or ""
    obituary.ocr_text = join_data(obituary.content)

    apply_ai_result(
        obituary,
        result,
        upload_guesses=gs_config.APP_CONFIG.get("ai_upload_guesses", False),
    )

    logger.info(
        "AI result: %s, %s | %s %s-%s-%s | %s %s-%s-%s | guessed: %s",
        obituary.last_name,
        obituary.first_name,
        obituary.birth_place,
        obituary.birth_year,
        obituary.birth_month,
        obituary.birth_day,
        obituary.death_place,
        obituary.death_year,
        obituary.death_month,
        obituary.death_day,
        result.get("gegokt_velden"),
    )

    if gs_config.APP_CONFIG.get("ai_save_json", False):
        save_ai_json(obituary, result)

    return result


def save_ai_json(obituary, result):
    """Save the AI result next to the logs: <logs>/ai/<obituary_id>.json."""
    folder = os.path.join(gs_config.APP_CONFIG["logs_folder"], "ai")
    try:
        os.makedirs(folder, exist_ok=True)
        data = dict(result)
        data["bestand"] = obituary.file_path
        data["obituary_id"] = obituary.obituary_id
        path = os.path.join(folder, f"{obituary.obituary_id}.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        logger.debug("AI result saved to %s", path)
    except OSError as error:
        logger.warning("Could not save AI JSON: %s", error)


# ------------------------------------------------------------------
# Failures per document
# ------------------------------------------------------------------

def _failures_path():
    return os.path.join(gs_config.APP_CONFIG["logs_folder"], "ai_failures.json")


def _read_failures():
    try:
        with open(_failures_path(), encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_failures(data):
    try:
        os.makedirs(os.path.dirname(_failures_path()), exist_ok=True)
        with open(_failures_path(), "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except OSError as error:
        logger.warning("Could not save AI failure counter: %s", error)


def clear_failure(file_path):
    """Forget earlier failures of a document that now succeeded."""
    data = _read_failures()
    if data.pop(file_path, None) is not None:
        _write_failures(data)


def register_failure(file_path):
    """
    Count a failed AI analysis of a document. After max_failures attempts
    the document is moved to <its folder>/_failed so it is not retried
    every cycle (_failed is skipped by the backend, like _corrupt).

    Return:
      True if the document was moved to _failed
    """
    data = _read_failures()
    count = int(data.get(file_path, 0)) + 1
    max_failures = int(gs_config.APP_CONFIG.get("ai_max_failures", 3))

    if count < max_failures:
        data[file_path] = count
        _write_failures(data)
        logger.info("AI failure %s/%s for %s", count, max_failures, file_path)
        return False

    parent_folder, file_name = os.path.split(file_path)
    destination = os.path.join(parent_folder, "_failed", file_name)
    moved, _ = move_file(file_path, destination)
    data.pop(file_path, None)
    _write_failures(data)
    logger.error("AI failed %s times, moved to _failed: %s", count, file_path)
    return bool(moved)
