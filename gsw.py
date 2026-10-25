"""
Script to analyze pdf files that contain images of scanned memorial cards or funeral announcements.
"""

import sys
from datetime import datetime
from pathlib import Path
from signal import SIGINT, signal

import colorama
from dotenv import find_dotenv, load_dotenv
from readchar import key, readkey

# The backend modules (gs_*.py) live in backend/
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required (datetime.UTC is used).")

# Load .env BEFORE importing the gs_* modules: gs_db_models reads GSW_DB
# when it is imported. The .env is searched in the current folder (where
# the config file is read too), then in its parent folders.
load_dotenv(find_dotenv(usecwd=True), override=True)

import gs_args  # noqa: E402
import gs_config  # noqa: E402
from gs_ai_tools import ai_enabled, init_ai  # noqa: E402
from gs_db_tools import get_db_session  # noqa: E402
from gs_helpers import countdown, separator_msg  # noqa: E402
from gs_logger import setup_logger  # noqa: E402
from gs_processor import (  # noqa: E402
    process_downloads,
    process_prep,
    process_test,
    process_uploads,
)
from gs_wp_tools import create_web_session  # noqa: E402

# Add some nice colors
colorama.init(wrap=True)

# Define the lock file path relative to the script's directory
LOCK_FILE = Path(__file__).parent / "gsw.lock"


def create_lock_file():
    """
    Add a lock file preventing multiple instances of app running
    """
    if LOCK_FILE.exists():
        print("Script is already running or lock file not cleared properly.")
        print(f"Lock file exists: {LOCK_FILE}")
        sys.exit(1)  # Exit with an error code

    try:
        LOCK_FILE.touch(exist_ok=False)  # Create the lock file
    except Exception as e:
        print(f"Failed to create lock file: {e}")
        sys.exit(1)


def remove_lock_file():
    """
    When app is properly terminated, remove lock file
    """
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()  # Remove the lock file
    except Exception as e:
        print(f"Failed to remove lock file: {e}")


def handler(signum, frame):
    """
    Control-c handler.
    """
    msg = "Ctrl-c was pressed. Do you really want to exit? y/N "
    print(msg, end="", flush=True)
    while True:
        res = readkey()
        if res in ("Y", "y"):
            print("")
            print("Processing interrupted by Ctrl-C")
            remove_lock_file()
            sys.exit(0)
        if res in (key.ENTER, "n", "N"):
            print("", end="\r", flush=True)
            print(" " * len(msg), end="\r", flush=True)
            break


def main():
    """
    This is where the main stuff starts.
    """

    # Generate global from CLI provided arguments, named APP_ARGS (=dictionary)
    gs_args.init()

    # Generate global from config provided arguments, named APP_CONFIG (=dictionary)
    gs_config.init()

    # Set up logger
    logger = setup_logger(
        log_folder=gs_config.APP_CONFIG["logs_folder"],
        log_file="gsw.log",
        log_level=gs_config.APP_CONFIG["loglevel"],
        log_name="gsw_logger",
    )

    # AI settings ([AI] in config) and AI log file
    if ai_enabled():
        init_ai()
        logger.info("AI extraction enabled (model %s)", gs_config.APP_CONFIG["ai_model"])
        print(f"AI-extractie actief (model {gs_config.APP_CONFIG['ai_model']})")
    else:
        logger.info("AI extraction disabled, using Tesseract")
        print("AI-extractie uit: Tesseract wordt gebruikt")

    # Set up database session
    with get_db_session() as db_session:

        # Add timed loop
        while True:
            print(
                f'Checking {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', flush=True
            )

            # Set up requests web session
            web_session = create_web_session()
            if web_session is None:
                print(
                    "\033[31mWP_USER en/of WP_API ontbreken in .env "
                    "(zie .env.example)\033[0m",
                    flush=True,
                )
                logger.error("No WordPress credentials (WP_USER/WP_API)")
                sys.exit(1)

            with web_session:
                # Testing routines
                process_test(web_session, db_session)

                # Pre-processes
                process_prep(web_session, db_session)

                # Downloading results from site to make room
                process_downloads(web_session, db_session)

                # Process the files in working directory for upload
                process_uploads(web_session, db_session)

            if bool(gs_config.APP_CONFIG["run_once"]):
                logger.info("%s", separator_msg("App ran once"))
                break

            print("\033[35mPress ctrl-C to stop processing\033[0m")

            countdown(gs_config.APP_CONFIG["sleep"])
            print("-" * 30, flush=True)

    logger.info("%s", separator_msg("App ended"))


if __name__ == "__main__":
    create_lock_file()  # Prevent multiple instances running
    signal(SIGINT, handler)  # Start the interrupt routine

    try:
        main()
    finally:
        remove_lock_file()  # Ensure lock file is removed even if an error occurs
