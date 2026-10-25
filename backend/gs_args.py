"""
Creating a global variable for CLI arguments that can be made available across modules
"""

import argparse
from textwrap import dedent

APP_ARGS = {}


def get_arguments():
    """
    Get us the arguments passed from starting the main script.
    """
    # Get command line arguments
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """
            GenScan4Web processes pdf files with embedded scanned images of memorial cards or 
            funeral announcements by pulling out useful information for genealogists.
            That information is then uploaded to a Wordpress web site where volunteers help 
            verify the information.
            Once verified, the redacted information is used to rename the original pdf files 
            holding the scans.
            """
        ),
    )
    parser.add_argument(
        "-w",
        "--workdir",
        default="",
        help="Set the working directory",
    )
    parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        # help="Enable copy of original files to 'backup' folder",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-c",
        "--csv",
        action="store_true",
        # help="Enable export of processed data to 'csv' folder",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-m",
        "--move",
        action="store_true",
        # help="Enable move of renamed files to 'processed' folder",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        type=str,
        default="NOTSET",
        choices=["NOTSET", "DEBUG", "INFO"],
        help="Set logging level, default is %(default)s",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s v0.1",
        help="Show version number",
    )
    # Below arguments only to be used during development
    parser.add_argument("-t", "--test", action="store_true", help=argparse.SUPPRESS)

    return vars(parser.parse_args())


def init():
    """
    Initializing the global dictionary for the arguments
    """
    global APP_ARGS
    APP_ARGS = get_arguments()
