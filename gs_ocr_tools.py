"""
GenScan OCR tools
"""

import logging
import re

import pytesseract

logger = logging.getLogger("gsw_logger")


def extract_ocr_data(image, language=r"nld+fra", segmentation=r"--psm 1"):
    """
    Extract text data from an image

    Parameters:
      image (image): Image to OCR on
      language (string): Tesseract supported languages, default 'nld+fra'
      segmentation (string): Tesseract segmentation method, default 1

    Return:
      extracted_text (dictionary): Tesseract dictionary; result of OCR
    """

    logger.debug("Extracting OCR data from image")

    extracted_text = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT,
        lang=language,
        config=segmentation,
    )

    return extracted_text


def locate_word(ocr_data, text_pattern="geboren|né|née"):  # kdo: 2023-12-29 : not used
    """
    This routine is searching for a given regex string in the OCR'd text of a given image.

    Parameters:
      ocr_data (dict): Tesseract data dictionary.
      text_pattern (string): Text, supporting regex expression, to locate on the image.

    Return:
      Coordinates of text location.
    """

    logger.debug("Locating '%s' in image", text_pattern)

    # Initialize variables to store text and line coordinates
    text_coordinates = None
    line_coordinates = None
    paragraph_coordinates = None

    # Iterate through the text information to find the coordinates of the target text
    for i in range(len(ocr_data["text"])):
        # condition to only pick boxes with certain confidence
        if int(ocr_data["conf"][i]) > 10:
            # Check if text matches any of the target words
            if re.fullmatch(text_pattern, ocr_data["text"][i].strip(), re.IGNORECASE):
                # Extract coordinates
                text_coordinates = (
                    ocr_data["left"][i],
                    ocr_data["top"][i],
                    ocr_data["left"][i] + ocr_data["width"][i],
                    ocr_data["top"][i] + ocr_data["height"][i],
                )

                # Find the PARAGRAPH coordinates where we found the target text
                for j in range(len(ocr_data["par_num"])):
                    if (
                        ocr_data["par_num"][j] == ocr_data["par_num"][i]
                        and ocr_data["block_num"][j] == ocr_data["block_num"][i]
                        and ocr_data["page_num"][j] == ocr_data["page_num"][i]
                    ):
                        # Store the paragraph coordinates
                        paragraph_coordinates = (
                            ocr_data["left"][j],
                            ocr_data["top"][j],
                            ocr_data["left"][j] + ocr_data["width"][j],
                            ocr_data["top"][j] + ocr_data["height"][j],
                        )

                        # Break out of the paragraph loop as we found the correct paragraph
                        break

                # Find the LINE coordinates where we found the target text
                for j in range(len(ocr_data["line_num"])):
                    if (
                        ocr_data["line_num"][j] == ocr_data["line_num"][i]
                        and ocr_data["par_num"][j] == ocr_data["par_num"][i]
                        and ocr_data["block_num"][j] == ocr_data["block_num"][i]
                        and ocr_data["page_num"][j] == ocr_data["page_num"][i]
                    ):
                        # Store the line coordinates
                        line_coordinates = (
                            ocr_data["left"][j],
                            ocr_data["top"][j],
                            ocr_data["left"][j] + ocr_data["width"][j],
                            ocr_data["top"][j] + ocr_data["height"][j],
                        )

                        # Break out of the line loop as we found the correct line
                        break

                # Break out of the if as we found the target text
                # break
    if text_coordinates:
        logger.debug("Text '%s' found", text_pattern)
    else:
        logger.debug("No match found")

    return {
        "text_coordinates": text_coordinates,
        "line_coordinates": line_coordinates,
        "paragraph_coordinates": paragraph_coordinates,
    }


def get_text_angle(pil_image):  # kdo: 2023-11-19 : getting false rotations
    """
    This routine is finds the angle of text in an image.

    Parameters:
      image (image): Image to OCR on.

    Return:
      Angle (float).
    """

    logger.debug("Getting text rotation")

    # Image size
    img_width, img_height = pil_image.size

    # Setting the points for cropped image
    left = 0
    top = img_height / 4
    right = img_width
    bottom = img_height * 3 / 4

    # pick middle of image
    img = pil_image.crop((left, top, right, bottom))
    osd = pytesseract.image_to_osd(img, output_type="dict")

    orientation = float(osd["orientation"])
    confidence = float(osd["orientation_conf"])
    rotate = float(osd["rotate"])

    logger.debug("Orientation: %s", orientation)
    logger.debug("Rotate: %s", rotate)
    logger.debug("Confidence: %s", confidence)

    return rotate
