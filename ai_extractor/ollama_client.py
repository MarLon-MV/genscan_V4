"""Communication with Ollama and parsing of the JSON answer."""

import json
import logging
import re

import requests

from . import config

logger = logging.getLogger(__name__)


def parse_json_antwoord(tekst):
    """Read a JSON object from the Ollama answer."""
    if not isinstance(tekst, str) or not tekst.strip():
        raise ValueError("Ollama gaf een leeg antwoord.")

    tekst = tekst.strip()

    # Strip any Markdown code fences.
    tekst = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        tekst,
        flags=re.IGNORECASE,
    )
    tekst = re.sub(r"\s*```\s*$", "", tekst)

    try:
        data = json.loads(tekst)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Look for a JSON object if the model added extra text anyway.
    begin = tekst.find("{")

    if begin != -1:
        decoder = json.JSONDecoder()

        try:
            data, _ = decoder.raw_decode(tekst[begin:])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError("Ollama gaf geen geldig JSON-object.")


def vraag_ollama(
    prompt,
    afbeelding_base64=None,
    num_predict=None,
    timeout=600,
    pogingen=3,
):
    """Ask Ollama for a JSON object, with diagnostic logging."""

    if num_predict is None:
        num_predict = config.NUM_PREDICT

    bericht = {
        "role": "user",
        "content": prompt,
    }

    if afbeelding_base64:
        bericht["images"] = [afbeelding_base64]

    laatste_fout = None

    for poging in range(pogingen):
        payload = {
            "model": config.MODEL,
            "messages": [bericht],
            "stream": False,
            # No format="json": that caused problems in the earlier
            # image analysis. JSON is requested via the prompt.
            "options": {
                # First attempt is deterministic; on a retry use slight
                # variation, otherwise you get the exact same error.
                "temperature": 0 if poging == 0 else 0.3,
                "num_ctx": config.NUM_CTX,
                "num_predict": num_predict,
                "repeat_penalty": 1.1,
            },
        }

        try:
            antwoord = requests.post(
                config.OLLAMA_URL,
                json=payload,
                timeout=timeout,
            )

            logger.info(
                "Ollama HTTP-status: %s; poging %s/%s",
                antwoord.status_code,
                poging + 1,
                pogingen,
            )

            if not antwoord.ok:
                logger.error(
                    "Ollama HTTP-fout: %s",
                    antwoord.text[:2000],
                )
                antwoord.raise_for_status()

            data = antwoord.json()
            bericht_data = data.get("message") or {}
            inhoud = bericht_data.get("content") or ""

            prompt_tokens = data.get("prompt_eval_count")
            eval_tokens = data.get("eval_count")

            logger.info(
                "Ollama done=%r, done_reason=%r, "
                "prompt_eval_count=%r, eval_count=%r, "
                "inhoud_lengte=%s",
                data.get("done"),
                data.get("done_reason"),
                prompt_tokens,
                eval_tokens,
                len(inhoud),
            )

            # Warnings for the two classic causes of "unknown":
            # truncated prompt and truncated answer.
            if (
                isinstance(prompt_tokens, int)
                and prompt_tokens >= config.NUM_CTX - 50
            ):
                logger.warning(
                    "Prompt zit tegen num_ctx (%s) aan: mogelijk "
                    "afgekapt. Verklein de afbeelding of verhoog "
                    "NUM_CTX.",
                    config.NUM_CTX,
                )

            if data.get("done_reason") == "length":
                logger.warning(
                    "Antwoord afgekapt door num_predict (%s).",
                    num_predict,
                )

            if not inhoud.strip():
                logger.warning(
                    "Lege Ollama-respons: %s",
                    antwoord.text[:2000],
                )
                raise ValueError("Ollama gaf geen tekst terug.")

            return parse_json_antwoord(inhoud)

        except (
            requests.RequestException,
            ValueError,
        ) as fout:
            laatste_fout = fout

            logger.warning(
                "Ollama-poging %s/%s mislukt: %s",
                poging + 1,
                pogingen,
                fout,
            )

    raise RuntimeError(
        f"Ollama gaf na {pogingen} pogingen geen geldig antwoord: "
        f"{laatste_fout}"
    )


def controleer_ollama(timeout=5):
    """
    Check once that Ollama answers and that the model is installed.

    Returns (ok, message). Does not raise.
    """
    url = f"{config.ollama_basis_url()}/api/tags"

    try:
        antwoord = requests.get(url, timeout=timeout)
        antwoord.raise_for_status()
        modellen = antwoord.json().get("models") or []
    except (requests.RequestException, ValueError) as fout:
        return False, f"Ollama antwoordt niet op {url}: {fout}"

    namen = set()
    for item in modellen:
        for sleutel in ("name", "model"):
            naam = item.get(sleutel)
            if naam:
                namen.add(naam)
                namen.add(naam.removesuffix(":latest"))

    if config.MODEL not in namen:
        return False, (
            f"Model {config.MODEL!r} niet gevonden in Ollama. "
            f"Installeer het met: ollama pull {config.MODEL}"
        )

    return True, f"Ollama OK ({config.MODEL})"
