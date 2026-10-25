"""
Pre-flight check before running gsw.py (plan phase 5.10).

Checks, in this order:
  1. Python version and .env credentials
  2. Ollama answers and the model is installed (only if [AI] enabled)
  3. WordPress /wp-json/custom/v1/system-status answers
     (if not, gsw.py silently skips every document)
  4. The rouwberichten post type exists
  5. The working folder and the database exist

Usage:
    python check_setup.py            # reads ./config and ./.env
    python check_setup.py -c other_config
Exit code 0 = everything OK, 1 = at least one check failed.
"""

import argparse
import configparser
import os
import sys
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

OK, FAIL = "\033[32mOK  \033[0m", "\033[31mFAIL\033[0m"


def report(passed, text):
    print(f"[{OK if passed else FAIL}] {text}")
    return passed


def main():
    parser = argparse.ArgumentParser(description="GenScan pre-flight check")
    parser.add_argument("-c", "--config", default="config")
    args = parser.parse_args()

    load_dotenv(find_dotenv(usecwd=True), override=True)
    results = []

    results.append(
        report(sys.version_info >= (3, 11), f"Python {sys.version.split()[0]} (>= 3.11)")
    )

    config = configparser.ConfigParser()
    if not config.read(args.config, encoding="utf-8"):
        report(False, f"Config file '{args.config}' not found (copy config.default)")
        sys.exit(1)

    site = config.get("WORDPRESS", "site", fallback="").rstrip("/")
    user, password = os.getenv("WP_USER"), os.getenv("WP_API")
    results.append(report(bool(site) and "your_site" not in site, f"[WORDPRESS] site = {site}"))
    results.append(report(bool(user and password), "WP_USER and WP_API in .env"))

    # Ollama
    if config.getboolean("AI", "enabled", fallback=True):
        import ai_extractor

        ai_extractor.configureer(
            model=config.get("AI", "model", fallback=None),
            ollama_url=config.get("AI", "ollama_url", fallback=None),
        )
        ok, message = ai_extractor.controleer_ollama()
        results.append(report(ok, message))
    else:
        print("[skip] AI disabled in config (Tesseract is used)")

    # WordPress
    if site and user and password:
        auth = (user, password)
        for path, label in (
            ("/wp-json/custom/v1/system-status", "system-status endpoint"),
            ("/wp-json/wp/v2/rouwberichten?per_page=1", "rouwberichten post type"),
        ):
            try:
                response = requests.get(site + path, auth=auth, timeout=10)
                results.append(report(response.ok, f"{label}: HTTP {response.status_code}"))
            except requests.RequestException as error:
                results.append(report(False, f"{label}: {error}"))

    # Local files
    folder = Path(config.get("FOLDERS", "working_folder", fallback=""))
    results.append(report(folder.is_dir(), f"working folder {folder}"))
    db = Path(os.getenv("GSW_DB", "gsw.db"))
    results.append(report(db.is_file(), f"database {db}"))
    if db.name == "gsw.db":
        results.append(report(False, "GSW_DB points to gsw.db: use a copy (gsw.local.db)"))

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
