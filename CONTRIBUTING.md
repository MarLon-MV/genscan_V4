# Contributing

## Set up

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp config.default config && cp .env.example .env && cp gsw.db gsw.local.db
python -m pytest tests
```

Use Python 3.11+. Never point `GSW_DB` at the production `gsw.db` and never
use production WordPress credentials while developing; use the local Docker
site (`http://localhost:8080`) with its own application password.

## Workflow

1. Branch from `integracion-ia` (or `main`): `git switch -c feature/<short-name>`.
2. Keep changes small and focused; one concern per commit.
3. Add or update a test in `tests/` for logic you change (the AI -> `Obituary`
   mapping in `backend/gs_ai_tools.py` is covered by `tests/test_ai_mapping.py`).
4. Run `python -m pytest tests` and `python check_setup.py` before opening a
   pull request.
5. Describe in the PR what changes in the **WordPress output** (post fields,
   file names, Excel columns), if anything. The goal of this project is that
   inputs and outputs stay identical to the original backend.

## Code rules

- The old backend (`gsw.py`, `backend/gs_*.py`) stays in charge of the flow. The AI
  only replaces Tesseract + regex; do not move other logic into
  `ai_extractor/`.
- `ai_extractor/` imports nothing from `gs_*`. The backend talks to it only
  through the functions exported in `ai_extractor/__init__.py`.
- In `ai_extractor`, read settings as `config.MODEL` (not
  `from .config import MODEL`) so `configureer()` overrides work.
- Fill only **empty** fields from the AI (file name has priority). Unknown
  dates are `None`, never `""`; unknown places and names are `""`.
- Use named loggers (`ai_extractor.*`, `gsw_logger`); do not call
  `logging.basicConfig`.
- Match the surrounding style (the `ai_extractor` package uses Dutch names,
  `gs_*` uses English).
- Never commit `.env`, `config`, databases, scans or logs.

## Prompts

Model instructions are in `ai_extractor/prompts.py`. After changing them,
run the fixed test set (the same PDFs every time) through
`tools/test_pdf.py` and compare with the baseline
the Tesseract baseline CSV.
