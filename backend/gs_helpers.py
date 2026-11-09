"""
Some helper functions for genscan
"""

import logging
import os
import random
import re

# import shutil
import string

# import sys
import time
import unicodedata

# from configparser import ConfigParser
from datetime import datetime
from enum import Enum

import emoji
import pandas as pd

import gs_config
from gs_corrections import dict_city_corrections
from gs_db_tools import (
    get_division_diacritics,
    get_division_short_names,
    get_file_template,
)

logger = logging.getLogger("gsw_logger")
CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")


class LifeEvent(Enum):
    """Some life event constants"""

    BIRTH = "birth"
    DEATH = "death"


def clean_html(raw_html):
    """
    Cleans out HTML tags from string.

    Parameters:
      raw_html (str): String containing HTML tags.

    Return:
      clean_text (str): Cleaned out string.
    """
    clean_text = re.sub(CLEANR, "", raw_html)
    return clean_text


def shorten_msg(message, max_length=50):
    """
    Shortens string to specific length by trimming left and right

    Parameters:
      message (str): String to shorten.
      max_length (integer): final length of middle part.

    Return:
      String.
    """
    if len(message) > max_length:
        characters = (len(message) - max_length) // 2 + 1
        message = message[characters:-characters]
        message = message[:max_length]

    return message


def convert_string_to_bool(str_value):
    """
    Convert string to bool

    Parameters:
      str_value (str): A string representing true or false, 0 or 1

    Return:
      (bool)
    """

    match str_value.lower().strip():
        case "true":
            return True
        case "false":
            return False
        case "1":
            return True
        case "0":
            return False
        case _:
            return False


def separator_msg(message, decorator="-", repeats=20):
    """
    Create a separator line with decorators front and back of the message
       -----Message-----

    Parameters:
      message (str): String to embed.
      decorator (str): (Single) character to repeat. Default: "-"
      repeats (integer): Number of times to repeat the decorator

    Return:
      String.
    """

    return shorten_msg(
        (decorator * repeats) + " " + message + " " + (decorator * repeats)
    )


def is_tess_dict(tess_dict):
    """
    Check if dictionary is actually a Tesseract dictionary

    Parameters:
      tess_dict (dict): Tesseract OCR dictionary

    Return:
      Boolean
    """

    expected_keys = [
        "level",
        "page_num",
        "block_num",
        "par_num",
        "line_num",
        "word_num",
        "left",
        "top",
        "width",
        "height",
        "conf",
        "text",
    ]

    # Test if it is a Tesseract dictionary
    return isinstance(tess_dict, dict) and bool(
        set(tess_dict.keys()).intersection(expected_keys)
    )


def clean_ocr_text(ocr_dict, remove_text=""):
    """
    Clean up the dictionary by removing/replacing certain characters/words

    Parameters:
      ocr_dict (dict): Tesseract OCR dictionary
      remove_text (str): (regex) string that should be removed from the dictionary

    Return:
      ocr_just_words (dict): Reduced Tesseract Dictionary: just words or None
    """

    logger.info("Cleaning up Tesseract dictionary")

    ocr_just_words = None
    year = int(datetime.now().strftime("%Y"))

    # Test if it is a Tesseract dictionary
    if is_tess_dict(ocr_dict):
        # Convert to Pandas DataFrame (not sure if this is required to filter out data but it works)
        df_ocr = pd.DataFrame.from_dict(ocr_dict)

        # Extract just the words (level 5)
        words_only = (df_ocr[(df_ocr["page_num"] == 1) & (df_ocr["level"] == 5)]).copy()
        words_only.reset_index(drop=True, inplace=True)
        logger.debug("Total word count: %s", len(words_only["text"]))

        # Remove this
        remove_char = (
            r"[,…“”‘’«»*/:!#%&;<=>®©@_—{}~£€𝜋🟊„•■\.\,\|\[\]\^\?\"\(\)\$\*\\\']"
        )
        remove_words = rf"^({remove_text})$"

        # Walk thru all words:
        for i, word in enumerate(words_only["text"]):
            # Remove emojis
            word = emoji.replace_emoji(word, replace="")

            # Clean words from unnecessary characters and update
            word = re.sub(remove_char, "", word).strip()
            words_only.loc[i, "text"] = word

            # Remove words that have weird proportions
            ratio = (
                words_only.loc[i, "height"] / words_only.loc[i, "width"]
                if words_only.loc[i, "width"] > 0
                else 100
            )

            # Remove certain numbers (to exclude as much as possible non-year numbers)
            number = 0
            if word.strip().isdecimal():
                number = int(word)
                if 31 < number < 1600:
                    number = 99999

            # Remove low confidence words
            # confidence = int(words_only.loc[i, "conf"])

            # Remove words that should not be considered
            word = re.sub(
                remove_words,
                "",
                word,
                flags=re.IGNORECASE,
            ).strip()

            if (
                ratio > 10.0
                or len(word) < 1  # Don't seem that many
                or number > year
                # or confidence < 50 # drops a lot of words that do seem correct
            ):
                words_only.drop(i, inplace=True)

        words_only.reset_index(drop=True, inplace=True)
        logger.debug("Final word count: %s", len(words_only["text"]))

        ocr_just_words = words_only.to_dict("list")

    return ocr_just_words


def clean_up_text(text_to_clean="", remove_text=""):
    """
    Clean up the embedded text by removing/replacing certain characters/words

    Parameters:
      text_to_clean (str): Text to clean out
      remove_text (str): (regex) string that should be removed from the text

    Return:
      text_to_clean (str): Just words
    """

    logger.info("Cleaning up text string")
    if len(text_to_clean) == 0:
        return text_to_clean

    # Replace known faults
    text_to_clean = re.sub(r"T\sremelo", "Tremelo", text_to_clean)

    # Remove emojis
    text_to_clean = emoji.replace_emoji(text_to_clean, replace="")

    # Remove this
    remove_char = r"[,…“”‘’«»*/:!#%&;<=>®©@_—{}~£€𝜋🟊„•■\.\,\|\[\]\^\?\"\(\)\$\*\\\']"
    remove_words = rf"({remove_text})"

    # Clean words from unnecessary characters and update
    text_to_clean = re.sub(r"\.", " ", text_to_clean).strip()
    text_to_clean = re.sub(remove_char, "", text_to_clean).strip()

    # Remove words that should not be considered
    text_to_clean = re.sub(
        remove_words,
        "",
        text_to_clean,
        flags=re.IGNORECASE,
    ).strip()

    logger.debug("Cleaned up text has %s chars", len(text_to_clean))
    logger.debug("%15s : %s", "Clean text len", len(text_to_clean))
    logger.debug("%15s : %s", "Clean text", text_to_clean)

    return text_to_clean


def readable_ocr_text(ocr_dict, word_separator=" "):
    """
    Create something readable text out of OCR data, including line separations

    Parameters:
      ocr_dict (dict): Tesseract OCR dictionary
      word_separator (str): How words are separated one from the other, default is a space

    Return:
      ocr_readable_text (str): Readable text
    """

    logger.info("Creating readable OCR text")

    ocr_just_text = "\n"

    # Test if it is a Tesseract dictionary
    if is_tess_dict(ocr_dict):
        # Convert to Pandas DataFrame (not sure if this is required to filter out data but it works)
        df_ocr = pd.DataFrame.from_dict(ocr_dict)

        # Extract just the words (level 5)
        words_only = (df_ocr[(df_ocr["page_num"] == 1) & (df_ocr["level"] == 5)]).copy()
        words_only.reset_index(drop=True, inplace=True)

        # Group up words in same lines
        lines_grouped = words_only.groupby(
            ["level", "page_num", "block_num", "par_num", "line_num"]
        )

        # regex = rf"({word_separator}(?:"
        # regex += r"°\d+|\+\d+|"
        # regex += r"geboren|"
        # regex += r"overleden|overleed|heengegaan|"
        # regex += r"gestorven|stierf|sterft|teruggekeerd|"
        # regex += r"ingeslapen|ontslapen|ontsliep|ontslaapt|herboren|"
        # regex += rf"ten{word_separator}hemel{word_separator}gevaren|ging{word_separator}over|"
        # regex += r"overgegaan|verongelukt|"
        # # French
        # regex += r"née|né|"
        # regex += r"décédée|décédé|rejoint|fusillé|endormie"
        # regex += rf"){word_separator})"

        logger.debug(
            "Extracted line: (level,page,block,par,line) [max_height,max_width,ratio, words] text"
        )
        for i, line in lines_grouped:
            line_of_text = (
                f"{word_separator}{word_separator.join(line['text'])}{word_separator}"
            )
            # text_found = find_regex_in_string(line_of_text, regex)
            # if bool(text_found):
            #     logger.debug(
            #         "Extracted line: [%s] %s >>>>%s",
            #         i,
            #         line["height"].max(),
            #         line_of_text,
            #     )
            # else:
            logger.debug(
                "Extracted line: %s [%3i,%3i,%5.2f,%2i] %s",
                i,
                line["height"].max(),
                line["width"].max(),
                (
                    line["height"].max() / line["width"].max()
                    if line["width"].max() > 0
                    else 1
                ),
                len(line["text"]),
                line_of_text,
            )

            if len(line_of_text.strip(word_separator)) > 0:
                ocr_just_text += line_of_text + "\n"

    # Remove emojis
    ocr_just_text = emoji.replace_emoji(ocr_just_text, replace="")

    return ocr_just_text


def generate_rand(length=10, string_type="lower"):
    """
    Generate a randomly generated string of defined length

    Parameters:
      length (int): Length of generated string
      type (str): any of letters (default), digits, year, printable, upper or lower case

    Return:
      String
    """
    match string_type:
        case "digits":
            return "".join(random.choices(string.digits, k=length))
        case "year":
            return str(random.randrange(1600, int(datetime.now().strftime("%Y"))))
        case "printable":
            return "".join(random.choices(string.printable, k=length))
        case "upper":
            return "".join(random.choices(string.ascii_uppercase, k=length))
        case "lower":
            return "".join(random.choices(string.ascii_lowercase, k=length))
        case _:
            return "".join(random.choices(string.ascii_letters, k=length))


def average_without_outliers(values, threshold=2.0):
    """
    Calculate the average of a list of values, excluding outliers.

    Parameters:
    - values (list): List of numerical values.
    - threshold (float): Threshold for excluding outliers based on standard deviation.
                        Values outside the threshold * standard deviation are excluded.

    Returns:
    - integer: Nearest integer of average of the values excluding outliers or
               default value 30
    """
    # Example usage:
    # data = [1, 2, 3, 100, 5, 6, 7, 8, 9]
    # result = average_without_outliers(data)
    # print("Average without outliers:", result, flush=True)

    if not values:
        return 30  # Handle empty list

    # Calculate the mean and standard deviation
    mean_value = sum(values) / len(values)
    std_dev = (sum((x - mean_value) ** 2 for x in values) / len(values)) ** 0.5

    # Filter out values that deviate too much
    filtered_values = [x for x in values if abs(x - mean_value) <= threshold * std_dev]

    if not filtered_values:
        return 30  # Handle the case where all values are considered outliers

    # Calculate the average of the filtered values
    rounded_average = round(sum(filtered_values) / len(filtered_values))
    return rounded_average


def split_full_name(full_name):
    """
    Splitting a full name into first and last name.

    Parameters:
      full_name (str): Full name including underscores as separators

    Return:
      last_name (str): Last name or None
      first_name (str): First name or None
    """

    # Adjust last name based on predefined first parts
    full_name = re.sub(r"(^vanden)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^vander)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^vande)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^van)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^der)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^den)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^de)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^ten)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"(^ter)_", r"\1 ", full_name, flags=re.IGNORECASE)

    full_name = re.sub(r"([_\s]vanden)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]vander)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]vande)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]van)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]der)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]den)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]de)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]ten)_", r"\1 ", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"([_\s]ter)_", r"\1 ", full_name, flags=re.IGNORECASE)

    # Split in first and last name
    first_name, _, last_name = full_name.rpartition("_")

    # If more then one dash -, replace them by a space
    if first_name.count("-") > 1:
        first_name = first_name.replace("-", " ")

    # Camel case the results
    first_name = first_name.replace("_", " ").title()
    last_name = last_name.title()

    first_name = first_name if len(first_name) > 2 else None
    last_name = last_name if len(last_name) > 2 else None

    logger.debug("%15s: %s, %s", "name", first_name, last_name)

    return first_name, last_name


def get_name(ocr_dict):
    """
    Usually the name of the deceased is printed in the tallest font, so try
    to find the name based on tallest words
    Not always successful, but proven to be best approach

    Parameters:
      ocr_dict (dict): Tesseract OCR dictionary

    Return:
      last_name (str): Last name
      first_name (str): First name
    """

    first_name = ""
    last_name = ""
    max_height = 0
    line_with_name = ""

    ignore_words = r"(druk|begr|ondern|uitv|rouwl|rouwc|begel|gevoel|kerkel|moeder|"
    ignore_words += r"_Huis|kind|RUST_IN_VREDE|BĲ_DE_HEER|jezus|christus|jésus|zuster|"
    ignore_words += r"gedacht|vrome|zalig|ziel|droefh|godvr|barmh|dood|bidden|rouw|"
    ignore_words += r"rechtv|hemelr|pieux|bid_v|moedig|ECCE_HOMO|memoriam|crux|"
    ignore_words += r"gedenk|geloof|hoop|petits-enfants|genade|heilig|REQUIESCAT|"
    ignore_words += r"gewaar|geest|leven|van_dit|gods_|gelijk|tijd|bid_god|rust|"
    ignore_words += r"doorboord|wegdoen|repose|prières|sierraad|mémoire|wijsh|"
    ignore_words += r"geleden|0|1|2|3|4|5|6|7|8|9|wereld|elkander|testament|"
    ignore_words += r"heeren|paradisum|aflaat|consolatrix|gezegend|opgeëiste|"
    ignore_words += r"weledelen|geschiede|bloem|liefde|broeder|zuster|"
    ignore_words += r"dierbaar|dierbare|dankbaar|dankbare|herinnering|aandenken|pastor)"

    break_words = r"(né|née|naquit|geboren|°|echtg|weduw|veuve|veuf|zoon|dochter)"

    remove_text = (
        r"(dame|dokter|juffrouw|jufvrouw|meester|mejuffer|mej|priester|mejuffrouw|"
    )
    remove_text += r"mevrouw|mevr|mijnheer|monsieur|pater|priester|eerzamen|vrouw|zeh|mademoiselle|"
    remove_text += r"soeur|madame|pére|mére|engelken|messire|weduwe|weduwnaar|"
    remove_text += r"echtgenoot|echtgenote|echtgenoote|eerwaarde|BARONNE|BARON|"
    remove_text += r"weduw|wed|de_heer|heer|dubbel|sab|dochtertje|dochter|zoontje|zoon|"
    remove_text += r"echtg|egtg|missionaris|schipper|echtgemere|inspecteur|drs|"
    remove_text += r"kanunnik|directeur|veuve|veuf|epou|épou|fille|fils|douairière)"

    # Test if it is a Tesseract dictionary
    if is_tess_dict(ocr_dict):
        # Convert to Pandas DataFrame (not sure if this is required to filter out data but it works)
        df_text = pd.DataFrame.from_dict(ocr_dict)

        if len(df_text) > 0:
            # Group up words in same lines
            lines_grouped = df_text.groupby(
                ["level", "page_num", "block_num", "par_num", "line_num"]
            )

            # Loop thru the lines to find tallest line
            for i, line in lines_grouped:
                full_line = "_".join(line["text"])
                logger.debug(
                    "Line to inspect: %s [%3i,%4i] %s",
                    i,
                    line["height"].max(),
                    line["width"].sum(),
                    full_line,
                )

                # Stop if line contains certain words as defined above
                # They usually appear after the deceased name
                text_found = find_regex_in_string(full_line, break_words)
                if bool(text_found):
                    logger.debug("Found break word")
                    break

                # Ignore line with to few or to many words,
                # names considered to be between 2 and 5 words
                if len(line["text"]) not in range(2, 6):
                    logger.debug("Too few or too many words")
                    continue

                # Ignore full lines containing certain words as they are often false finds
                text_found = find_regex_in_string(full_line, ignore_words)
                if bool(text_found):
                    logger.debug("Ignoring line")
                    continue

                # Ignore lines taller than defined height
                if line["height"].max() > 120:
                    logger.debug("Line height too high")
                    continue

                # Check if line is taller or equal than already found tallest line
                if line["height"].max() >= max_height:
                    max_height = line["height"].max()
                    line_with_name = full_line
                    logger.debug("^^^^^^ Tallest so far ^^^^^^")

            logger.debug("%15s: %s", "Tallest name", line_with_name)

            # Clean out the tallest text found
            line_with_name = re.sub("_+?", "_", line_with_name)
            line_with_name = re.sub("_-_", "_", line_with_name)
            line_with_name = re.sub("-_", "_", line_with_name)
            line_with_name = re.sub("_-", "_", line_with_name)

            # Remove words that should not be considered from the line
            line_with_name = re.sub(
                rf"({remove_text})_",
                "",
                line_with_name,
                flags=re.IGNORECASE,
            ).strip()
            logger.debug("%15s: %s", "Clean name", line_with_name)

            first_name, last_name = split_full_name(line_with_name)

    logger.debug("%15s: %s", "first name", first_name)
    logger.debug("%15s: %s", "last name", last_name)

    return first_name, last_name


def find_regex_in_string(text_to_search: str, search_text: str, flag: str = "I") -> str:
    """
    Find regular expression in text

    Parameters:
      text_to_search (str): The text to look in to
      search_text (str): regex to look for
      flag (str): default is ignore case, unless otherwise provided

    Return:
      result (str): Text found
    """
    # Remove emojis
    search_text = emoji.replace_emoji(search_text, replace="")

    # Compile regex
    regex = re.compile(search_text, flags=re.IGNORECASE)
    if flag != "I":
        regex = re.compile(search_text)
    # Search text with regex
    result = regex.search(text_to_search)

    return result


def finditer_regex_in_string(text_to_search, search_text):
    """
    Find regular expression in text and return iterable

    Parameters:
      text_to_search (str): The text to look in to
      search_text (str): regex to look for

    Return:
      result (iterator): Text found
    """
    # Remove emojis
    text_to_search = emoji.replace_emoji(text_to_search, replace="")
    search_text = emoji.replace_emoji(search_text, replace="")

    # Compile regex
    regex = re.compile(search_text, flags=re.IGNORECASE)
    # Search text with regex
    result = regex.finditer(text_to_search)

    return result


def join_data(data: list) -> str:
    """
    Join list data into one string, using underscore as spaces.
    If data is a string, spaces and newlines are replaced with underscores.
    Then some cleanup is performed for certain situations.

    Parameters:
      data (list|string): A list or string

    Return:
      String
    """

    if isinstance(data, list):
        joined_text = "_".join(data)
    elif isinstance(data, str):
        joined_text = re.sub(r"\s+", r"_", data)
    else:
        logger.debug("No text joined.")
        return ""

    # joined_text = re.sub(r"_-_", r"-", joined_text)
    # joined_text = re.sub(r"-_", r"-", joined_text)
    # joined_text = re.sub(r"°_(\d)", r"°\g<1>", joined_text)
    # joined_text = re.sub(r"°_", r"°", joined_text)
    # joined_text = re.sub(r"\+_(\d)", r"+\g<1>", joined_text)
    # joined_text = re.sub(r"\+_", r"", joined_text)
    joined_text = re.sub(r"_+", r"_", joined_text)

    # Remove emojis
    joined_text = emoji.replace_emoji(joined_text, replace="")

    logger.debug("%15s : %s", "Joined text len", len(joined_text))
    logger.debug("%15s : %s", "Joined text", joined_text)

    return joined_text


def validate_day(day):
    """
    Validates that the input is a day number within the range 1 to 31.

    Parameters:
        day (str | int): The day to validate, either as a string or an integer.

    Returns:
        int | None: The day as an integer if it is within the valid range;
                         otherwise, None.
    """

    logger.debug("%15s: %s", "Original", day)
    try:
        # Attempt to convert the input to an integer
        day = int(day)
    except (ValueError, TypeError):
        logger.debug("%15s: %s", "Failure", "INT conversion")

        # Return None if conversion fails
        return None

    # Check if the day is within the valid range
    if 1 <= day <= 31:
        logger.debug("%15s: %s", "Valid", day)

        return day

    logger.debug("%15s: %s", "Not valid", day)

    return None


def validate_month(month):
    """
    Converts the month name in Dutch, French, or English to a month number,
    or validates an integer month.

    Parameters:
        month (str | int): The month to validate, either as a string or integer.

    Returns:
        int | None: The month as an integer if it is valid (1-12); otherwise, None.
    """

    logger.debug("%15s: %s", "Original", month)

    # Dictionary to map month names in various languages to their respective month numbers
    month_map = {
        "haardmaand": 1,
        "jan": 1,
        "januaeri": 1,
        "januari": 1,
        "january": 1,
        "janvier": 1,
        "louwmaand": 1,
        "nieuwjaarmaand": 1,
        "nieuwjaermaend": 1,
        "nivôse": 1,
        "sneeuwmaand": 1,
        "feb": 2,
        "februaeri": 2,
        "februari": 2,
        "february": 2,
        "février": 2,
        "kortemaand": 2,
        "kortemaend": 2,
        "pluviôse": 2,
        "regenmaand": 2,
        "schrikkelmaand": 2,
        "slijkmaand": 2,
        "sprokkelmaand": 2,
        "buienmaand": 3,
        "dorremaand": 3,
        "guldenmaand": 3,
        "kalvermaand": 3,
        "lentemaand": 3,
        "maa": 3,
        "maart": 3,
        "maerte": 3,
        "maertemaend": 3,
        "mar": 3,
        "march": 3,
        "mars": 3,
        "meert": 3,
        "sint-josephsmaand": 3,
        "ventôse": 3,
        "windmaand": 3,
        "apr": 4,
        "aprii": 4,
        "april": 4,
        "arlekijnmaand": 4,
        "avr": 4,
        "avril": 4,
        "eierenmaand": 4,
        "eiermaand": 4,
        "germinal": 4,
        "grasmaand": 4,
        "harlekijnmaand": 4,
        "kiemmaand": 4,
        "paasmaand": 4,
        "paesmaend": 4,
        "bidmaand": 5,
        "bloeiemaand": 5,
        "bloeimaand": 5,
        "floréal": 5,
        "mai": 5,
        "mariamaand": 5,
        "may": 5,
        "mei": 5,
        "meie": 5,
        "meimaend": 5,
        "met": 5,
        "wonnemaand": 5,
        "jun1": 6,
        "braakmaand": 6,
        "braammaand": 6,
        "garsmaend": 6,
        "juin": 6,
        "jun": 6,
        "june": 6,
        "juni": 6,
        "juuny": 6,
        "prairial": 6,
        "rozenmaand": 6,
        "weidemaand": 6,
        "zomermaand": 6,
        "hooimaand": 7,
        "juillet": 7,
        "jul": 7,
        "juli": 7,
        "jullietmaend": 7,
        "july": 7,
        "juuly": 7,
        "messidor": 7,
        "vennemaand": 7,
        "août": 8,
        "arenmaand": 8,
        "aug": 8,
        "august": 8,
        "augusti": 8,
        "augustus": 8,
        "hittemaand": 8,
        "koornmaand": 8,
        "oegst": 8,
        "oegstmaend": 8,
        "oogst": 8,
        "oogstmaand": 8,
        "ougstmaend": 8,
        "thermidor": 8,
        "fructidor": 9,
        "fruitmaand": 9,
        "gerstmaand": 9,
        "haevermaend": 9,
        "havermaand": 9,
        "herfstmaand": 9,
        "sep": 9,
        "september": 9,
        "septembre": 9,
        "vruchtmaand": 9,
        "aarzelmaand": 10,
        "oct": 10,
        "october": 10,
        "octobre": 10,
        "okt": 10,
        "oktober": 10,
        "oktoober": 10,
        "rozenkransmaand": 10,
        "vendémiaire": 10,
        "wijnmaand": 10,
        "wynmaend": 10,
        "zaaimaand": 10,
        "bloedmaand": 11,
        "brumaire": 11,
        "loefmaand": 11,
        "mistmaand": 11,
        "nevelmaand": 11,
        "nov": 11,
        "november": 11,
        "novembermaend": 11,
        "novembre": 11,
        "slachtmaand": 11,
        "smeermaand": 11,
        "dec": 12,
        "déc": 12,
        "december": 12,
        "décembre": 12,
        "donkeremaand": 12,
        "frimaire": 12,
        "kerstmaand": 12,
        "midwintermaand": 12,
        "rijpmaand": 12,
        "wintermaand": 12,
        "wintermaend": 12,
        "wolfsmaand": 12,
    }

    try:
        # Attempt to convert the input to an integer
        month = int(month)
        if 1 <= month <= 12:
            logger.debug("%15s: %s", "Valid (int)", month)

            return month
        logger.debug("%15s: %s", "Not valid (int)", month)

        return None
    except (ValueError, TypeError):
        logger.debug("%15s: %s", "Maybe string", month)
        # Check if the input is a string and convert it to a month number
        if isinstance(month, str):
            # Remove possible wrong characters
            month = re.sub(r"[-#+_]", "", month)
            month_number = month_map.get(month.lower())
            if month_number:
                logger.debug("%15s: %s", "Valid (str)", month_number)

                return month_number

    # Return None for invalid inputs
    logger.debug("%15s: %s", "Not valid", month)

    return None


def validate_year(year):
    """
    Verifies that the year is within a valid range (1700 to the current year)

    Parameters:
        year (str | int): The year to validate, either as a string or integer.

    Returns:
        int | None: The year as an integer if it is within the valid range; otherwise, None.
    """

    logger.debug("%15s: %s", "Original", year)

    # Directly access the year from datetime
    current_year = datetime.now().year

    try:
        # Attempt to convert the input to an integer
        year = int(year)
    except (ValueError, TypeError):
        logger.debug("%15s: %s", "Failure", "INT conversion")

        # Return None if conversion fails
        return None

    # Check if the year is within the valid range
    if 1700 <= year <= current_year:
        logger.debug("%15s: %s", "Valid", year)

        return year

    logger.debug("%15s: %s", "Not valid", year)

    return None


def clean_city_names(city_to_clean):
    """
    Clean up some city names

    Parameters:
      city_to_clean (str): City name to clean

    Return:
      city_to_clean (str): Cleaned up city name
    """

    logger.debug("%15s: %s", "Original", city_to_clean)
    # Clean it up
    city_to_clean = city_to_clean.title()
    city_to_clean = re.sub(r"(St |St_)", "Sint ", city_to_clean)
    city_to_clean = re.sub(r"St-|St_-|Sint -|Sint_-", "Sint-", city_to_clean)
    city_to_clean = re.sub(r"Ste-", "Sinte-", city_to_clean)
    city_to_clean = re.sub(r"^\'S-", "'s-", city_to_clean)
    city_to_clean = re.sub(r"-Aan-", "-aan-", city_to_clean)
    city_to_clean = re.sub(r"-Op-", "-op-", city_to_clean)
    city_to_clean = re.sub(r"-De-", "-de-", city_to_clean)
    city_to_clean = re.sub(r"-Den-", "-den-", city_to_clean)
    city_to_clean = re.sub(r"-In-", "-in-", city_to_clean)
    city_to_clean = re.sub(r"-Ter-", "-ter-", city_to_clean)
    city_to_clean = re.sub(r"-Ten-", "-ten-", city_to_clean)
    city_to_clean = re.sub(r"^(Op|Haar|Zijn|Een)$", "", city_to_clean)
    city_to_clean = re.sub(r"_", " ", city_to_clean)
    city_to_clean = re.sub(r"Ij", "IJ", city_to_clean)

    # Check against city corrections, use original if not found
    city_to_clean = dict_city_corrections.get(city_to_clean, city_to_clean)

    logger.debug("%15s: %s", "Cleaned", city_to_clean)

    return city_to_clean


def insert_space(obituary, item=None):
    """
    Places a space between a lower case letter followed by an upper case letter
    Example: DeWever -> De Wever

    Parameters:
      obituary (Obituary class)
      item (str): defines the class attribute to convert

    Return:
      obituary (Obituary class): updated obituary
    """

    if item is not None:
        try:
            attribute = getattr(obituary, item)
            attribute = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", attribute)
            setattr(obituary, item, attribute)
            logger.debug("%15s: %s", "Converted to", attribute)
        except AttributeError:
            logger.debug("%15s: %s", "Wrong attribute", item)
    else:
        logger.debug("%s", "No attribute given")

    return obituary


def insert_single_quote(obituary, item=None):
    """
    Places a single quote between two consecutive upper case letters
    Example: DHondt -> D'Hondt

    Parameters:
      obituary (Obituary class)
      item (str): defines the class attribute to convert

    Return:
      obituary (Obituary class): updated obituary
    """

    if item is not None:
        try:
            attribute = getattr(obituary, item)
            attribute = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "'", attribute)
            setattr(obituary, item, attribute)
            logger.debug("%15s: %s", "Converted to", attribute)
        except AttributeError:
            logger.debug("%15s: %s", "Wrong attribute", item)
    else:
        logger.debug("%s", "No attribute given")

    return obituary


def clear_attribute(obituary, item=None):
    """
    Set provided item to empty string

    Parameters:
      obituary (Obituary class)
      item (str): defines the class attribute to convert

    Return:
      obituary (Obituary class): updated obituary
    """

    if item is not None:
        try:
            setattr(obituary, item, "")
            logger.debug("%15s: %s", "Converted to:", "empty string")
        except AttributeError:
            logger.debug("%15s: %s", "Unknown attribute", item)
    else:
        logger.debug("%s", "No attribute given")

    return obituary


def find_info_in_filepath(obituary, db_session):
    """
    Extract info from filepath using naming templates associated with
    the division and type of document
    Update the Obituary class with found information

    Parameters:
      obituary (Obituary class)
      db_session (database session)

    Return:
      obituary (Obituary class): updated obituary
    """

    logger.debug("%15s: %s", "Filename", obituary.file_base_name)

    # Look up template in db
    file_read_template = get_file_template(db_session, obituary, "read")

    if len(file_read_template) > 0:
        regex_template = convert_template(file_read_template, "regex")
        regex_find = find_regex_in_string(obituary.file_base_name, regex_template)
        # logger.debug("%15s: %s", "part count", len(regex_find))

        named_template = convert_template(file_read_template, "named")
        template_parts = finditer_regex_in_string(named_template, r"\{(.+?)\}")
        # logger.debug("%15s: %s", "part count", len(template_parts))

        if template_parts and regex_find:
            for i, template_part in enumerate(template_parts):
                logger.debug(
                    "%15s: %s: %s",
                    "Original",
                    template_part.group(1),
                    regex_find.group(i + 1),
                )
                # Update the Obituary attribute
                setattr(obituary, template_part.group(1), regex_find.group(i + 1))

                # Correct where necessary
                match template_part.group(1):
                    case "last_name":
                        insert_space(obituary, "last_name")
                        insert_single_quote(obituary, "last_name")
                    case "first_name":
                        insert_space(obituary, "first_name")
                        insert_single_quote(obituary, "first_name")
                    case "birth_year" | "death_year":
                        if validate_year(regex_find.group(i + 1)) is None:
                            clear_attribute(obituary, template_part.group(1))
                    case "birth_month" | "death_month":
                        if validate_month(regex_find.group(i + 1)) is None:
                            clear_attribute(obituary, template_part.group(1))
                    case "birth_day" | "death_day":
                        if validate_day(regex_find.group(i + 1)) is None:
                            clear_attribute(obituary, template_part.group(1))
                    case _:
                        # Clear out zeros in date parts
                        if regex_find.group(i + 1) in ["0000", "00"]:
                            clear_attribute(obituary, template_part.group(1))

                logger.debug(
                    "%15s: %s: %s",
                    "Correction",
                    template_part.group(1),
                    getattr(obituary, template_part.group(1)),
                )
            logger.debug("Extraction complete")
        else:
            logger.debug("Extraction not complete")

    return obituary


def custom_escape(string_to_escape, exclude=""):
    """
    Escapes regex characters in a string except for some excluded characters

    Parameters:
      string_to_escape (str)
      exclude (str)

    Return:
      (str): Custom escaped string
    """

    logger.debug("%15s: %s", "Original", string_to_escape)
    escaped = []
    for char in string_to_escape:
        # Check if the character is special in regex and not in the exclude list
        if re.escape(char) != char and char not in exclude:
            escaped.append(f"\\{char}")
        else:
            escaped.append(char)
    escaped_string = "".join(escaped)
    logger.debug("%15s: %s", "Escaped", escaped_string)

    return escaped_string


def convert_template(template, to_format="regex"):
    """
    Convert a template string to regex or named string

    Parameters:
      template (str): template to convert
      to_format (str): the word regex or named

    Return:
      template (str): converted template
    """


    match to_format:
        case "regex":
            # Get first single separator character from template
            separator_found = find_regex_in_string(template, r"[\}\]](.?)[\{\[]")
            if separator_found is None:
                separator_character = r"[^0-9a-zéèëêçô]"
            else:
                separator_character = f"\\{separator_found[1]}"
            logger.debug("%15s: %s", "separator", separator_character)

            # Make sure reserved regex items are escaped
            template = custom_escape(template, exclude=r"[]{}")

            # Template to regex options
            template_placeholders_conversion = {
                r"{fo}": r"(.+?)",  #            folder
                r"{dv}": r"(.+?)",  #            division
                r"{y}": r"(\d\d\d\d)",  #        year
                r"{m}": r"(\d\d)",  #            month
                r"{d}": r"(\d\d)",  #            day
                r"{ln}": r"(.+?)",  #            last name
                r"{fn}": r"(.+?)",  #            first name
                r"{bp}": r"(.+?)",  #            birth place
                r"{by}": r"(\d\d\d\d)",  #       birth year
                r"{bm}": r"(\d\d)",  #           birth month
                r"{bd}": r"(\d\d)",  #           birth day
                r"{dp}": r"(.+?)",  #            deceased place
                r"{dy}": r"(\d\d\d\d)",  #       deceased year
                r"{dm}": r"(\d\d)",  #           deceased month
                r"{dd}": r"(\d\d)",  #           deceased day
                r"{dt}": r"(RB|BP|OB|KB|KO)",  # document type
                r"{dn}": r"(\d+?)",  #           document number
                r"{bn}": r"(\d*?)",  #           box number
                r"{g}": r"(M|V|X)",  #           gender
                r"{p}": r"(foto)",  #            portrait picture is available
                r"{n}": r"(.+?)",  #             notes
            }
        case "named":
            # Template to Obituary field options
            template_placeholders_conversion = {
                r"{fo}": r"{folder_name}",
                r"{dv}": r"{division}",
                r"{y}": r"{year}",
                r"{m}": r"{month}",
                r"{d}": r"{day}",
                r"{ln}": r"{last_name}",
                r"{fn}": r"{first_name}",
                r"{bp}": r"{birth_place}",
                r"{by}": r"{birth_year}",
                r"{bm}": r"{birth_month}",
                r"{bd}": r"{birth_day}",
                r"{dp}": r"{death_place}",
                r"{dy}": r"{death_year}",
                r"{dm}": r"{death_month}",
                r"{dd}": r"{death_day}",
                r"{dt}": r"{obituary_type}",
                r"{dn}": r"{document_number}",
                r"{bn}": r"{box_number}",
                r"{g}": r"{gender}",
                r"{p}": r"{face}",
                r"{n}": r"{note}",
            }
        case _:
            # Not a valid conversion method
            logger.debug("%s not a valid conversion method", to_format)

            return ""

    # Replace template with regex or Obituary filed options
    for placeholder, regex in template_placeholders_conversion.items():
        template = template.lower().replace(placeholder, regex)

    # Do some cleanup
    match to_format:
        case "regex":
            # Fix optional parts between square brackets []
            template = template.replace(r"[", r"(")
            template = template.replace(r"]", r")?")
            # Match template from beginning, anything trailing should be ignored
            # template = f"^{template.lower()}(?=$|[^0-9a-zéèëêçô])" -- original
            template = f"^{template.lower()}(?=$|{separator_character})"
        case "named":
            # Fix optional parts between square brackets []
            template = template.replace(r"[", "")
            template = template.replace(r"]", "")
    logger.debug("%15s: %s", to_format, template)

    return template


def replace_strings(
    original_string: string, target_strings: list, replacement: string
) -> str:
    """
    Replace all occurrences of strings in text with a replacement text.

    Parameters:
        original_string (str): The original string where replacements need to be made.
        target_strings (list): A list of target strings to be replaced.
        replacement (str): The string that will replace all occurrences of the target strings.

    Return:
        A modified string with all target strings replaced, or original_string if empty.

    """
    # Inspired by ChatGPT

    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    # Preprocess both original_string and replacement to account for underscores
    # unless replacement is the underscore character itself
    if replacement != "_":
        preprocessed_original = original_string.lower().replace(" ", "_")
        preprocessed_replacement = replacement.lower().replace(" ", "_")
        # If the replacement (with underscores) is already in the preprocessed original_string,
        #  return the original string as there is no need to do the replacement
        if preprocessed_replacement in preprocessed_original:
            return original_string

    # Filter out empty strings from the target_strings list
    filtered_targets = [target for target in target_strings if target]

    # If the target_strings list is empty after filtering, return the original string
    if not filtered_targets:
        return original_string

    # Escape special characters in target strings to ensure regex safety
    escaped_targets = [re.escape(target) for target in filtered_targets]

    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    #   is there a re.sub maximum pattern size?
    #   looks like some replacements are not done
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # # Join the escaped targets into a single pattern for regex search
    # pattern = "|".join(escaped_targets)

    # # Use re.sub to replace all occurrences of the target strings with the replacement
    # modified_string = re.sub(pattern, replacement, original_string, flags=re.IGNORECASE)

    # Replace for each individual target
    modified_string = original_string
    for target in escaped_targets:
        modified_string = re.sub(
            target, replacement, modified_string, flags=re.IGNORECASE
        )

    return modified_string


def normalize_life_info(original_string: str) -> str:
    """
    Apply some cleanup to life info

    Parameters:
        original_string (str): The string to replace words in

    Return:
        A modified string with all target strings replaced, or original_string if empty.
    """
    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    normalized_text = remove_unnecessary_text(original_string)
    normalized_text = normalize_birth_text(normalized_text)
    normalized_text = normalize_death_text(normalized_text)
    normalized_text = normalize_location_text(normalized_text)

    return normalized_text


def remove_unnecessary_text(original_string: str) -> str:
    """
    Remove specific words listed from a string

    Parameters:
        original_string (str): The string to replace words in

    Return:
        A modified string with all target strings replaced, or original_string if empty.
    """

    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    # Remove emojis
    original_string = emoji.replace_emoji(original_string, replace="")

    # Strings to replace
    target_strings = [
        "_en_",
        "_in_den_",
        "_in_de_",
        "_in_het_",
        "_op_de_",
        "_na_een_",
        "_is_",
        "_te_zijn_",
        "_in_zijn_",
        "_in_haar_",
        "_tot_zijn_",
        "_tot_haar_",
        "_van_zijn_",
        "_van_haar_",
        "_zijn_",
        "_haar_",
        "_van_ons_",
        "_van_een_",
        "_door_",
        "_veel_",
        "_thuis_",
        "_woning_",
        "_in_az_",
        "_in_wzc_",
        "_in_residentie_",
        "_in_huiselijke_kring_",
        "_in_huiskring_",
        "_in_familiekring_",
        "_in_thuiskring_",
        "_in_woonzorghuis_",
        "_in_home_",
        "_ten_huize_",
        "_omringd_",
        "_gesteund_",
        "_schielijk_",
        "_te_vroeg_",
        "_in_volle_",
        "_ongeval_",
        "_smartelijk_",
        "_onverwacht_",
        "_zachtjes_",
        "_zacht_",
        "_rustig_",
        "_godvruchtig_",
        "_god_",
        "_vruchtig_",
        "_god-vruchtig_",
        "_kristelijk_",
        "_heer_",
        "_ziekenhuis_",
        "_kliniek_",
        "_hospitaal_",
        "_revalidatiecentrum_",
        "_woonzorgcentrum_",
        "_woon-_zorgcentrum_",
        "_zorgcentrum_",
        "_familie_",
        "_stadskliniek_",
        "_rusthuis_",
        "_tengevolge_",
        "_langdurige_",
        "_ziekte_",
        "_liefdevol_",
        "_vredevol_",
        "_plots_",
        "_plotseling_",
        "_stichtend_",
        "_verkeersongeval_",
        "_tragisch_",
        "_haastig_",
        "_vroom_",
        "_pijnlijk_",
        "_schepper_",
        "_naar_het_vaderhuis_",
        "_az_",
        "_wzc_",
        "_strijd_",
        "_van_Lourdes_",
        "_levensjaar_",
        "_kinderen_",
        "_vrede_",
        "_in_gods_",
        "_van_christus_",
        "_aan_de_liefde_",
        "_ouders_",
    ]

    # FR
    target_strings += [
        "_et_",
        "_accidentellement_",
    ]

    # DE
    # target_strings += ["_gestorben_", "_entschlafen_"]

    # UK
    # target_strings += ["_died_"]

    # Special
    target_strings += ["_+_", "_†_", "_t_"]
    target_strings += ["_°_", "_*_"]
    target_strings += ["_°", "_*"]
    target_strings += ["_+", "_†"]

    modified_string = replace_strings(original_string, target_strings, "_")

    logger.debug("%15s: %s", "Text cleaned", modified_string)

    return modified_string


def normalize_birth_text(original_string: str) -> str:
    """
    Normalize words listed in function to the word 'geboren'

    Parameters:
        original_string (str): The string to replace words in

    Return:
        A modified string with all target strings replaced, or original_string if empty.
    """

    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    # logger.debug("%15s: %s", "Original", original_string)
    # Strings to replace
    # NL
    target_strings = [
        "_gebore_",
        "_hij_zag_het_levenslicht_",
        "_tot_het_leven_geroepen_",
    ]

    # FR
    target_strings += ["_née_", "_né_", "_naquit_"]

    # DE
    # Is same as Dutch: geboren

    # UK
    target_strings += ["_born_"]

    # Special
    # target_strings += ["_°_", "_*_"]

    modified_string = replace_strings(original_string, target_strings, "_geboren_")
    # logger.debug("%15s: %s", "Modified Final", modified_string)

    return modified_string


def normalize_death_text(original_string: str) -> str:
    """
    Normalize words listed in function to the word 'overleden'

    Parameters:
        original_string (str): The string to replace words in

    Return:
        A modified string with all target strings replaced, or original_string if empty.
    """

    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    # Strings to replace
    # NL
    target_strings = [
        "_overleed_",
        "_ontslapen_",
        "_ontsliep_",
        "_heengegaan_",
        "_gestorven_",
        "_ingeslapen_",
        "_teruggekeerd_",
        "_ontslaapt_",
        "_stierf_",
        "_herboren_",
        "_sterft_",
        "_ten_hemel_gevaren_",
        "_ging_over_",
        "_overgegaan_",
        "_verongelukt_",
        "_gesneuveld_",
        "_ontrukt_",
        "_ontnomen_",
        "_naar_het_vaderhuis_terug",
    ]

    # FR
    target_strings += [
        "_fusillé_",
        "_endormie_",
        "_rejoint_",
        "_décédée_",
        "_décédé_",
        "_decedee_",
        "_decede_",
        "_décéda_",
        "_mourut_",
    ]

    # DE
    target_strings += ["_gestorben_", "_entschlafen_"]

    # UK
    target_strings += ["_died_"]

    # Special
    # target_strings += ["_+_", "_†_", "_t_"]

    modified_string = replace_strings(original_string, target_strings, "_overleden_")

    return modified_string


def normalize_location_text(original_string: str) -> str:
    """
    Normalize words listed in function to the word 'te' or 'er'

    Parameters:
        original_string (str): The string to replace words in

    Return:
        A modified string with all target strings replaced, or original_string if empty.
    """

    # If original_string is empty, return it as is
    if not original_string:
        return original_string

    # logger.debug("%15s: %s", "Original", original_string)
    # Strings to replace
    # NL
    target_strings = ["_aldaar_", "_aldaer_", "_daar_", "_alwaar_", "_el_"]
    # FR
    target_strings += ["_y_"]
    # DE
    # target_strings += ["_y_"]
    # UK
    # target_strings += ["_y_"]

    modified_string = replace_strings(original_string, target_strings, "_er_")

    # Strings to replace
    # NL
    target_strings = ["_in_", "_van_"]
    # FR
    target_strings += ["_à_", "_a_"]
    # DE
    # target_strings += ["_y_"]
    # UK
    # target_strings += ["_y_"]

    modified_string = replace_strings(modified_string, target_strings, "_te_")

    # logger.debug("%15s: %s", "Modified Final", modified_string)

    return modified_string


def find_life_info(obituary, db_session):
    """
    Extract birth and death info from string of text in obituary attribute

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (DB session)

    Return:
      obituary (Obituary object): updated obituary object
    """

    # START Test section : find life info
    # Normalize text to hold just the correct strings to make searches easier
    # Replace different words with one common word, e.g. heengegaan > overleden
    normalized_text = remove_unnecessary_text(obituary.ocr_text)
    normalized_text = normalize_birth_text(normalized_text)
    normalized_text = normalize_death_text(normalized_text)
    normalized_text = normalize_location_text(normalized_text)

    # Find complex info
    # regex:
    # r"(_geboren.*?\d{4})((?:.*?_overleden.*?\d{4})?(?:.*?\d{4}.*?_overleden)?)"
    # better regex: ?
    #   catches more if place comes after dates?
    #   Assumes place starts with capital letter
    # (_geboren.*?\d{4}(?:_te_[A-Z][a-zA-Z]*)?)((?:.*?_overleden.*?\d{4})?
    #   (?:.*?\d{4}.*?_overleden)?(?:.*?_te_[A-Z][a-zA-Z]*)?)
    # group 1
    regex = r"(_geboren.*?\d{4}(?:_te_[A-Z][a-zA-Z]*)?)"
    # group 2
    regex += r"((?:.*?_overleden.*?\d{4})?(?:.*?\d{4}.*?_overleden)?(?:.*?_te_[A-Z][a-zA-Z]*)?)"

    life_text_found = find_regex_in_string(normalized_text, regex, flag="N")
    if bool(life_text_found):
        logger.debug("%15s: %s", "Life info g0", life_text_found.group(0))

        logger.debug("%15s: %s", "Life info g1", life_text_found.group(1))
        birth_place = extract_location(
            life_text_found.group(1), check_string="_geboren"
        )
        logger.debug("%15s: %s", "B.Place", birth_place)

        logger.debug("%15s: %s", "Life info g2", life_text_found.group(2))

        # Assume death_place is birth_place, correct later on
        death_place = birth_place
        # Find the first occurrence of "_er_" (case-insensitive)
        er_index = life_text_found.group(2).find("_er_")
        # If "_er_" is not found, get the place
        if er_index == -1:
            death_place = extract_location(
                life_text_found.group(2), check_string="_overleden"
            )
        logger.debug("%15s: %s", "D.Place", death_place)
    else:
        logger.debug("%15s: %s", "Life info", "not found")
    # END Test section : find life info

    # Update Obituary object with compact date information from OCR
    find_compact_dates(obituary)

    # Update Obituary object with birth information from OCR
    find_birth_info(obituary)

    # Update Obituary object with death information from OCR
    find_death_info(obituary)

    return obituary


def find_compact_dates(obituary):
    """
    Extract compact dates info from string of text in obituary attribute
    e.g. 29 september 1884 - 20 juli 1967

    Parameters:
      obituary (Obituary object): initial obituary information

    Return:
      obituary (Obituary object): update obituary object
    """

    # Find compact dates
    # Test (3) new regex 2025-05-17
    #    => group(0): _24_juni_1926_<some text|-|+>_5_7_2024_
    #    => group(1): 24_juni_1926
    #    => group(2): 5_7_2024
    regex = r"_(\d{1,2}_(?:[a-z]+|\d{1,2})_\d{4})"
    regex += r"_?[a-z-†\+]*_(\d{1,2}_(?:[a-z]+|\d{1,2})_\d{4})_"

    compact_dates_found = find_regex_in_string(obituary.ocr_text, regex)
    if compact_dates_found:
        logger.debug("%15s: %s", "Compact dates 3", compact_dates_found.group(0))
        logger.debug("%15s: %s", "Compact dates 3", compact_dates_found.group(1))
        logger.debug("%15s: %s", "Compact dates 3", compact_dates_found.group(2))
    else:
        logger.debug("%15s: %s", "Compact dates", "not found")

    return obituary


def extract_city(text, fallback_city=None):
    """
    Extract the city from the given text. Returns fallback_city if no city is found.
    """
    regex_same_city = r"_(?:er|aldaar|daar|alwaar|y|el)_"
    regex_city = r"(?:te|in|van|à|a)_((?:(?:de|st|sint)_)?.*?)_.*?\d{4}"

    if find_regex_in_string(text, regex_same_city):
        return fallback_city or ""

    match = find_regex_in_string(text, regex_city)
    return clean_city_names(match.group(1)) if match else ""


def extract_date(text):
    """
    Extract day, month, and year from the text.
    """
    regex_date = r"_(\d{1,2})_([a-zA-Z]+|\d{1,2})_(\d{4})"
    match = find_regex_in_string(text, regex_date)

    if match:
        return (
            validate_day(match.group(1)),
            validate_month(match.group(2)),
            validate_year(match.group(3)),
        )
    return None, None, None


def update_obituary(obituary, life_event, city, day, month, year):
    """
    Update the obituary object with extracted information.
    """
    if life_event == LifeEvent.BIRTH:
        obituary.birth_place = city or obituary.birth_place
        obituary.birth_day = day or obituary.birth_day
        obituary.birth_month = month or obituary.birth_month
        obituary.birth_year = year or obituary.birth_year
        logger.debug("%15s: %s (%s-%s-%s)", "Birth Info", city, year, month, day)
    else:
        obituary.death_place = city or obituary.death_place
        obituary.death_day = day or obituary.death_day
        obituary.death_month = month or obituary.death_month
        obituary.death_year = year or obituary.death_year
        logger.debug("%15s: %s (%s-%s-%s)", "Death Info", city, year, month, day)


def find_life_event_info_chatgpt(obituary, life_event=LifeEvent.BIRTH):
    """
    !!!! UNTESTED 2025-04-19 !!!!
    Inproved version of find_life_event_info_kdo(), by ChatGPT
    Extract birth or death information from an obituary's text.

    Parameters:
      obituary (Obituary): The obituary object containing OCR text and attributes.
      life_event (LifeEvent): The type of life event to extract (default: LifeEvent.BIRTH).

    Returns:
      Obituary: Updated obituary object with extracted life event information.
    """

    if not isinstance(life_event, LifeEvent):
        logger.error("%15s: %s", "Invalid life event", life_event)

        return obituary

    logger.debug("%15s: %s", "Life event", life_event.value.capitalize())

    # Normalize text to hold just the correct strings to make searches easier
    # Replace different words with one common word, e.g. heengegaan > overleden
    normalized_text = normalize_life_info(obituary.ocr_text)

    # Regex patterns --- kdo: doesn't seem OK 2025-04-20
    birth_pattern = r"((?:_geboren).*?(?:17|18|19|20)\d{1,2})"
    death_pattern = r"(?:_geboren).*?(?:17|18|19|20)\d{1,2}"
    death_pattern += r"(.*?_(?:overleden).*?(?:17|18|19|20)\d{1,2})"

    regex = birth_pattern if life_event == LifeEvent.BIRTH else death_pattern

    text_found = find_regex_in_string(normalized_text, regex)
    if not text_found:
        logger.debug("No matching text found for life event.")

        return obituary

    text_cleaned = remove_unnecessary_text(text_found.group(1))

    # Extract city
    city = extract_city(
        text_cleaned, obituary.birth_place if life_event == LifeEvent.DEATH else None
    )

    # Extract date
    day, month, year = extract_date(text_cleaned)

    # Update obituary object
    update_obituary(obituary, life_event, city, day, month, year)

    return obituary


def find_life_event_info_kdo(obituary, life_event="birth"):
    """
    !!!! NEW !!!! UNTESTED 2025-04-19 !!!!
    Extract birth info from string of text in obituary attribute

    Parameters:
      obituary (Obituary object): initial obituary information
      life_event (str): either birth (default) or death

    Return:
      obituary (Obituary object): updated obituary object
    """

    life_event = life_event.lower()
    if life_event not in {"birth", "death"}:
        logger.debug("%15s: %s", "Life event", "unknown")

        return obituary

    city = ""
    year = None
    month = None
    day = None

    logger.debug("%15s: %s", "Life event", life_event)
    if life_event == "birth":
        # Find birth segment
        regex = r"("
        regex += r"(?:_(?:geboren|née|né|°))"
        regex += r".*?"
        regex += r"(?:17|18|19|20)_?\d_?\d"
        regex += r")"
    else:
        # Find death segment
        regex = r"(?:"
        regex += r"(?:_(?:né|née|geboren|°))"
        regex += r".*?"
        regex += r"(?:17|18|19|20)_?\d_?\d"
        regex += r")"
        regex += r"("  # group 1
        regex += r".*?"
        regex += r"(?:_(?:overleden|overleed|ontslapen|ontsliep|heengegaan|ontnomen|"
        regex += r"gestorven|ingeslapen|teruggekeerd|décédé|décédée|rejoint|ontrukt|"
        regex += r"ontslaapt|stierf|herboren|sterft|decede|decedee|fusillé|gesneuveld|"
        regex += r"ten_hemel_gevaren|ging_over|overgegaan|endormie|verongelukt|\+|†))"
        regex += r".*?"
        regex += r"(?:17|18|19|20)_?\d_?\d"
        regex += r")"  # end group 1

    text_found = find_regex_in_string(obituary.ocr_text, regex)

    if text_found:
        text_found = text_found.group(1)
        logger.debug("%15s: %s", "Text found", text_found)

        # Remove specific words from string as they might interfere
        text_cleaned = remove_unnecessary_text(text_found)

        # Extract city
        # Check if city of demise should be same as birth city
        regex = r"_(er|aldaar|aldaer|daar|alwaar|y|el)_"
        regex_return = find_regex_in_string(text_cleaned, regex)
        if regex_return:
            city = obituary.birth_place
        else:
            regex = r"(?:te|in|van|à|a)_((?:(?:de|st|sint)_)?.*?)_"
            regex += r".*?"
            regex += r"\d{4}"
            regex_return = find_regex_in_string(text_cleaned, regex)
            if regex_return:
                city = regex_return.group(1)
            else:
                city = ""
        city = clean_city_names(city)

        # Find date
        regex = r"_(\d{1,2})_([a-zA-Z]+|\d{1,2})_(\d{4})"
        regex_return = find_regex_in_string(text_cleaned, regex)

        # Extract date info
        if regex_return:
            day = validate_day(regex_return.group(1))
            month = validate_month(regex_return.group(2))
            year = validate_year(regex_return.group(3))

    # Update the obituary information if not already known
    if life_event == "birth":
        obituary.birth_place = city if len(obituary.birth_place) == 0 else ""
        obituary.birth_year = year if len(obituary.birth_year) == 0 else None
        obituary.birth_month = month if len(obituary.birth_month) == 0 else None
        obituary.birth_day = day if len(obituary.birth_day) == 0 else None

        logger.debug(
            "%15s: %s (%s-%s-%s)",
            life_event.capitalize(),
            obituary.birth_place,
            obituary.birth_year,
            obituary.birth_month,
            obituary.birth_day,
        )
    else:
        obituary.death_place = city if len(obituary.death_place) == 0 else ""
        obituary.death_year = year if len(obituary.death_year) == 0 else None
        obituary.death_month = month if len(obituary.death_month) == 0 else None
        obituary.death_day = day if len(obituary.death_day) == 0 else None

        logger.debug(
            "%15s: %s (%s-%s-%s)",
            life_event.capitalize(),
            obituary.death_place,
            obituary.death_year,
            obituary.death_month,
            obituary.death_day,
        )

    return obituary


def find_birth_info(obituary):
    """
    Extract birth info from string of text in obituary attribute

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (DB session)

    Return:
      obituary (Obituary object): update obituary object
    """

    birth_city = ""
    birth_year = None
    birth_month = None
    birth_day = None

    # Find birth segment
    regex = r"("
    regex += r"(?:_(?:geboren|née|né|°))"
    regex += r".*?"
    regex += r"(?:17|18|19|20)_?\d_?\d"
    regex += r")"

    text_found = find_regex_in_string(obituary.ocr_text, regex)

    if text_found:
        text_found = text_found.group(1)
        logger.debug("%15s: %s", "Text found", text_found)
    else:
        text_found = ""
        logger.debug("%15s: %s", "Text found", "None")

    # Find city
    birth_regex = r"(?:(?:_(?:in|te|à|a))_((?:(?:de|st|sint)_)?.*?)_)"
      # returns group(1) == city|None
    birth_regex += r".*?"
    birth_regex += r"\d{4}"

    birth_info = find_regex_in_string(text_found, birth_regex)
    if birth_info:
        # Find city
        birth_city = (
            clean_city_names(birth_info.group(1)) if birth_info.group(1) else ""
        )

        # Find date
        regex = r"_(\d{1,2})_([a-zA-Z]+|\d{1,2})_(\d{4})"
        regex_return = find_regex_in_string(birth_info.group(0), regex)

        # Extract date info
        if regex_return:
            birth_day = validate_day(regex_return.group(1))
            birth_month = validate_month(regex_return.group(2))
            birth_year = validate_year(regex_return.group(3))

    # Update the obituary information if not already known
    if len(obituary.birth_place) == 0:
        obituary.birth_place = birth_city
    if len(obituary.birth_year) == 0:
        obituary.birth_year = birth_year
    if len(obituary.birth_month) == 0:
        obituary.birth_month = birth_month
    if len(obituary.birth_day) == 0:
        obituary.birth_day = birth_day

    logger.debug(
        "%15s: %s (%s-%s-%s)",
        "Birth",
        obituary.birth_place,
        obituary.birth_year,
        obituary.birth_month,
        obituary.birth_day,
    )

    return obituary


def find_death_info(obituary):
    """
    Extract death info from string of text in obituary attribute

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (DB session)

    Return:
      obituary (Obituary object): update obituary object
    """

    death_city = ""
    death_year = None
    death_month = None
    death_day = None

    # Find death segment
    regex = r"("  # group 1
    regex += r"(?:_(?:né|née|geboren|°))"
    regex += r".*?"
    regex += r"(?:17|18|19|20)_?\d_?\d"
    regex += r")"  # end group 1
    regex += r"("  # group 2
    regex += r".*?"
    regex += r"(?:_(?:overleden|overleed|ontslapen|ontsliep|heengegaan|ontnomen|"
    regex += r"gestorven|ingeslapen|teruggekeerd|décédé|décédée|rejoint|ontrukt|"
    regex += r"ontslaapt|stierf|herboren|sterft|decede|decedee|fusillé|gesneuveld|"
    regex += r"ten_hemel_gevaren|ging_over|overgegaan|endormie|verongelukt|\+|†))"
    regex += r".*?"
    regex += r"(?:17|18|19|20)_?\d_?\d"
    regex += r")"  # end group 2

    text_found = find_regex_in_string(obituary.ocr_text, regex)

    if text_found:

        text_found = text_found.group(2)
        logger.debug("%15s: %s", "Text found", text_found)

        # Remove specific words from string as they might interfere
        text_cleaned = remove_unnecessary_text(text_found)
        logger.debug("%15s: %s", "Text cleaned", text_cleaned)

        # Check if city of demise should be same as birth city
        regex = r"_(er|aldaar|aldaer|daar|alwaar|y|el)_"
        regex_return = find_regex_in_string(text_cleaned, regex)
        if regex_return:
            death_city = obituary.birth_place
        else:
            # Extract city of demise
            regex = r"_(?:te|in|van|à|a)_((?:(?:De|St|Sint)_)?.*?)_"
            regex_return = find_regex_in_string(text_cleaned, regex)
            if bool(regex_return):
                death_city = regex_return.group(1)
            else:
                death_city = ""
        death_city = clean_city_names(death_city)

        # Find date
        regex = r"_(\d{1,2})_([a-zA-Z]+|\d{1,2})_(\d{4})"
        regex_return = find_regex_in_string(text_cleaned, regex)

        # Extract date info
        if regex_return:
            death_day = validate_day(regex_return.group(1))
            death_month = validate_month(regex_return.group(2))
            death_year = validate_year(regex_return.group(3))

    # Update the obituary information if not already known
    if len(obituary.death_place) == 0:
        obituary.death_place = death_city
    if len(obituary.death_year) == 0:
        obituary.death_year = death_year
    if len(obituary.death_day) == 0:
        obituary.death_day = death_day
    if len(obituary.death_month) == 0:
        obituary.death_month = death_month

    logger.debug(
        "%15s: %s (%s-%s-%s)",
        "Death",
        obituary.death_place,
        obituary.death_year,
        obituary.death_month,
        obituary.death_day,
    )

    return obituary


def get_note_info(obituary):
    """
    Search for extra information in text.

    Parameters:
      obituary (Obituary object): initial obituary information

    Return:
      obituary (Obituary object): updated obituary information
    """

    # Preset result
    note = ""
    if obituary.note:
        note = obituary.note
    note_2 = ""
    # Define boundaries for Oud-strijder
    regexpression = r"_(oud[_-]?strijders?|oudstriider|oudstrider)_"
    regexpression += r".*?(?:(?:1_?9_?)?\'?([14]_?[04])"
    regexpression += r".*?(?:1_?9_?)?\'?([14]_?[58]))"
    # group(1) = (oud[_-]?strijder)
    # group(2) = ([14]_?[04])
    # group(3) = ([14]_?[58])

    note_2 = find_note_element(obituary.ocr_text, regexpression, "Oud-strijder")
    note += f" - {note_2}" if len(note) > 0 and len(note_2) > 0 else note_2

    # Define boundaries for krijgsgevangene
    regexpression = r"_(krijgsgevangene|kriigsgevangene|krigsgevangene)_"
    regexpression += r".*?(?:(?:1_?9_?)?\'?([14]_?[04])"
    regexpression += r".*?(?:1_?9_?)?\'?([14]_?[58]))"
    # group(1) = (krijgsgevangene)
    # group(2) = ([14]_?[04])
    # group(3) = ([14]_?[58])

    note_2 = find_note_element(obituary.ocr_text, regexpression, "krijgsgevangene")
    note += f" - {note_2}" if len(note) > 0 and len(note_2) > 0 else note_2

    # Define boundaries for weggevoerde
    regexpression = (
        r"_(weggevoerde)_.*?(?:(?:1_?9_?)?\'?([14]_?[04]).*?(?:1_?9_?)?\'?([14]_?[58]))"
    )
    # group(1) = (weggevoerde)
    # group(2) = ([14]_?[04])
    # group(3) = ([14]_?[58])
    note_2 = ""
    note_2 = find_note_element(obituary.ocr_text, regexpression, "weggevoerde")
    note += f" - {note_2}" if len(note) > 0 and len(note_2) > 0 else note_2

    obituary.note = note

    logger.debug("%15s: %s", "Note", obituary.note)

    return obituary


def find_note_element(full_text, search_element, replacement):
    """
    Find a specific element of information in the text that is to be used in the note.

    Parameters:
      full_text (str): text to search in
      search_element (str): regex string denoting what to look for
      replacement (str):


    Return:
      note (str): text found

    """

    logger.debug("Looking for '%s'", replacement)
    note = ""

    # Compile regex
    regex_compiled = re.compile(search_element, flags=re.IGNORECASE)
    # Search text with regex
    found_text = regex_compiled.search(full_text)
    # Extract info
    if bool(found_text):
        logger.debug("Found for '%s': %s", replacement, found_text.group(0))
        if bool(found_text.group(1)):  # group(1) = (replacement)
            note += replacement
            if bool(found_text.group(2)):  # group(2) = ([14]_?[04])
                note += f" 19{found_text.group(2).replace('_','').strip()}"
            if bool(found_text.group(3)):  # group(3) = ([14]_?[58])
                note += f"-19{found_text.group(3).replace('_','').strip()}"

            logger.debug("%15s: %s", "sub note", note)

    return note


def log_info_results(info):
    """
    Printing all information to log.

    Parameters:
      info (class): The collected information
    """
    logger.info("Summary info found in document")
    for arg in vars(info):
        logger.info(
            "%25s:%8s: %s",
            arg,
            type(getattr(info, arg)).__name__,
            getattr(info, arg),
        )


def countdown(t):
    """
    Count down timer.
    Prints time counting down.

    Parameters:
      t (int): time in seconds
    """

    while t:
        mins, secs = divmod(t, 60)
        timer = f"{mins:02d}:{secs:02d}"
        print(f"Waiting ... {timer}", end="\r", flush=True)
        time.sleep(1)
        t -= 1


def set_new_file_name(obituary, db_session):
    """
    Create new file name based on naming templates associated with
    the division and type of document
    Update the Obituary Post class with found information

    Parameters:
      obituary (Obituary Post class)
      db_session (database session)

    Return:
      obituary (Obituary Post class): updated obituary
    """

    # Look up template in db
    file_write_template = get_file_template(db_session, obituary, "write")

    if len(file_write_template) > 0:
        create_new_file_name(db_session, obituary, file_write_template)
    else:
        # No "write" template for this division: use the default format
        create_default_file_name(obituary)

    logger.debug("%15s: %s", "Filename", obituary.new_file_name)

    return obituary


def _default_name_part(text):
    """Text safe for a file name; spaces become _, empty becomes onbekend."""
    text = re.sub(r"\(.*?\)", "", text or "")
    text = re.sub(r"[<>:\\/|?\"'\[\]*\x00-\x1f]+", "", text)
    text = re.sub(r"\s+", "_", text.strip()).strip("._")
    return text or "onbekend"


def _default_date_part(year, month, day):
    """1923-02-06, or 1923-02 / 1923 when the rest is unknown, else onbekend."""
    if not isinstance(year, int):
        return "onbekend"
    parts = [f"{year:04d}"]
    if isinstance(month, int):
        parts.append(f"{month:02d}")
        if isinstance(day, int):
            parts.append(f"{day:02d}")
    return "-".join(parts)


def build_default_file_name(obituary_post):
    """
    Build the default file name without changing the object:
      lastname_firstname_birthdate_deathdate.<original extension>
    """
    name = "_".join(
        (
            _default_name_part(obituary_post.last_name),
            _default_name_part(obituary_post.first_name),
            _default_date_part(
                obituary_post.birth_year,
                obituary_post.birth_month,
                obituary_post.birth_day,
            ),
            _default_date_part(
                obituary_post.death_year,
                obituary_post.death_month,
                obituary_post.death_day,
            ),
        )
    )
    return name + os.path.splitext(obituary_post.file_name)[1]


def create_default_file_name(obituary_post):
    """
    Default file name when the division has no "write" template:
      lastname_firstname_birthdate_deathdate.<original extension>
    Unknown parts are written as "onbekend".

    Parameters:
      obituary_post: ObituaryPost object

    Return:
      obituary_post: updated ObituaryPost object
    """
    obituary_post.new_file_name = build_default_file_name(obituary_post)

    return obituary_post


def create_new_file_name(db_session, obituary_post, new_file_name):
    """
    Construct file name out of components.
    Replaces placeholder sections with actual data.

    Parameters:
      obituary_post: ObituaryPost object
      new_file_name (str): file naming template to use

    Return:
      obituary_post: updated ObituaryPost object
    """

    date = datetime.now()

    # Construct new file name
    replacements = {}
    replacements["fo"] = (
        obituary_post.folder_name if len(obituary_post.folder_name) > 0 else None
    )
    replacements["dv"] = (
        obituary_post.division_slug[1:].title()
        if len(obituary_post.division_slug) > 0
        else None
    )
    replacements["y"] = date.strftime(r"%Y")
    replacements["m"] = date.strftime(r"%m")
    replacements["d"] = date.strftime(r"%d")

    replacements["ln"] = (
        obituary_post.last_name.strip() if len(obituary_post.last_name) > 0 else None
    )

    # Remove anything between brackets, i.e. alias name, from first name
    if len(obituary_post.first_name) > 0:
        replacements["fn"] = re.sub(r"\(.*?\)", "", obituary_post.first_name).strip()
    else:
        replacements["fn"] = None

    # Convert person names to CapitalizedWords case if required
    if get_division_short_names(db_session, obituary_post.division_slug):
        replacements["ln"] = (
            capitalized_words(replacements["ln"]) if replacements["ln"] else None
        )
        replacements["fn"] = (
            capitalized_words(replacements["fn"],"-") if replacements["fn"] else None
        )

    replacements["bp"] = (
        obituary_post.birth_place.strip() if obituary_post.birth_place else None
    )
    replacements["by"] = (
        f"{obituary_post.birth_year:04d}"
        if isinstance(obituary_post.birth_year, int)
        else None
    )
    replacements["bm"] = (
        f"{obituary_post.birth_month:02d}"
        if isinstance(obituary_post.birth_month, int)
        else None
    )
    replacements["bd"] = (
        f"{obituary_post.birth_day:02d}"
        if isinstance(obituary_post.birth_day, int)
        else None
    )
    replacements["dp"] = (
        obituary_post.death_place.strip() if obituary_post.death_place else None
    )
    replacements["dy"] = (
        f"{obituary_post.death_year:04d}"
        if isinstance(obituary_post.death_year, int)
        else None
    )
    replacements["dm"] = (
        f"{obituary_post.death_month:02d}"
        if isinstance(obituary_post.death_month, int)
        else None
    )
    replacements["dd"] = (
        f"{obituary_post.death_day:02d}"
        if isinstance(obituary_post.death_day, int)
        else None
    )
    replacements["dt"] = (
        obituary_post.obituary_type.strip() if obituary_post.obituary_type else None
    )
    replacements["dn"] = (
        obituary_post.document_number.strip() if obituary_post.document_number else None
    )
    replacements["bn"] = (
        obituary_post.box_number.strip() if obituary_post.box_number else None
    )
    replacements["g"] = (
        obituary_post.gender
        if (obituary_post.gender).upper() in {"M", "V", "X"}
        else None
    )
    replacements["p"] = "foto" if obituary_post.face else None
    replacements["n"] = obituary_post.note.strip() if obituary_post.note else None

    # Walk thru them
    for placeholder, replacement in replacements.items():
        new_file_name = update_template(new_file_name, placeholder, replacement)

    # Remove unused optional sections, looks for {} between []
    regex = r"\[[^\[\]]*?\{[^\[\]\{\}]*?\}[^\[\]]*?\]"
    new_file_name = re.sub(regex, "", new_file_name)
    logger.debug("%25s: %s", "Optionals removed", new_file_name)

    # clean up remaining unused placeholders
    # Maybe not necessary, but let's do it anyway
    for placeholder in replacements:
        new_file_name = update_template(new_file_name, placeholder, "")
    logger.debug("%25s: %s", "Placeholders removed", new_file_name)

    # Remove text between parentheses (example)
    new_file_name = re.sub(r"\(.*?\)", "", new_file_name)
    logger.debug("%25s: %s", "(..text..) removed", new_file_name)

    # change multiple spaces to one
    new_file_name = re.sub(r"\s+", " ", new_file_name)
    logger.debug("%25s: %s", "Single spacing applied", new_file_name)

    # Remove leading and trailing spaces
    new_file_name = new_file_name.strip()
    logger.debug("%25s: %s", "Trailing spaces removed", new_file_name)

    # Replace white space with custom character
    new_file_name = re.sub(r"\s", gs_config.APP_CONFIG["replace_space"], new_file_name)
    logger.debug("%25s: %s", "Spaces replaced", new_file_name)

    # Remove invalid characters
    new_file_name = re.sub(r"[<>:\\\/\|?\"\'\]\[*]+", "", new_file_name)
    logger.debug("%25s: %s", "Invalid chars removed", new_file_name)

    # Convert diacritics if required
    new_file_name = convert_diacritics(
        new_file_name, get_division_diacritics(db_session, obituary_post.division_slug)
    )
    logger.debug("%25s: %s", "Diacritics converted", new_file_name)

    # New file name
    obituary_post.new_file_name = (
        new_file_name + os.path.splitext(obituary_post.file_name)[1]
    )

    logger.debug("%25s: %s", "New file name", obituary_post.new_file_name)

    return obituary_post


def update_template(template, part, replacement=None):
    """
    Replace template part with alternative value when defined in template.
    Alternative template part looks like this:
      e.g. {dp|unknown}
    In this case the word unknown is used if no death place was found for the obituary.

    Parameters:
      template (str): the full template string
      part (str): the part to look for
      replacement (str): the text to use

    Return:
      template: the template with just alternative value
    """

    # logger.debug("Start")

    regex = r"({" + part + r"(?:(\|.*?))?})"

    # Get the default to use if there is one
    if replacement is None or len(replacement) == 0:
        # Check if a default is defined
        text_found = find_regex_in_string(template, regex)
        if bool(text_found):
            if bool(text_found.group(2)):
                if (text_found.group(2)).startswith("|"):
                    replacement = text_found.group(2)[1:]

    logger.debug("%25s: '%s'", "replacing {" + part + "}", replacement)

    # Update the template
    if replacement is not None:
        template = re.sub(regex, replacement, template, 0, re.IGNORECASE)

    logger.debug("%25s: %s", "updated template", template)

    # logger.debug("End")
    return template


def normalize_city_names(obituary, db_session):
    """
    Create new file name based on naming templates associated with
    the division and type of document
    Update the Obituary Post class with found information

    Parameters:
      obituary (Obituary Post class)
      db_session (database session)

    Return:
      obituary (Obituary Post class): updated obituary
    """

    obituary.birth_place = normalize_city_name(obituary.birth_place)
    obituary.death_place = normalize_city_name(obituary.death_place)

    return obituary


def normalize_city_name(city_name_and_country):
    """
    If country code in name make it uppercase and position it after
    city name.
    Naming convention returned: city [optional: (country code)]

    Parameters:
      city_name_and_country (str): original city

    Return:
      city_name_and_country (str): possibly modified city
    """

    # Assume no country in city name, i.e. it is in BE
    city = city_name_and_country
    country = ""

    # Find possible 2 letters between brackets representing a country
    regex = r"(?:\(|\[|\{])\w\w(?:\)|\]|\})"
    regex_return = find_regex_in_string(city_name_and_country, regex)

    # Split in city and country
    if bool(regex_return):
        city = city_name_and_country.replace(regex_return.group(0), "").strip()
        country = regex_return.group(0)[1:3].strip().upper()

    if len(country) > 0:
        city_name_and_country = f"{city} ({country})"

    logger.debug("%15s: %s", "city normalized", city_name_and_country)

    return city_name_and_country


def extract_location(text: str, check_string: str = "_geboren") -> str:
    """
    From a string containing a specific substring identify the first occurrence
    of the substring "_te_" and extracts the substring immediately following "_te_"
    up until the next occurrence of "_" or the end of the string.

    Parameters:
      text (str): the string to process
      check_string (str): the part that needs to be in the text

    Return:
      text (str): found string or empty string
    """
    # Inspired by ChatGPT
    # Convert both the text and check_string to lowercase for case-insensitive comparison
    lower_text = text.lower()
    lower_check_string = check_string.lower()

    # Ensure the check_string is in the text (case-insensitive check),
    # otherwise return an empty string
    if lower_check_string not in lower_text:
        return ""

    # Find the first occurrence of "_te_" (case-insensitive)
    te_index = lower_text.find("_te_")

    # If "_te_" is not found, return an empty string
    if te_index == -1:
        return ""

    # Start extracting after "_te_"
    start_index = te_index + len("_te_")

    # Find the next underscore or end of line
    end_index = lower_text.find("_", start_index)

    # If no underscore is found, take the rest of the string
    if end_index == -1:
        end_index = len(text)

    # Extract the substring between "_te_" and the next "_"
    return text[start_index:end_index]


def convert_diacritics(input_str: str, do_convert: bool = False) -> str:
    """
    Converts a string with diacritical marks (accents) to its ASCII equivalent.

    Parameters:
    input_str (str): Input string containing diacritical characters.

    Returns:
    str: The string with diacritical marks replaced by their ASCII equivalent.
    """

    if not do_convert:
        return input_str

    # Normalize the string into its decomposed form, separating base characters and accents
    normalized_str = unicodedata.normalize("NFD", input_str.strip())

    # Filter out diacritical marks and return the base characters
    return "".join(
        char for char in normalized_str if unicodedata.category(char) != "Mn"
    )


def camel_case(input_str: str) -> str:
    """
    Converts a string into camelCase format. The first word is lowercased, and
    subsequent words have their first letter capitalized with spaces removed.

    Parameters:
    input_str (str): Input string containing multiple words.

    Returns:
    str: The camelCase formatted string.
    """
    # Split the string into words based on spaces
    words = input_str.split()

    # Lowercase the first word
    first_word = words[0].lower()

    # Capitalize the first letter of the subsequent words
    capped_words = [word.capitalize() for word in words[1:]]

    # Concatenate the first word with the capitalized subsequent words
    return first_word + "".join(capped_words)


def capitalize_first_letters(input_str):
    """
    Capitalizes the first character of each word, leaving the remaining characters untouched,
    and removes all spaces between the words.

    Parameters:
    input_str (str): Input string containing multiple words.

    Returns:
    str: The string with the first character of each word capitalized and spaces removed.
    """
    # Split the string into words based on spaces
    words = input_str.split()

    # Capitalize only the first character of each word, leaving the rest untouched
    all_capitalized_words = [word[0].upper() + word[1:] for word in words]

    # Concatenate the capitalized words without spaces
    return "".join(all_capitalized_words)


def capitalized_words(input_txt, ignore_punctuation_character=None):
    """
    Capitalizes the first character of each word, setting to lower case for the remaining
    and removes all spaces and punctuation between the words, except for a single
    provided punctuation character.

    Parameters:
    input_txt (str): Input string containing multiple words.
    ignore_punctuation_character (str): single punctuation character that is preserved

    Returns:
    str: The string with the first character of each word capitalized and spaces removed.
    """

    unwanted_characters = string.punctuation + " "

    # Check ignored punctuation character to keep
    if ignore_punctuation_character is not None:
        if ignore_punctuation_character in string.punctuation:
            unwanted_characters = unwanted_characters.replace(
                ignore_punctuation_character, ""
            )

    # Remove unwanted characters from capitalized text
    clean_txt = "".join(ch for ch in input_txt.title() if ch not in unwanted_characters)
    return clean_txt.replace(" ", "")


def print_dict(d, indent=0):
    for key, value in d.items():
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_dict(value, indent + 1)
        else:
            print("  " * indent + f"{key}: {value}")
       