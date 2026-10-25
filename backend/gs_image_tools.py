"""
Some helper functions for genscan images
"""

import io
import logging
import os

import cv2
import numpy as np
import pypdfium2 as pdfium

# from codetiming import Timer, TimerError
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

import gs_config
from gs_file_tools import delete_file

logger = logging.getLogger("gsw_logger")
Image.MAX_IMAGE_PIXELS = None  # disables the warning


def open_image(file_path):
    """
    Opens an image file and returns it as a PIL Image object.

    Parameters:
        file_path (str): Path to the image file.

    Returns:
        list: A list containing the PIL Image object if successfully opened
    """
    try:
        image = Image.open(file_path)
        logger.debug("%15s: %s", "Image loaded", file_path)
        return [image]
    except FileNotFoundError:
        logger.debug("%15s: %s", "File not found", file_path)
        return None
    except IOError as e:
        logger.debug("%15s: %s", "Cannot open file", e)
        return None


def display_images(pil_images):
    """
    Just to show images during development
    """
    for pil_image in pil_images:
        pil_image.show()


def is_square_like(width, height, tolerance=0.05):
    """
    Determines if an image is square-like based on a given tolerance.

    Args:
        width (int): The width of the image.
        height (int): The height of the image.
        tolerance (float): The acceptable deviation from a perfect square (default: 0.05).

    Returns:
        bool: True if the image is square-like, False otherwise.
    """
    ratio = width / height
    return abs(1 - ratio) <= tolerance


def is_landscape(width, height, tolerance=0.05):
    """
    Determines the image is 'landscape'.
    If not it is considered 'portrait'.
    If the image is square-like, it is considered 'portrait'.

    Args:
        width (int): The width of the image.
        height (int): The height of the image.
        tolerance (float): The acceptable deviation from a perfect square (default: 0.05).

    Returns:
        boolean: True or False.
    """
    return image_orientation(width, height, tolerance) == "landscape"


def image_orientation(width, height, tolerance=0.05):
    """
    Determines the orientation of an image as 'landscape' or 'portrait'.
    If the image is square-like, it returns 'portrait'.

    Args:
        width (int): The width of the image.
        height (int): The height of the image.
        tolerance (float): The acceptable deviation from a perfect square (default: 0.05).

    Returns:
        str: 'landscape' or 'portrait'.
    """
    logger.debug(
        "%15s: %sx%s (tolerance %s)", "Check orientation", width, height, tolerance
    )
    ratio = width / height
    if abs(1 - ratio) <= tolerance:
        logger.debug("%15s: %s", "Orientation", "portrait-like")
        return "portrait"
    orientation = "landscape" if width > height else "portrait"
    logger.debug("%15s: %s", "Orientation", orientation)
    return orientation


def resize_image(pil_image, new_height=1000):
    """
    Resizing the image

    Parameters:
      pil_image (PIL): a PIL formatted image
      new_height (int): New height for image, default 1000px

    Return:
      new_image (PIL): Image resized to new height with added border
    """

    # border_size = 10
    img_width = pil_image.size[0]
    img_height = pil_image.size[1]
    img_ratio = new_height / img_height
    new_width = int(img_width * img_ratio)
    new_height = int(img_height * img_ratio)

    new_image = ImageOps.expand(
        pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS),
    )

    logger.debug("Image resized to %sx%s", new_width, new_height)

    return new_image


def resize_big_image(pil_image, max_size=1080):
    """
    Resizing big image to a maximum side size, but keeping ratio

    Parameters:
      pil_image (PIL): a PIL formatted image
      max_size (int): New maximum size in pixels of a side, default 1080px

    Return:
      new_image (PIL): Resized image
    """

    # determine image size
    img_width = pil_image.size[0]
    img_height = pil_image.size[1]
    logger.debug(
        "Image size is %sx%s (%s pixels)", img_width, img_height, img_width * img_height
    )

    pil_image.thumbnail((max_size, max_size))
    img_width, img_height = pil_image.size
    logger.debug(
        "Image resized to %sx%s (%s pixels)",
        img_width,
        img_height,
        img_width * img_height,
    )

    return pil_image


def create_images_with_pdf2im(pdf_file_path, dpi=200):
    """
    Create images from all PDF pages.
    Based on pdf2image which requires poppler for windows!

    Parameters:
      pdf_file_path (string): full path of PDF file

    Return:
      List of images in PIL format
    """

    # inspired by ChatGPT

    poppler_path = os.path.join(os.getcwd(), "poppler", "Library", "bin")

    images = []
    # Check if poppler is installed in subfolder of current working directory
    try:
        if os.path.exists(poppler_path):
            images = convert_from_path(
                pdf_file_path, dpi=dpi, poppler_path=poppler_path, size=3000
            )
        # If not, try with bin path in environment variables
        else:
            images = convert_from_path(pdf_file_path, dpi=dpi, size=3000)

    except FileNotFoundError:
        logger.error("File not found: %s", pdf_file_path)

    except PDFPageCountError:
        logger.error(
            "Unable to get page count for PDF file: %s. It may not be a valid PDF.",
            pdf_file_path,
        )

    except Exception as e:
        logger.error(
            "An unexpected error occurred while processing the PDF file: %s. Error: %s",
            pdf_file_path,
            str(e),
        )

    # Fallback without poppler: render with PyMuPDF (same dpi and size)
    if len(images) == 0:
        images = create_images_with_pymupdf(pdf_file_path, dpi=dpi, size=3000)

    logger.info("Created %s images", len(images))
    for img, image in enumerate(images):
        logger.debug("Image %s: %s", img, image.size)

    return images


def create_images_with_pymupdf(pdf_file_path, dpi=200, size=3000):
    """
    Create images from all PDF pages with PyMuPDF (no poppler needed).
    The longest side is limited to 'size' pixels, like pdf2image.

    Parameters:
      pdf_file_path (string): full path of PDF file
      dpi (int): render resolution
      size (int): maximum length of the longest side

    Return:
      List of images in PIL format
    """

    try:
        import pymupdf  # pylint: disable=import-outside-toplevel
    except ImportError:
        logger.error("PyMuPDF not installed, can't render %s", pdf_file_path)
        return []

    images = []
    try:
        with pymupdf.open(pdf_file_path) as document:
            for page in document:
                zoom = dpi / 72
                longest = max(page.rect.width, page.rect.height) * zoom
                if size and longest > size:
                    zoom *= size / longest
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                image = Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
                images.append(image)
        logger.info("Rendered %s pages with PyMuPDF", len(images))
    except Exception as e:  # pylint: disable=broad-except
        logger.error("PyMuPDF could not render %s: %s", pdf_file_path, e)
        images = []

    return images


def is_image_only_pdf(pdf_path):
    """
    Check if PDF has only images using PyPDF2

    Parameters:
      pdf_file_path (str): full path of PDF file

    Return: True or False
    """

    try:
        pdf = PdfReader(pdf_path)
        for page in pdf.pages:
            # Check for text content
            text = page.extract_text()
            if text and text.strip():
                # If any text is found, it's not an image-only PDF
                logger.debug("Not an image-only PDF, text found")

                return False

            # Check for image objects in the page
            if "/XObject" in page["/Resources"]:
                xobjects = page["/Resources"]["/XObject"].get_object()
                for obj in xobjects:
                    if xobjects[obj]["/Subtype"] == "/Image":
                        # If an image is found, continue checking other pages
                        continue

            # If no images and no text are found on a page, it's not an image-only PDF
            logger.debug("Not an image-only PDF, no text and no images found")

            return False

        # If all pages contain only images, return True
        logger.debug("Is an image-only PDF")

        return True

    except PdfReadError as e:
        logger.error("Error reading PDF: %s.", pdf_path)
        logger.error("PDFReadError: %s", str(e))

        return False

    except Exception as e:
        logger.error("Error reading PDF: %s.", pdf_path)
        logger.error("Exception: %s", str(e))

        return False


def extract_images_with_pypdf2(pdf_file_path):
    """
    Extract all images out of a PDF using PyPDF2
    Much faster than function extract_images_from_pdf
    Remark: Fails to extract images from certain pdf files !

    Parameters:
      pdf_file_path (string): full path of PDF file

    Return:
      images (list): List of images in PIL format
    """

    # Check if document is image only PDF, i.e. as in PDF made by scanning
    images = []
    if is_image_only_pdf(pdf_file_path):
        pdf = PdfReader(pdf_file_path)
        for page in pdf.pages:
            for image in page.images:
                images.append(Image.open(io.BytesIO(image.data)))

    logger.info("Extracted %s images", len(images))
    for img, images in enumerate(images):
        logger.debug("Image %s: %s", img, img.size)

    return images


def extract_images_with_pypdf2_fixed_dpi(pdf_file_path, target_dpi=300):
    """
    Extract all images out of a PDF using PyPDF2 with a fixed DPI
    Much faster than function extract_images_from_pdf
    Remark: Fails to extract images from certain pdf files !

    Parameters:
      pdf_file_path (str): full path of PDF file
      target_dpi (int): fixed DPI to use

    Return:
      images (list): List of images in PIL format
    """

    # Check if document is image only PDF, i.e. as in PDF made by scanning
    images = []
    if is_image_only_pdf(pdf_file_path):
        pdf = PdfReader(pdf_file_path)

        for page in pdf.pages:
            for image in page.images:
                # Load image into memory
                img = Image.open(io.BytesIO(image.data))

                # Calculate the current DPI if known, or assume 200 (common default DPI)
                current_dpi = img.info.get("dpi", (200, 200))[0]

                # Calculate the target size based on the current and desired DPI
                target_width = int((img.width * target_dpi) / current_dpi)
                target_height = int((img.height * target_dpi) / current_dpi)

                # Resize the image to the new dimensions if necessary
                if current_dpi != target_dpi:
                    img = img.resize((target_width, target_height), Image.LANCZOS)

                # Save to an in-memory file with the target DPI
                img_with_dpi = io.BytesIO()
                img.save(img_with_dpi, format="PNG", dpi=(target_dpi, target_dpi))
                img_with_dpi.seek(0)

                # Load the modified image back into an Image object if needed
                images.append(Image.open(img_with_dpi))

    logger.info("Extracted %s images", len(images))

    return images


def extract_images_with_pdfium(pdf_file_path):
    """
    Extract all images out of a PDF using pypdfium2
    kdo: 2024-04-26 - has some issues with text extraction
         not yet resolved

    Parameters:
      pdf_file_path (str): full path of PDF file

    Return:
      images (list): List of images in PIL format
      embedded_text (str): Text that is possibly already in the file
    """

    embedded_text = ""
    images = []

    pdf = pdfium.PdfDocument(pdf_file_path)

    n_pages = len(pdf)
    for page_number in range(n_pages):
        page = pdf.get_page(page_number)
        # Make image of it
        bitmap = page.render(scale=2)
        pil_image = bitmap.to_pil()
        images.append(pil_image)

        # Extract text
        textpage = page.get_textpage()
        embedded_text += textpage.get_text_range()

    logger.info("Extracted %s images", len(images))
    if len(embedded_text) > 0:
        logger.info("Document has embedded text (%s chars)", len(embedded_text))
    else:
        logger.info("Document has NO embedded text")

    return embedded_text, images


def extract_text_with_pypdf2(pdf_file_path):
    """
    Extract all text out of a PDF using PyPDF2

    Parameters:
      pdf_file_path (str): full path of PDF file

    Return:
      embedded_text (str|None): Text that is possibly already in the file or None
    """

    embedded_text = ""

    reader = PdfReader(pdf_file_path)
    for page in reader.pages:
        embedded_text += page.extract_text()

    if len(embedded_text) > 0:
        logger.info("Document has embedded text (%s chars)", len(embedded_text))
        logger.debug("%15s : %s", "pypdf2 text len", len(embedded_text))
        logger.debug("%15s : %s", "pypdf2 text", embedded_text)
    else:
        embedded_text = None
        logger.info("Document has NO embedded text")

    return embedded_text


def trim_image_borders(pil_image, thresh=220):
    """
    Trim excessive black borders to smallest possible

    Parameter
      pil_image (list): PIL formatted image
      tresh (int): Threshold level to turn into BW

    Return:
      PIL image
    """
    # Turn image into B/W
    bw_image = pil_image.convert("L").point(
        lambda x: 255 if x > thresh else 0, mode="1"
    )
    # Bounding box given as a 4-tuple defining the left, upper, right, and lower pixel coordinates.
    # If the image is completely empty, this method returns None.
    bbox = bw_image.getbbox()
    if bbox:
        cropped_image = pil_image.crop(bbox)
        # cropped_image.show()
        return cropped_image

    return pil_image


def trim_images_borders(pil_images, thresh=240):
    """
    Trim black image borders from PIL images

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Trimming black borders")

    new_pil_images = []

    # Loop thru images
    for n, pil_image in enumerate(pil_images):
        cropped_image = trim_image_borders(pil_image, thresh)
        if cropped_image:
            original_area = pil_image.size[0] * pil_image.size[1]
            cropped_area = cropped_image.size[0] * cropped_image.size[1]

            # Check if the cropped area is no more than 10% smaller than the original
            if cropped_area >= 0.9 * original_area:
                logger.debug("Image %s cropped %s", n, cropped_image.size)
                new_pil_images.append(cropped_image)
            else:
                logger.debug(
                    "Image %s cropping rejected, original size: %s, cropped size: %s",
                    n,
                    pil_image.size,
                    cropped_image.size,
                )
                new_pil_images.append(pil_image)
        else:
            logger.debug("Image %s not cropped %s", n, pil_image.size)
            new_pil_images.append(pil_image)

    return new_pil_images


def align_images_rotation(pil_images):
    """
    Align orientation of images to first image orientation

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Aligning images orientation to first image")

    if len(pil_images) == 1:
        logger.debug("Single image %s, no further processing", pil_images[0].size)

        return pil_images

    new_pil_images = []

    # Get orientation of first image orientation
    width, height = pil_images[0].size
    orientation = "portrait" if width < height else "landscape"

    # Loop thru images
    for n, pil_image in enumerate(pil_images):
        width, height = pil_image.size
        orientation_other = "portrait" if width < height else "landscape"
        if orientation_other == orientation:
            logger.debug("Image %s is %s %s", n, orientation, pil_image.size)
            new_pil_images.append(pil_image)
        else:
            logger.debug("Image %s is %s %s", n, orientation_other, pil_image.size)
            rotated_pil_image = pil_image.rotate(90, expand=True)
            new_pil_images.append(rotated_pil_image)
            logger.debug(
                "Image %s rotated to %s %s", n, orientation, rotated_pil_image.size
            )

    return new_pil_images


def split_landscape_images(pil_images):
    """
    Expand landscape image(s) into left and right image(s).
    Most landscape documents have text columns left and right.
    Most portrait documents have text in just one column.

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Splitting landscape images in left and right image")

    new_pil_images = []

    # Loop thru images
    for n, pil_image in enumerate(pil_images):
        width, height = pil_image.size

        if is_landscape(width, height, tolerance=0.02):  # it is a landscape image
            half = width // 2
            new_pil_images.append(pil_image.crop((0, 0, half, height)))  # left part
            new_pil_images.append(
                pil_image.crop((half, 0, width, height))
            )  # right part
            logger.debug("Image %s split in two", n)
        else:  # it is a portrait image
            new_pil_images.append(pil_image)
            logger.debug("Image %s left unchanged", n)

    return new_pil_images


def save_image_as_pdf(image_path, keep_original=False):
    """
    Converts a JPG/JPEG image to a PDF and saves it to the specified path.
    If the provided output file path does not have a .pdf extension, it will be updated to have one.
    The function will not proceed if the image_path is not a JPG or JPEG file.

    Parameters:
        image_path (str): The path to the image file.
        keep_original (boolean): Keep (True) or delete (False) the original image

    Returns:
        (str): file name, either original or PDF version
    """

    # Ensure the input file has a .jpg or .jpeg extension
    if not image_path.lower().endswith((".jpg", ".jpeg")):
        logger.debug(
            "%15s: %s",
            "File extension",
            f"Is not an image ({os.path.splitext(image_path)[1]})",
        )
        return os.path.basename(image_path)

    if not isinstance(keep_original, bool):
        logger.debug(
            "%15s: %s",
            "Keep_original",
            f"Is not a correct boolean value ({keep_original})",
        )
        return os.path.basename(image_path)

    try:
        with Image.open(image_path) as image:
            # Ensure the output file has a .pdf extension
            pdf_path = os.path.splitext(image_path)[0] + ".pdf"

            # Convert the image to RGB if it's not already
            if image.mode in ("RGBA", "LA"):
                image = image.convert("RGB")

            # Save the image as a PDF
            image.save(pdf_path, "PDF", resolution=100.0)
            logger.debug("Image saved as PDF at %s", pdf_path)

        # Delete original image file, if required
        if not keep_original and delete_file(image_path):
            logger.debug("Original image deleted")
        else:
            logger.debug("Original image kept")

    except Exception as e:
        logger.debug("An error occurred: %s", e)

        return os.path.basename(image_path)

    return os.path.basename(pdf_path)


def save_image(image_path, pil_image):
    """
    Save single image to defined path.

    Parameters:
      image_path (str): Full path and name for location to save image to.
      pil_image: One image.
    """

    #   Add timer
    # t_save_img = Timer(name="SaveImageTimer", logger=None)
    # t_save_img.start()

    logger.debug("Saving image %s", image_path)

    # pil_image.save(image_path, "webp", lossless=True, quality=90)
    pil_image.save(image_path, "webp", lossless=False, quality=80)
    # kdo 2025-02-09 : The pil.save() operation takes way too much time !!!
    #                  Need to check out if JPG or PNG is faster

    # t_save_img.stop()
    # try:
    #    logger.debug(
    #        "%s : %.2fs",
    #        "End - Run time",
    #        Timer.timers.total(t_save_img.name),
    #    )
    # except KeyError:
    #    logger.debug("End - No timer registered")
    #    return

    # Timer.timers.clear()


def save_web_image(image_path, file_name, web_image, text=None):
    """
    Save single image with black border for web usage.
    Add watermark if required.

    Parameters:
      image_path (str): Full path for location to save image to
      file_name (str): File name to use
      web_image (PIL): One image
      text (str): the text to add to watermark

    Return:
    image_file_path (str): Full path to image
    """

    #   Add timer
    # t_save_webimg = Timer(name="SaveWebImageTimer", logger=None)
    # t_save_webimg.start()

    image_file_path = os.path.join(
        image_path,
        file_name,
    )
    logger.debug("Saving web image %s", image_file_path)

    border_size = 10

    # Add watermark if required
    if gs_config.APP_CONFIG["watermark"]:
        web_image = watermark_image(
            web_image,
            watermark_text=f'{gs_config.APP_CONFIG["watermark_text"]} - {text}',
        )

    # Add a bit of border
    web_image = ImageOps.expand(web_image, border=border_size)

    save_image(image_file_path, web_image)

    logger.debug("Web image saved")

    # t_save_webimg.stop()
    # try:
    #    logger.debug(
    #        "%s : %.2fs",
    #        "End - Run time",
    #        Timer.timers.total(t_save_webimg.name),
    #    )
    # except KeyError:
    #    logger.debug("End - No timer registered")
    #    return

    # Timer.timers.clear()

    return image_file_path


def save_images(image_path, image_name, pil_images, name_differentiator=""):
    """
    Save images to defined path.

    Parameters:
      images_path (str): Location to save images to.
      images_name (str): Base file name for images. Number and format is appended.
      pil_images (list): One or more images.
    """
    if logger.level == logging.DEBUG:

        for n, image in enumerate(pil_images):
            full_path = os.path.join(
                image_path, f"{image_name}_{n:0>2}_{name_differentiator}.jpg"
            )
            save_image(full_path, image)


def grayscale_images(pil_images):
    """
    Make a grayscale versions of image(s).

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Grayscale images")

    new_pil_images = []

    # Loop thru images
    for pil_image in pil_images:
        new_pil_images.append(pil_image.convert("L"))

    return new_pil_images


def threshold_images(pil_images):
    """
    Apply OTSU threshold om image(s).

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Threshold images")

    new_pil_images = []

    # Loop thru images
    for pil_image in pil_images:
        # convert to cv2 image
        cv2_image = np.array(pil_image)
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_RGB2BGR)
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)  # gray
        # apply threshold
        _, cv2_image = cv2.threshold(
            cv2_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        # convert back to PIL image
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(cv2_image)
        new_pil_images.append(pil_image.convert("L"))

    return new_pil_images


def enhance_images(pil_images):
    """
    Enhance contrast of image(s).

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Enhance images")

    factor = 1.5  # increase contrast
    new_pil_images = []

    # Loop thru images
    for pil_image in pil_images:
        image = ImageEnhance.Contrast(pil_image)
        new_pil_images.append(image.enhance(factor))

    return new_pil_images


def rotate_images(pil_images):
    """
    Rotate image(s) by 90 degrees.

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """

    logger.info("Rotate images")

    new_pil_images = []

    # Loop thru images
    for pil_image in pil_images:
        new_pil_images.append(pil_image.rotate(90))

    return new_pil_images


def straighten_images(pil_images):
    """
    Rotate images if text is under an angle.

    Parameters:
      pil_images (list): One or more PIL images

    Return:
      List of PIL images
    """
    # kdo: 2023-11-19 : getting false rotations
    return pil_images
    # logger.debug("Start")
    # logger.info("Straightening images")

    # new_pil_images = []

    # # Loop thru images
    # for n, pil_image in enumerate(pil_images):
    #     angle = get_text_angle(pil_image)
    #     logger.debug("Angel image %s is %s", n, angle)

    #     new_pil_images.append(pil_image.rotate(angle, expand=True))

    # logger.debug("End")

    # return new_pil_images


def draw_rectangle(pil_image, coordinates=None, color="blue"):
    """
    Draw a rectangle on an image

    Parameters:
      pil_image: One PIL image

    Return:
      One PIL image
    """

    if coordinates:
        draw = ImageDraw.Draw(pil_image)
        draw.rectangle(coordinates, outline=color, width=1)

    return pil_image


def pre_process_images(pil_images, *processes):
    """
    Apply some corrections to a set of images.

    Parameters:
      pil_images (list): One or more PIL images
      processes (tuple): Contains one or more actions to apply to images in order provided
        - TRIM   : trim dark borders of images
        - ALIGN  : align orientation of images to orientation of first image
        - STRAIGHTEN : try to rotate images to level text horizontally
        - GRAY   : convert original images to gray
        - OTSU   : convert original images to gray and apply OTSU threshold
        - ENHANCE: enhance contrast of original images
        - ROTATE : rotate image 90 degrees

    Return:
      pil_images (list): One or more processed PIL images
    """

    logger.info("Pre-processing images with %s", processes)
    for process in processes:
        logger.debug("Pre-process method: %s", process.upper())
        match process.upper():
            case "TRIM":
                # kdo: 2023-11-26 : getting too much cut off
                pil_images = trim_images_borders(pil_images, thresh=240)
            case "ALIGN":
                pil_images = align_images_rotation(pil_images)
            case "STRAIGHTEN":
                # kdo: 2023-11-19 : getting false rotations
                pil_images = straighten_images(pil_images)
            case "GRAY":
                pil_images = grayscale_images(pil_images)
            case "OTSU":
                # kdo: 2023-12-02: images seem worse off, but still text is found
                pil_images = threshold_images(pil_images)
            case "ENHANCE":
                # kdo: 2023-12-02 : not always better
                pil_images = enhance_images(pil_images)
            case "ROTATE":
                pil_images = rotate_images(pil_images)

    return pil_images


def pil_to_cv2(pil_img):
    """Converting a Pillow image to OpenCV format."""
    cv2_img = np.array(pil_img)
    return cv2.cvtColor(cv2_img, cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_img):
    """Converting a OpenCV image to Pillow format."""
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cv2_img)


def vertically_concat_resize(cv2_img_list, interpolation=cv2.INTER_CUBIC):
    """
    Vertically concatenating images.

    Parameters:
      cv2_img_list (list): One or more cv2 images
      interpolation (string): Interpolation mode

    Return:
      One cv2 image
    """
    # define a function for vertically concatenating images of different widths
    # from https://www.geeksforgeeks.org/concatenate-images-using-opencv-in-python/
    # function calling
    # img_v_resize = vertically_concat_resize([img1, img2, img1])

    # take minimum width
    for img, cv2_img in enumerate(cv2_img_list):
        logger.debug("Image %s: %s", img, cv2_img.shape)
    w_min = min(cv2_img.shape[1] for cv2_img in cv2_img_list)
    logger.debug("%15s: %spx", "Minimum width", w_min)

    # resizing images
    img_list_resize = [
        cv2.resize(
            cv2_img,
            (w_min, int(cv2_img.shape[0] * w_min / cv2_img.shape[1])),
            interpolation=interpolation,
        )
        for cv2_img in cv2_img_list
    ]

    # combine the images
    img_combined = cv2.vconcat(img_list_resize)
    logger.debug("Combined Image: %s", img_combined.shape)

    return img_combined


def horizontally_concat_resize(cv2_img_list, interpolation=cv2.INTER_CUBIC):
    """
    Horizontally concatenating images.

    Parameters:
      cv2_img_list (list): One or more cv2 images
      interpolation (string): Interpolation mode

    Return:
      One cv2 image
    """
    # define a function for horizontally concatenating images of different heights
    # from https://www.geeksforgeeks.org/concatenate-images-using-opencv-in-python/
    # function calling
    # img_h_resize = horizontally_concat_resize([img1, img2, img1])

    # take minimum height
    for img, cv2_img in enumerate(cv2_img_list):
        logger.debug("Image %s: %s", img, cv2_img.shape)
    h_min = min(cv2_img.shape[0] for cv2_img in cv2_img_list)
    logger.debug("%15s: %spx", "Minimum height", h_min)

    # image resizing
    img_list_resize = [
        cv2.resize(
            cv2_img,
            (int(cv2_img.shape[1] * h_min / cv2_img.shape[0]), h_min),
            interpolation=interpolation,
        )
        for cv2_img in cv2_img_list
    ]

    # combine the images
    img_combined = cv2.hconcat(img_list_resize)
    logger.debug("Combined Image: %s", img_combined.shape)

    return img_combined


def concatenate_images(pil_images, orientation="first"):
    """
    Create one image from multiple images.

    Parameters:
      pil_images (list): One or more PIL images
      orientation (str): vertical, horizontal, both is the orientation
                            the images should be concatenated to each other,
                            default (first) is based on first image orientation

    Return:
      One PIL image
    """

    if len(pil_images) > 1:
        cv2_images = [pil_to_cv2(pil_img) for pil_img in pil_images]
        shape_height, shape_width, _ = cv2_images[0].shape
        match orientation.lower():
            case "vertical":
                # for landscape images
                cv2_image = vertically_concat_resize(cv2_images)
            case "horizontal":
                # for portrait images
                cv2_image = horizontally_concat_resize(cv2_images)
            case _:  # same as first image
                if is_landscape(shape_width, shape_height, tolerance=0.02):
                    # for landscape images
                    cv2_image = vertically_concat_resize(cv2_images)
                else:
                    # for portrait images
                    cv2_image = horizontally_concat_resize(cv2_images)

        pil_image = cv2_to_pil(cv2_image)
    else:
        pil_image = pil_images[0]

    logger.debug("Created one big image")

    return pil_image


def has_face(obituary, pil_image):
    """
    Detecting if a picture with face is present.
    Saved in DEBUG mode.

    Parameters:
      obituary (Obituary object): initial obituary information
      pil_image (PIL image): Image to search for face on

    Return:
      obituary (Obituary object): updated obituary information
    """

    obituary.face = False

    # Load face recognition classifier
    face_classifier = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    # Find face
    cv2_image = pil_to_cv2(pil_image)
    face = face_classifier.detectMultiScale(
        cv2_image, scaleFactor=1.1, minNeighbors=5, minSize=(300, 300)
    )

    if len(face) > 0:
        obituary.face = True

    # Save image if debug is on for face recognition
    if (
        logger.level == logging.DEBUG
        and gs_config.APP_CONFIG["debug_images_with_faces"]
        and gs_config.APP_CONFIG["debug_folder"]
    ):
        if obituary.face:
            # Draw rectangle around face(s)
            for face_x, face_y, face_width, face_height in face:
                cv2.rectangle(
                    cv2_image,
                    (face_x, face_y),
                    (face_x + face_width, face_y + face_height),
                    (0, 255, 0),
                    4,
                )
                logger.debug(
                    "%15s: x%s y%s %sx%s",
                    "Face",
                    face_x,
                    face_y,
                    face_width,
                    face_height,
                )

            debug_filename = f"{obituary.obituary_id}_face.jpg"
        else:
            debug_filename = f"{obituary.obituary_id}_noface.jpg"

        # Save as debug image
        logger.debug("Writing %s to debug folder", debug_filename)
        image_file_path = os.path.join(
            gs_config.APP_CONFIG["debug_folder"],
            debug_filename,
        )
        cv2.imwrite(image_file_path, cv2_image)

    logger.debug("%15s: %s (%sx)", "Found face", obituary.face, len(face))

    return obituary


# Watermark fonts: Windows name first, then macOS / Linux paths.
WATERMARK_FONTS = [
    "arial.ttf",
    "Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _watermark_font(font_size):
    """Arial in the given size, or the closest available font."""
    for font_name in WATERMARK_FONTS:
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    logger.debug("No TrueType font found for watermark, using default font")
    return ImageFont.load_default(size=font_size)


def watermark_image(pil_image, watermark_text=""):
    """
    Watermark an image
    Parameters:
      pil_image (PIL image): Image to put watermark on
      watermark_text (str): Text to print on image

    Return:
      (PIL image)
    """

    logger.info("Watermarking image")

    # Add black border
    pil_image = ImageOps.expand(pil_image, border=10)

    # Convert to add transparent layer
    input_image = pil_image.convert("RGBA")
    width, height = input_image.size

    overlay = Image.new("RGBA", input_image.size, color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Add lines
    watermark_color_pattern = (0, 0, 0, 20)
    for i in range(0, width + height, 100):
        draw.line([(0, height - i), (i, height)], fill=watermark_color_pattern, width=5)

    # Add text
    font_size = 80
    font = _watermark_font(font_size)
    # left, top, right, bottom = draw.textbbox((0, 0), watermark_text, font)
    # text_width = right - left
    # text_height = bottom - top

    text_width = draw.textlength(watermark_text, font=font)
    # Reduce font size until the text fits within the image width
    # Leave some padding (10px on each side)
    try:
        while text_width > width - 20:
            font_size -= 5
            font = _watermark_font(font_size)
            text_width = draw.textlength(watermark_text, font=font)

        # Calculate the position to center the text
        x = (width - text_width) // 2
        y = (height - font_size) // 2
        watermark_color_text = (0, 0, 0, 30)

        # Draw the text on the overlay
        draw.text((x, y), watermark_text, fill=watermark_color_text, font=font)
    except ValueError:
        logger.debug("Can't write watermark on image")
    finally:
        # Combine the original image with the overlay
        watermarked_image = Image.alpha_composite(input_image, overlay)

    return watermarked_image


def create_working_images(pil_images, obituary_type):
    """
    Create working images out of originals
    Parameters:
      pil_images (PIL images): One or more PIL images
      obituary_type (string): Type of obituary

    Return:
      web_image: Used to upload to web
      ocr_image: Used to perform OCR on
    """

    # Perform some specific preprocessing based on obituary type
    match obituary_type.lower():
        case "bp":
            pil_images = pre_process_images(pil_images, "ALIGN", "TRIM")
        case _:
            pil_images = pre_process_images(pil_images, "ALIGN")

    # Create web image
    web_image = concatenate_images(pil_images, orientation="first")
    # Resize web image
    web_image = resize_big_image(web_image, max_size=1800)
    logger.debug("Created image for WEB %s", web_image.size)

    # Create OCR image
    pil_images = split_landscape_images(pil_images)
    ocr_image = concatenate_images(pil_images, orientation="vertical")
    logger.debug("Created image for OCR %s", ocr_image.size)

    return web_image, ocr_image


def is_valid_pdf(pdf_path):
    """
    Verifies if a PDF is not corrupt, broken, or the path is incorrect.

    Parameters:
      pdf_path (str): full path to the PDF file.

    Returns:
      bool: True if the PDF is valid and can be read, False otherwise.
    """
    logger.debug("Start checking PDF validity")

    # Check if the file exists and the path is correct
    if not os.path.exists(pdf_path):
        logger.error("PDF file not found: %s", pdf_path)
        return False

    # Check if the path is a file (not a directory or other type)
    if not os.path.isfile(pdf_path):
        logger.error("The provided path is not a file: %s", pdf_path)
        return False

    # Try to open and read the PDF to check if it's valid
    try:
        # Open the PDF with PyPDF2
        logger.debug("%15s: %s", "Opening PDF", pdf_path)
        pdf = PdfReader(pdf_path)

        # Attempt to read the number of pages (this often fails for corrupt PDFs)
        logger.debug("Testing pages")
        num_pages = len(pdf.pages)
        logger.debug("%15s: %d", "PDF has pages", num_pages)

        # Try extracting text
        logger.debug("Testing text")
        total_text_length = sum(len(page.extract_text() or "") for page in pdf.pages)
        logger.debug("%15s: %d", "PDF has text", total_text_length)

        logger.debug("PDF integrity check passed.")

        return True

    except PdfReadError as e:
        logger.error("PDF read error for %s", pdf_path)
        logger.error("PDF read error: %s", str(e))

    except Exception as e:
        logger.error("Unexpected error for %s", pdf_path)
        logger.error("Unexpected error: %s", str(e))

    return False


def is_large_image_pil(img, min_size=300):
    """
    Check if a PIL.Image instance's dimensions are greater than the specified size.

    Parameters:
        img (PIL): A PIL Image instance.
        min_size (int): The minimum size threshold for both width and height (default is 300px).

    Returns:
        bool: True if both width and height are greater than min_size, False otherwise.
    """
    if not str(min_size).isdigit():
        return False

    width, height = img.size
    return width > int(min_size) and height > int(min_size)
