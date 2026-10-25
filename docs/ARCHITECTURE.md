# Architecture

## Overview

```
 scans (divisions/<_slug>/*.pdf|jpg)
          |
          v
   gsw.py  ── loop: prep -> downloads -> uploads ──┐
          |                                        |
          v                                        v
  gs_processor.py                       WordPress REST API
   process_prep      divisions <- WP     /wp/v2/rouwberichten
   process_downloads reviewed posts ->   /wp/v2/media
                     rename + Excel      /custom/v1/system-status
   process_uploads   scan -> post
          |
          |  per document
          v
  render pages / web image / file-name parsing      (gs_image_tools, gs_helpers)
          |
          v
  gs_ai_tools.extract_with_ai ──> ai_extractor ──> RapidOCR + Ollama (qwen2.5vl)
          |                         (replaces Tesseract + regex)
          v
  face, note, gender, priority, upload              (unchanged)
```

## Backend modules (original, `backend/gs_*.py`)

| Module | Role |
|---|---|
| `gsw.py` (project root) | entry point, lock file, main loop |
| `gs_args.py`, `gs_config.py` | CLI arguments and `config` file -> `APP_CONFIG` |
| `gs_processor.py` | the three phases: prep, downloads, uploads |
| `gs_wp_tools.py` | WordPress REST client (auth from `.env`) |
| `gs_image_tools.py`, `gs_ocr_tools.py` | PDF/image handling, Tesseract (legacy path), face detection |
| `gs_helpers.py` | file-name templates, date validation, notes, naming |
| `gs_file_tools.py` | moving/renaming files, folder rules |
| `gs_db_models.py`, `gs_db_tools.py` | SQLite (`GSW_DB`): documents, divisions, templates, first names, cities |
| `gs_xl_tools.py`, `gs_xl_headers.py` | Excel index `_Index_<folder>.xlsx` |
| `gs_classes.py` | `Obituary` data class |

## AI integration

`gs_ai_tools.py` is the only bridge between both worlds.

- `init_ai()` applies `[AI]` settings via `ai_extractor.configureer()` and
  writes `<logs>/ai_extractor.log`.
- `check_ai_service()` checks Ollama and the model once per upload cycle.
- `extract_with_ai(obituary, pil_images, embedded_text)` runs the analysis and
  maps the result onto the `Obituary` (table below). It raises
  `AIServiceError` when Ollama is down (not the document's fault) and any
  other exception when the document itself fails.
- `register_failure()` / `clear_failure()` count failures per document in
  `<logs>/ai_failures.json`; after `max_failures` the file goes to `_failed`.

| AI result | `Obituary` | WordPress `acf` |
|---|---|---|
| voornaam / achternaam | first_name / last_name | voornaam / familienaam |
| geboortedatum (ISO) | birth_year/month/day | geboortedatum{...} |
| overlijdensdatum (ISO) | death_year/month/day | overlijdensdatum{...} |
| geboorteplaats / overlijdensplaats | birth_place / death_place (`clean_city_names`) | geboorteplaats / overlijdensplaats |
| rapidocr_tekst or embedded text | content, ocr_text | content |
| (not AI) | gender, face, note | gender, foto, nota |

## `ai_extractor` package

| Module | Role |
|---|---|
| `pipeline.py` | `analyseer_afbeeldingen()` (backend), `analyseer_pagina()` (`tools/test_pdf.py`) |
| `ocr.py` | PDF render (PyMuPDF), RapidOCR, text crop |
| `ollama_client.py` | chat call, `controleer_ollama()` |
| `prompts.py` | all model prompts |
| `normalisatie.py` | clean and validate the model output |
| `herstel.py` | name splitting, second round, guess round |
| `config.py` | defaults, `configureer()`, named logger `ai_extractor` |

Pipeline per document: OCR every page -> pick the page with most text ->
first analysis (find persons + roles, pick the deceased) -> second round for
missing fields -> guess round (flagged in `gegokt_velden`) -> validation.

## Decisions

- The old flow stays in charge so inputs/outputs are identical by definition.
- Guessed fields are not uploaded by default (WordPress has no review flag).
- An unreachable Ollama stops the *cycle*, not the program.
- `ai_extractor` has no dependency on `gs_*`, so it can be used and tested alone
  (`tools/test_pdf.py`).

## Known differences with the original

- Tesseract is not used when `[AI] enabled = true`.
- Dates from the AI are validated like the old ones; impossible years drop the
  whole date.
- Division/box/document number are read from the path with `/` and `\`
  (the original was Windows-only).
