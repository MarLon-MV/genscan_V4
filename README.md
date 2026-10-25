# genscan2

GenScan reads scanned memorial cards and death notices (PDF/JPG), extracts
name, dates and places, uploads them to WordPress as `rouwberichten` posts
and later renames the originals once volunteers have reviewed the posts.

This project is the **original GenScan backend (`gsw.py`) with the AI
extraction plugged in**. The old Tesseract + regex step is replaced by
RapidOCR + a local vision model (Ollama). Everything else (inputs, outputs,
WordPress upload, Excel index, database) is the old code, so the inputs and
outputs are the same. See [docs/GenScan_backend_IO.txt](docs/GenScan_backend_IO.txt).

Everything runs locally; only WordPress receives data.

## Quick start

Requirements: **Python 3.11+**, [Ollama](https://ollama.com), a GPU
(recommended), ~6 GB disk for the model.

```bash
git clone <this repository> && cd genscan2
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

ollama pull qwen2.5vl:3b                               # the model in config

cp config.default config                               # then edit (see below)
cp .env.example .env                                   # then edit (see below)
cp gsw.db gsw.local.db                                 # work on a COPY, never on gsw.db

python check_setup.py                                  # pre-flight check
python gsw.py -w ./werkmap -l DEBUG                    # run
```

1. **`config`**: set `[WORDPRESS] site` and `[FOLDERS] working_folder`
   (absolute path). Local Docker site: `http://localhost:8080`.
2. **`.env`**: `WP_USER`, `WP_API` (a WordPress *application password*;
   for the local site create a local one in wp-admin) and
   `GSW_DB=gsw.local.db`.
3. Put scans in `<working_folder>/divisions/<_slug>/`
   (`.pdf`, `.jpg`, `.jpeg`; folders `_ignore`, `_corrupt`, `_failed` are skipped).
4. Make sure Ollama is running (`ollama serve`).

`gsw.py` is a REST **client**: it opens no port and needs no CORS. It
repeats `prep -> downloads -> uploads` until stopped (`run_once = true` in
`config` runs a single cycle).

### Pre-flight check

`python check_setup.py` verifies Python version, `.env` credentials, Ollama
and model, the `system-status` endpoint, the `rouwberichten` post type, the
working folder and that `GSW_DB` is not the production `gsw.db`. If
`system-status` does not answer, the backend skips **all** documents without
raising an error, so run this first.

## Configuration

`config.default` documents every option. The `[AI]` section:

| Option | Default | Meaning |
|---|---|---|
| `enabled` | `true` | `false` = old Tesseract behaviour |
| `model` | `qwen2.5vl:3b` | Ollama model |
| `ollama_url` | `http://localhost:11434` | Ollama address |
| `max_pages` | `2` | pages analysed per document |
| `upload_guesses` | `false` | upload fields the model had to guess (see below) |
| `save_json` | `true` | full AI result in `<logs>/ai/<id>.json` |
| `max_failures` | `3` | failed analyses before a document goes to `_failed` |

**Guessed fields.** When the model cannot read a field it makes a best
estimate and lists it in `gegokt_velden`. WordPress has no field for "check
this", so by default (`upload_guesses = false`) guesses are *not* uploaded and
the field stays empty for the volunteers, as with the old backend.

**File names.** In the download step reviewed originals are renamed to
`lastname_firstname_birthdate_deathdate.<ext>` (e.g.
`ARDENOIS_Joseph_1923-02-06_2002-11-20.pdf`; unknown parts are `onbekend`).
A division with its own `write` template in the `templates` table keeps using
that template; this format is the default when there is none.

**Ollama down.** Ollama is checked once at the start of every upload cycle.
If it does not answer, that cycle's uploads are skipped and retried next
cycle; documents stay where they are. A document that fails on its own
`max_failures` times is moved to `_failed`.

## How the AI plugs in

Per document, in `gs_processor.process_uploads`:

1. render pages, build web image, parse the file name (unchanged);
2. `gs_ai_tools.extract_with_ai()` replaces Tesseract + `get_name` +
   `find_life_info`; it only fills fields still **empty** after the file
   name, and validates dates with `validate_year/month/day`;
3. face detection, note, gender, upload, downloads, Excel (unchanged).

Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project structure

```
gsw.py                 entry point (prep -> downloads -> uploads loop)
check_setup.py         pre-flight check before running gsw.py
config.default         configuration template   -> copy to `config`
.env.example           credentials template     -> copy to `.env`
requirements*.txt      dependencies (-dev adds pytest)
backend/               the original backend (gs_*.py): WordPress, files, DB, Excel
  gs_ai_tools.py       the bridge to the AI (the only AI-aware backend module)
ai_extractor/          RapidOCR + Ollama extraction (independent of backend/)
tools/test_pdf.py      try the AI on one PDF, no WordPress needed
tests/                 pytest
docs/                  ARCHITECTURE.md, GenScan_backend_IO.txt
```

Runtime folders (`werkmap/`, `logs/`, `*.db`, `.env`, `config`) are created
locally and ignored by git.

## Trying the AI on a single file (development)

```bash
python tools/test_pdf.py scan.pdf     # result in test_output/resultaat.json
```

Handy to tune prompts; not part of the production flow.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests
```

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| All documents skipped, no error | `system-status` endpoint does not answer; run `check_setup.py` |
| `Ollama antwoordt niet` / `Model ... niet gevonden` | start `ollama serve`; `ollama pull <model>` |
| `Script is already running` | stale `gsw.lock`; delete it if no instance runs |
| Application passwords refused over HTTP | local WordPress needs `WP_ENVIRONMENT_TYPE=local` |
| `No module named ...` | venv not active; `python -m pip install -r requirements.txt` |
| Slow (minutes per document) | CPU only; use a GPU or a smaller `max_pages` |

Logs: `<working_folder>/logs/gsw.log` and `ai_extractor.log`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Privacy

Scans and OCR text stay local. `.gitignore` keeps `.env`, `config`, `*.db`,
scan folders, logs and results out of git. Never commit production
credentials.
