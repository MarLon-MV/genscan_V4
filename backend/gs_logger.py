"""
Set up a project wide logger
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from gs_file_tools import create_base_folder
from gs_helpers import separator_msg


def setup_logger(
    log_folder=os.getcwd(), log_file="app.log", log_level="INFO", log_name="my_logger"
):
    """
    Set up a shared logger with a rotating file handler.

    Parameters:
        log_folder (string): Path of working directory. Default is current folder.
        log_file (string): The name of the log file. Default is "app.log".
        log_level (string): The logging level. Default is "INFO".
        log_name (string): The name of the logger. Default is "my_logger".

    Return:
        logger instance
    """

    # Ignore identifier of the current process.
    logging.logProcesses = False
    # Ignore identifier and name of the current thread.
    logging.logThreads = False
    # Ignore name of the current process in the multiprocessing framework.
    logging.logMultiProcessing = False

    # Create a logger
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level.upper())

    # Prevent propagation to root logger (which might send logs to console)
    logger.propagate = False

    # Remove any existing handlers attached to the logger
    if logger.hasHandlers():
        logger.handlers.clear()

    # Check if the logger already has handlers to avoid duplicate entries
    if not logger.handlers:
        if log_level != "NOTSET":
            # Create log file path
            if not os.path.exists(log_folder):
                create_base_folder(log_folder)
            # Construct log file path
            log_file = os.path.join(log_folder, log_file)

            # Add FileHandler for logging to a file
            file_handler = RotatingFileHandler(
                log_file, maxBytes=100 * 1024 * 1024, backupCount=100, encoding="utf-8"
            )
            file_handler.setLevel(log_level.upper())  # Set the level for file logging

            # Optionally, you can set a formatter for better log output format
            formatter = logging.Formatter(
                "%(asctime)s||%(levelname)-8s||%(funcName)-30s||%(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)

            # Add the file handler to the logger
            logger.addHandler(file_handler)

            # (Optional) If you also want to remove console output, avoid adding StreamHandler
            # logger.addHandler(logging.StreamHandler())  
            # Do NOT add this handler if you want to prevent console logs

            # Now, the logger will only write to the file, not the console.

            # Add a StreamHandler for the console with a higher log level
            # console_handler = logging.StreamHandler()
            # console_handler.setLevel(
            #     logging.ERROR
            # )  # Only ERROR and above will be logged to console
            # console_handler.setFormatter(formatter)

            # # Add the console handler
            # logger.addHandler(console_handler)

            logger.info("%s", separator_msg("App started"))

            logger.debug("Logger active, level %s", logging.getLevelName(logger.level))

    return logger
