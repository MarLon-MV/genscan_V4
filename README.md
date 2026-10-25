# GenScan

GenScan reads scanned memorial cards and death notices, extracts who the
deceased is (name, birth and death dates and places), and publishes the result
to WordPress for volunteers to review.

It is the original GenScan backend with one change: the old Tesseract + regex
text recognition is replaced by **RapidOCR + a local vision model (Ollama)**.
Everything else (WordPress upload, file renaming, Excel index, database) is the
old code, so inputs and outputs stay the same. Everything runs on your own
machine; only WordPress receives data.

## What it does

```text
scans in divisions/<_slug>/        1. UPLOAD     read the scan with the AI,
  (.pdf .jpg .jpeg)          ───►                 create a post in WordPress
                                                        │
                                                        ▼
                                                 volunteers review the post
                                                 and mark it "Verwerkt"
                                                        │
renamed/<type>/<new name>    ◄───  2. DOWNLOAD   fetch reviewed posts, rename the
Excel index, database                             original, update the Excel index
```

`gsw.py` repeats `prep → downloads → uploads` in a loop. `prep` first syncs the
divisions from WordPress and creates their folders.

A reviewed original is renamed to
`lastname_firstname_birthdate_deathdate.<ext>`, e.g.
`ARDENOIS_Joseph_1923-02-06_2002-11-20.pdf` (unknown parts are `onbekend`). A
division with its own `write` template in the database keeps using it.

## Requirements

- Python **3.11 or newer**
- [Ollama](https://ollama.com), installed and running
- A WordPress site with the `rouwberichten` post type and the
  `/wp-json/custom/v1/system-status` endpoint (or the local Docker copy)
- A GPU is strongly recommended. On CPU a document takes several minutes.
- About 6 GB of disk for the model

## Setup

### 1. Install

```bash
git clone <this repository> && cd genscan2
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
ollama pull qwen2.5vl:3b
```

### 2. Create your local settings

Both files are ignored by git.

```bash
cp config.default config
cp .env.example .env
cp gsw.db gsw.local.db               # always work on a copy of the database
```

### 3. Fill them in

| File | Setting | Value |
|---|---|---|
| `config` | `[WORDPRESS] site` | your site, e.g. `http://localhost:8080` |
| `config` | `[FOLDERS] working_folder` | absolute path to a work folder, e.g. `./werkmap` |
| `.env` | `WP_USER` | WordPress API user |
| `.env` | `WP_API` | a WordPress **application password** (24 characters, not the login password) |
| `.env` | `GSW_DB` | `gsw.local.db` |

### 4. Check everything before the first run

```bash
python check_setup.py
```

It verifies Python, credentials, Ollama and the model, the WordPress endpoints,
the work folder, and that you are not pointing at the production `gsw.db`. Fix
every `FAIL` first: if the `system-status` endpoint does not answer, the backend
silently skips all documents.

## Run

1. Start Ollama (`ollama serve`, or open the Ollama app).
2. Put scans in `<working_folder>/divisions/<_slug>/`. Run once first so `prep`
   creates the division folders.
3. Start:

```bash
python gsw.py -w ./werkmap -l DEBUG
```

Stop with `Ctrl+C`. With `run_once = true` in `config` it runs a single cycle.

Logs: `<working_folder>/logs/gsw.log` and `ai_extractor.log`. The full AI result
per document is in `<working_folder>/logs/ai/<id>.json`.

## Configuration

`config.default` documents every option. The ones for the AI are in `[AI]`:

| Option | Default | Meaning |
|---|---|---|
| `enabled` | `true` | `false` goes back to the old Tesseract behaviour |
| `model` | `qwen2.5vl:3b` | Ollama model |
| `ollama_url` | `http://localhost:11434` | where Ollama listens |
| `max_pages` | `2` | pages analysed per document |
| `upload_guesses` | `false` | upload fields the model had to guess |
| `save_json` | `true` | keep the full AI result per document |
| `max_failures` | `3` | failed analyses before a document is moved to `_failed` |

Behaviour worth knowing:

- **Guesses.** When the model cannot read a field it makes a best estimate. By
  default these are *not* uploaded (WordPress has no "check this" flag), so the
  field stays empty for the volunteers, as with the old backend.
- **File name first.** Data found in the file name wins; the AI only fills
  fields that are still empty. Dates are validated, so an impossible year never
  reaches WordPress.
- **Ollama down.** Checked at the start of every upload cycle. If it does not
  answer, uploads wait for the next cycle and no document is touched.
- **Failing document.** After `max_failures` failed analyses it is moved to
  `_failed`, which the backend skips.
- The folders `_ignore`, `_corrupt` and `_failed` inside a division are skipped.

## Project layout

```text
gsw.py              entry point
check_setup.py      pre-flight check
config.default      settings template      (copy to config)
.env.example        credentials template   (copy to .env)
backend/            the original backend (gs_*.py): WordPress, files, database, Excel
ai_extractor/       the AI: RapidOCR + Ollama
tools/test_pdf.py   try the AI on one PDF, no WordPress needed
tests/              automated tests
docs/               architecture and input/output reference
```

How the pieces fit together is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md);
the exact inputs and outputs of the backend in
[docs/GenScan_backend_IO.txt](docs/GenScan_backend_IO.txt).

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests                 # automated tests
python tools/test_pdf.py scan.pdf      # AI on one file → test_output/resultaat.json
```

Model instructions live in `ai_extractor/prompts.py`. To contribute, read
[CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| Every document is skipped, no error | the `system-status` endpoint does not answer; run `check_setup.py` |
| HTTP 401 from WordPress | `WP_API` is not an application password, or the local site needs `WP_ENVIRONMENT_TYPE` set to `local` |
| `Ollama antwoordt niet` | Ollama is not running: `ollama serve` |
| `Model ... niet gevonden` | `ollama pull <model>` |
| `Script is already running` | leftover `gsw.lock`; delete it if no other instance runs |
| `No module named ...` | the venv is not active, or run `python -m pip install -r requirements.txt` |
| A document takes minutes | normal on CPU; use a GPU or lower `max_pages` |

## Privacy

Scans and recognised text stay on your machine. `.gitignore` keeps `.env`,
`config`, databases, the work folder and logs out of git. Never commit
production credentials, and never run local tests against the production
database or site.
