"""
Some helper functions for file handling
"""

import logging
import os
import random
import re
import shutil
import sys

# from configparser import ConfigParser
from glob import glob
from pathlib import Path

import gs_config

logger = logging.getLogger("gsw_logger")


def create_simple_folder(folder_path):
    """
    Create folder recursively if it doesn't exist, regardless of parent folders

    Parameters:
      path (str): The folder path to create.

    Return:
      True: Only if success. On failure app is terminated
    """
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            logger.debug("%15s: %s", "Folder created", folder_path)
        except OSError:
            logger.debug("Error creating directory %s", folder_path)
            return False
    else:
        logger.debug("%15s: %s", "Path exists", folder_path)

    return True


def create_base_folder(folder_path, sub_folder=None):
    """
    Create folder recursively if it doesn't exist.

    Parameters:
      path (str): The folder path to create.
      folder (str): Optional sub folder to add.

    Return:
      bool: True, only if success. On failure app is terminated
    """

    if sub_folder is None:
        folder_path, sub_folder = os.path.split(folder_path)

    if os.path.exists(folder_path):
        path = os.path.join(folder_path, sub_folder)
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError:
                print(f"Error creating directory {path}.", flush=True)
                sys.exit()
    else:
        print(f"Parent path {folder_path} does not exist.", flush=True)
        sys.exit()

    return True


def create_base_folders(working_folder_path):
    """
    Creating necessary folders in working folder, from globally available arguments

    Parameters:
      working_folder_path (str): path of working folder

    Return:
      process_vars (dict): A dictionary containing process settings
    """
    # process_vars = {}

    logger.info("Creating folders")

    # Verify working directory exists
    if not os.path.exists(working_folder_path):
        print(f"=== Working folder {working_folder_path} does not exist.", flush=True)
        sys.exit()

    # Create required folders
    folders = [
        "debug_folder",
        "divisions_folder",
        "failed_folder",
        "logs_folder",
        "uploads_folder",
    ]

    for folder in folders:
        if create_base_folder(gs_config.APP_CONFIG[folder]):
            logger.debug("Folder available: %s", gs_config.APP_CONFIG[folder])


def filter_files(all_files, excluded_dirs=None):
    """
    List all files to keep, excluding those from certain directories/folders

    Parameters:
        all_files (list): All filepaths found
        excluded_dirs (list): List of directories/folders to ignore

    Return:
        list: List of files form directory/folder paths to keep
    """
    if excluded_dirs is None:
        excluded_dirs = []
    return [
        file
        for file in all_files
        if not os.path.isdir(file) and not any(dir in file for dir in excluded_dirs)
    ]


def get_file_paths(folder_path, file_patterns=None):
    """
    Read list of files in a folder and sub-folders.

    Parameters:
      folder_path (str): Path of folder holding the files to read.
      file_patterns (list): List of file name patterns to match (e.g., ["*.pdf", "*.jpg"]).

    Return:
      list: List of file paths, can be empty.
    """

    logger.info("Checking for local files")

    # Default file pattern
    if file_patterns is None:
        file_patterns = ["*.pdf"]

    # Check if folder path exists
    if not os.path.exists(folder_path):
        logger.warning("Base folder path %s does not exist.", folder_path)
        print(f"Base folder path {folder_path} does not exist.", flush=True)
        sys.exit()

    # Read the files
    document_files = []
    for file_pattern in file_patterns:
        full_path = os.path.join(folder_path, "**", file_pattern)
        logger.debug("Reading files with pattern: %s", full_path)
        document_files.extend(glob(full_path, recursive=True))

    # Remove files in top level folders that should not be processed
    excluded_dirs = [
        gs_config.APP_CONFIG["debug_folder"],
        gs_config.APP_CONFIG["failed_folder"],
        gs_config.APP_CONFIG["logs_folder"],
        gs_config.APP_CONFIG["processed_folder"],
        gs_config.APP_CONFIG["renamed_folder"],
        gs_config.APP_CONFIG["review_folder"],
        gs_config.APP_CONFIG["uploads_folder"],
        "_ignore",
        "_corrupt",
        "_failed",
    ]
    document_files = filter_files(document_files, excluded_dirs)
    document_files.sort()
    # random.shuffle(document_files)

    logger.info("Found %s local files available", len(document_files))

    return document_files


def move_file(source_file_path, destination_file_path, overwrite=False):
    """
    Move file from its original location to new location.

    Parameters:
      source_file_path (str): Full path with filename of file to copy
      destination_file_path (str): Full path of destination
      overwrite (bool): Whether to overwrite the destination file if it exists.

    Return:
      bool: success or failure to move
      str: original file path on failure, new file path on successful move
    """

    logger.debug("Start")

    logger.info("%15s: %s", "Moving from", source_file_path)
    logger.info("%15s: %s", "to", destination_file_path)

    if not os.path.exists(source_file_path):
        logger.debug("Source file does not exist")
        return False, source_file_path

    destination_path, destination_file = os.path.split(destination_file_path)
    # logger.debug("%15s: %s", "Original file", destination_file)
    if not os.path.exists(destination_path):
        logger.debug("Creating destination folder(s) %s", destination_path)
        folder_created = create_simple_folder(destination_path)
        if not folder_created:
            return False, source_file_path

    if not overwrite:
        base_name, ext = os.path.splitext(destination_file)
        counter = 1
        while os.path.exists(destination_file_path):
            destination_file = f"{base_name}_{counter}{ext}"
            destination_file_path = os.path.join(destination_path, destination_file)
            counter += 1
        # logger.debug("%15s: %s", "Renamed file", destination_file)
        logger.debug("Unique destination path resolved: %s", destination_file_path)

    try:
        shutil.move(source_file_path, destination_file_path)
        logger.info("%15s: %s", "Moved from", source_file_path)
        logger.info("%15s: %s", "to", destination_file_path)

    except shutil.SameFileError:
        # If source and destination are same
        logger.debug("Failure moving file; source and destination are same.")

    except IsADirectoryError:
        # If destination is a directory.
        logger.debug("Failure moving file; destination is directory.")

    except PermissionError:
        # If there is any permission issue
        logger.debug("Failure moving file; permission denied.")

    except Exception as error_msg:
        logger.debug("Failure moving file")
        logger.debug(
            "Error %s occurred.",
            error_msg,
        )
        logger.debug(
            "Error arguments %s",
            error_msg.args,
        )
    else:
        return True, destination_file_path

    return False, source_file_path


def copy_file(
    source_file_path, destination_file_path
):  # kdo: 2024-012-04 - seems unused
    """
    Copy file from its original location to new location.

    Parameters:
      source_file_path (str): Full path with filename of file to copy
      destination_file_path (str): Full path of destination

    Return:
      bool: success or failure to move
    """

    status = False

    _, source_file = os.path.split(source_file_path)  # eg. xxxxxx.pdf
    logger.info("Copying %s", source_file)
    logger.debug("Copying %s", source_file_path)
    logger.debug("     to %s", destination_file_path)
    if not os.path.exists(source_file_path):
        logger.debug("File does not exist %s", source_file_path)

        return status

    destination_path, _ = os.path.split(destination_file_path)
    if not os.path.exists(destination_path):
        logger.debug("Destination folder does not exist for %s", destination_file_path)

        return status

    try:
        shutil.copyfile(source_file_path, destination_file_path)
        logger.debug("Copied %s", source_file_path)
        status = True
    except shutil.SameFileError:
        # If source and destination are same
        logger.debug("Failure moving file; source and destination are same.")
    except IsADirectoryError:
        # If destination is a directory.
        logger.debug("Failure moving file; destination is directory.")
    except PermissionError:
        # If there is any permission issue
        logger.debug("Failure moving file; permission denied.")
    except Exception as error_msg:
        logger.debug("Failure moving file")
        logger.debug(
            "Error %s occurred.",
            error_msg,
        )
        logger.debug(
            "Error arguments %s",
            error_msg.args,
        )

    return status


def create_empty_file(file_path, file_name):
    """
    Create an empty file at the specified path with the given filename.

    Parameters:
        file_path (str): Directory where the file will be created.
        file_name (str): Name of the file to create.

    Returns:
        Path: The Path object of the created file, or None if an error occurred.
    """
    try:
        # Combine path and filename
        target_path = Path(file_path) / file_name

        # Ensure the directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the empty file
        target_path.touch(exist_ok=True)
        logger.info("Empty file created successfully: %s", target_path)
        return target_path
    except Exception as error:
        logger.error("Failed to create empty file: %s. Error: %s", file_name, error)
        return None


def delete_file(source_file_path):
    """
    Delete a file from its location.

    Parameters:
        source_file_path (str): Full path of the file to delete.

    Returns:
        bool: True if the file was successfully deleted, False otherwise.
    """
    logger.debug("Attempting to delete file: %s", source_file_path)

    file_path = Path(source_file_path)
    if not file_path.exists():
        logger.debug("File does not exist: %s", source_file_path)
        return False

    try:
        file_path.unlink()
        logger.info("File deleted successfully: %s", source_file_path)
        return True
    except OSError as error:
        logger.error("Failed to delete file: %s. Error: %s", source_file_path, error)
        return False


def check_file_exists(full_file_path=None):
    """
    Check if a file exists at the given path.

    Parameters:
        full_file_path (str): The path to check.

    Returns:
        bool or None: True if the file exists, False if it doesn't,
                      or None if no path is provided.
    """
    if full_file_path is None:
        logger.debug("No file path provided")
        return False

    file_path = Path(full_file_path)
    file_exists = file_path.is_file()

    logger.debug("File exists: %s -> %s", full_file_path, file_exists)
    return file_exists


def count_files_in_folders(root_dir, exclude_folders=None):
    """
    Count the number of files in the first level subfolders of the provided folder,
    including the subfolders but excluding those in the provided folder.
    Some predefined folders are excluded from the count.

    Parameters:
        root_dir (str): root path to traverse
        exclude_folders (list): folder names to exclude, subfolders are also excluded

    Return:
        file_count_dict (dict): dictionary of folder as key, count as value
    """
    # Skip if not correct type
    if exclude_folders is not None and not isinstance(exclude_folders, list):
        logger.debug(
            "Not correct type (%s), should be list. Bailing.", type(exclude_folders)
        )
        return None

    # Skip if folder is not there
    root_dir = os.path.normpath(root_dir)
    if not os.path.isdir(root_dir):
        logger.debug("File path is not a folder. Bailing.")
        return None

    file_count_dict = {}

    # Define a set of allowed extensions for documents and images
    allowed_extensions = {".pdf", ".jpg", ".jpeg"}

    # Default folders to exclude
    default_exclusions = [
        gs_config.APP_CONFIG["debug_folder"],
        gs_config.APP_CONFIG["logs_folder"],
        gs_config.APP_CONFIG["uploads_folder"],
        gs_config.APP_CONFIG["failed_folder"],
        gs_config.APP_CONFIG["processed_folder"],
        gs_config.APP_CONFIG["renamed_folder"],
        gs_config.APP_CONFIG["review_folder"],
        "_ignore",
        "_corrupt",
        "_failed",
    ]

    # Combine default exclusions with user-provided exclusions
    if exclude_folders is None:
        exclude_folders = []
    all_exclusions = set(default_exclusions + exclude_folders)

    # Iterate over the first-level subdirectories in the root directory
    for first_level_folder in os.listdir(root_dir):
        first_level_path = os.path.normpath(os.path.join(root_dir, first_level_folder))

        # Check if it's a directory and not in the exclusion list
        if os.path.isdir(first_level_path) and first_level_folder not in all_exclusions:
            file_count = 0
            # Traverse each first-level subfolder and count files in all nested subdirectories
            for dirpath, dirnames, filenames in os.walk(first_level_path):
                # If the current folder or any of its parent folders should be excluded, skip it
                if any(
                    excluded in dirpath.split(os.sep) for excluded in all_exclusions
                ):
                    # Prevent further traversal into subdirectories
                    dirnames[:] = []
                    continue
                # Count files
                file_count += sum(
                    1
                    for file in filenames
                    if file.lower().endswith(tuple(allowed_extensions))
                )

            # Store the count of files with the first-level folder name as key
            file_count_dict[first_level_folder] = file_count
            logger.debug("%20s: %s", first_level_folder, file_count)

    total_file_count = sum(file_count_dict.values())
    logger.info("%15s: %s", "Total file count", total_file_count)

    return file_count_dict if total_file_count > 0 else None


def move_corrupt_file(filepath):
    """
    Move a file considered to be corrupt to _corrupt folder.

    Parameters:
        filepath (str): Input string containing file path of file to move.

    Returns:
        bool
    """

    # Move file to _corrupt folder
    logger.error("PDF file is corrupt %s", filepath)
    # Get filename and folder from file path
    parent_folder, corrupt_file = os.path.split(filepath)
    corrupted_file_path = os.path.join(
        parent_folder,
        "_corrupt",
        corrupt_file,
    )
    logger.debug("Moving original file to _corrupt folder")
    status = move_file(filepath, corrupted_file_path)

    return status
