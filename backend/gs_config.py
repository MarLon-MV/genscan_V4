"""
Creating a global variable for config arguments that can be made available across modules
"""

import logging
import os
import sys
from configparser import ConfigParser

import gs_args

# Activate logger
logger = logging.getLogger("gsw_logger")

APP_CONFIG = {}


def init(file="config"):
    """
    Initializing the global dictionary for the config arguments
    """
    global APP_CONFIG
    APP_CONFIG = read_config(file)


def read_config(file="config"):
    """
    Read the config file and place data in a dictionary.

    Parameters:
      file (string): Path to config file. Default config in working working_folder

    Return:
      APP_CONFIG (dictionary)
    """
    # Default app configuration settings
    # [WORDPRESS]
    APP_CONFIG["wp_site"] = ""
    APP_CONFIG["wp_max_disk_used"] = 50000
    APP_CONFIG["wp_max_db_used"] = 400
    APP_CONFIG["wp_max_uploads"] = 20
    APP_CONFIG["division"] = "Genscan"

    # [PROCESS]
    APP_CONFIG["run_once"] = True
    APP_CONFIG["sleep"] = 600
    APP_CONFIG["max_per_cycle"] = 50
    APP_CONFIG["run_action"] = "both"

    # [FOLDERS]
    APP_CONFIG["working_folder"] = gs_args.APP_ARGS["workdir"]
    APP_CONFIG["loglevel"] = gs_args.APP_ARGS["loglevel"]

    # root working folders, these are used by the whole process
    APP_CONFIG["debug_folder"] = os.path.join(APP_CONFIG["working_folder"], "debug")
    APP_CONFIG["logs_folder"] = os.path.join(APP_CONFIG["working_folder"], "logs")
    APP_CONFIG["uploads_folder"] = os.path.join(APP_CONFIG["working_folder"], "uploads")
    APP_CONFIG["failed_folder"] = os.path.join(APP_CONFIG["working_folder"], "failed")
    APP_CONFIG["divisions_folder"] = os.path.join(
        APP_CONFIG["working_folder"], "divisions"
    )

    # folders used during file processing, created in the same folder where
    #  first document is found
    APP_CONFIG["processed_folder"] = "processed"
    APP_CONFIG["renamed_folder"] = "renamed"
    APP_CONFIG["review_folder"] = "review"

    # [FILES]
    APP_CONFIG["file_overwrite"] = False
    APP_CONFIG["replace_space"] = " "

    # [IMAGES]
    APP_CONFIG["concat_orientation"] = "vertical"
    APP_CONFIG["minimum_size"] = 300
    APP_CONFIG["debug_images_with_faces"] = False
    APP_CONFIG["watermark"] = True
    APP_CONFIG["watermark_text"] = APP_CONFIG["division"]
    APP_CONFIG["save_to_pdf"] = False
    APP_CONFIG["keep_original"] = False

    # [AI]
    # The AI (RapidOCR + vision model in Ollama) replaces Tesseract + regex
    # for name, dates and places. Everything else stays the same.
    APP_CONFIG["ai_enabled"] = True
    APP_CONFIG["ai_model"] = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b")
    APP_CONFIG["ai_ollama_url"] = "http://localhost:11434"
    APP_CONFIG["ai_max_pages"] = 2
    APP_CONFIG["ai_upload_guesses"] = False
    APP_CONFIG["ai_save_json"] = True
    APP_CONFIG["ai_max_failures"] = 3

    # Override if defined in config
    if os.path.isfile(file):
        _config = ConfigParser()
        _config.read(file)

        try:
            # [WORDPRESS]
            APP_CONFIG["wp_site"] = _config.get("WORDPRESS", "site", fallback="")

            APP_CONFIG["wp_max_disk_used"] = _config.getint(
                "WORDPRESS", "max_disk_used", fallback=50000
            )
            APP_CONFIG["wp_max_db_used"] = _config.getint(
                "WORDPRESS", "max_db_used", fallback=400
            )
            APP_CONFIG["wp_max_uploads"] = _config.getint(
                "WORDPRESS", "max_uploads", fallback=20
            )
            APP_CONFIG["division"] = _config.get(
                "WORDPRESS", "division", fallback="Genscan"
            )

            # [PROCESS]
            APP_CONFIG["run_once"] = _config.getboolean(
                "PROCESS", "run_once", fallback=True
            )
            APP_CONFIG["sleep"] = _config.getint("PROCESS", "sleep", fallback=600)
            APP_CONFIG["max_per_cycle"] = _config.getint(
                "PROCESS", "max_per_cycle", fallback=50
            )
            APP_CONFIG["run_action"] = _config.get(
                "PROCESS", "run_action", fallback="both"
            ).lower()

            # [FOLDERS]
            APP_CONFIG["working_folder"] = (
                _config.get(
                    "FOLDERS", "working_folder", fallback=gs_args.APP_ARGS["workdir"]
                )
            ).replace('"', "")

            APP_CONFIG["loglevel"] = _config.get(
                "FOLDERS", "loglevel", fallback=gs_args.APP_ARGS["loglevel"]
            )

            APP_CONFIG["debug_folder"] = os.path.join(
                APP_CONFIG["working_folder"],
                _config.get("FOLDERS", "debug_folder", fallback="debug"),
            )
            APP_CONFIG["logs_folder"] = os.path.join(
                APP_CONFIG["working_folder"],
                _config.get("FOLDERS", "logs_folder", fallback="logs"),
            )
            APP_CONFIG["uploads_folder"] = os.path.join(
                APP_CONFIG["working_folder"],
                _config.get("FOLDERS", "uploads_folder", fallback="uploads"),
            )
            APP_CONFIG["failed_folder"] = os.path.join(
                APP_CONFIG["working_folder"],
                _config.get("FOLDERS", "failed_folder", fallback="failed"),
            )
            APP_CONFIG["divisions_folder"] = os.path.join(
                APP_CONFIG["working_folder"],
                _config.get("FOLDERS", "divisions_folder", fallback="divisions"),
            )

            APP_CONFIG["processed_folder"] = _config.get(
                "FOLDERS", "processed_folder", fallback="processed"
            )
            APP_CONFIG["renamed_folder"] = _config.get(
                "FOLDERS", "renamed_folder", fallback="renamed"
            )
            APP_CONFIG["review_folder"] = _config.get(
                "FOLDERS", "review_folder", fallback="review"
            )

            # [FILES]
            APP_CONFIG["file_overwrite"] = _config.getboolean(
                "FILES", "file_overwrite", fallback=False
            )
            APP_CONFIG["replace_space"] = _config.get(
                "FILES", "replace_space", fallback=" "
            )

            # [IMAGES]
            APP_CONFIG["concat_orientation"] = _config.get(
                "IMAGES", "concat_orientation", fallback="vertical"
            )
            APP_CONFIG["minimum_size"] = _config.get(
                "IMAGES", "minimum_size", fallback=300
            )
            APP_CONFIG["debug_images_with_faces"] = _config.getboolean(
                "IMAGES", "debug_images_with_faces", fallback=False
            )
            APP_CONFIG["watermark"] = _config.getboolean(
                "IMAGES", "watermark", fallback=True
            )
            APP_CONFIG["watermark_text"] = (
                _config.get("IMAGES", "watermark_text", fallback=APP_CONFIG["division"])
            )[0:19]
            APP_CONFIG["save_to_pdf"] = _config.getboolean(
                "IMAGES", "save_to_pdf", fallback=False
            )
            APP_CONFIG["keep_original"] = _config.getboolean(
                "IMAGES", "keep_original", fallback=False
            )

            # [AI]
            APP_CONFIG["ai_enabled"] = _config.getboolean(
                "AI", "enabled", fallback=APP_CONFIG["ai_enabled"]
            )
            APP_CONFIG["ai_model"] = _config.get(
                "AI", "model", fallback=APP_CONFIG["ai_model"]
            ).strip()
            APP_CONFIG["ai_ollama_url"] = _config.get(
                "AI", "ollama_url", fallback=APP_CONFIG["ai_ollama_url"]
            ).strip()
            APP_CONFIG["ai_max_pages"] = _config.getint(
                "AI", "max_pages", fallback=APP_CONFIG["ai_max_pages"]
            )
            APP_CONFIG["ai_upload_guesses"] = _config.getboolean(
                "AI", "upload_guesses", fallback=APP_CONFIG["ai_upload_guesses"]
            )
            APP_CONFIG["ai_save_json"] = _config.getboolean(
                "AI", "save_json", fallback=APP_CONFIG["ai_save_json"]
            )
            APP_CONFIG["ai_max_failures"] = _config.getint(
                "AI", "max_failures", fallback=APP_CONFIG["ai_max_failures"]
            )

        except ValueError:
            print(
                "Error in config file: verify integers, floats and booleans are correct!",
                flush=True,
            )
            sys.exit(1)

    # Web site is required
    if len(APP_CONFIG["wp_site"]) == 0:
        print(
            "Error: a web URL should be defined in the config file: [WORDPRESS][site]",
            flush=True,
        )
        sys.exit(1)

    # Working directory is required
    if len(APP_CONFIG["working_folder"]) == 0:
        error_msg = "Error: a proper working folder should be defined in "
        error_msg += "the config file: [FOLDERS][working_folder]"
        print(
            error_msg,
            flush=True,
        )
        sys.exit(1)
    return APP_CONFIG
