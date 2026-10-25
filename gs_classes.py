"""
Class definitions
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime

# from gs_file_tools import create_file_name
from gs_helpers import clean_html, find_regex_in_string, generate_rand


@dataclass()
class Obituary:
    """
    Obituary information we need to gather
    """

    # All wordpress post data
    # wp_post_data: dict

    # Post attributes
    wp_post_id: int = None
    wp_post_status: str = ""
    wp_editor: str = ""
    wp_reviewer: str = ""
    wp_post_posted: bool = False
    wp_image_posted: bool = False
    wp_post_removed: bool = False
    wp_image_removed: bool = False
    wp_web_image_path: str = ""
    wp_featured_media: int = None
    # wp_post_link: str = field(init=False)
    wp_edit_time: int = None
    wp_review_time: int = None
    wp_edited_on: datetime = None
    wp_reviewed_on: datetime = None
    wp_priority: int = 10

    # File attributes
    file_path: str = ""
    folder_name: str = field(init=False)
    file_name: str = field(init=False)
    file_base_name: str = field(init=False)
    new_file_name: str = field(init=False)
    # review: bool = field(init=False)

    # Document attributes
    division_id: int = 0
    division_slug: str = field(init=False)
    obituary_type: str = field(init=False, default="rb")
    box_number: str = field(init=False, default="")
    document_number: str = field(init=False, default="")

    # OCR attributes
    content: str = ""
    ocr_text: str = ""

    # Person attributes
    first_name: str = ""
    last_name: str = ""
    birth_place: str = ""
    birth_year: str = ""
    birth_month: str = ""
    birth_day: str = ""
    death_place: str = ""
    death_year: str = ""
    death_month: str = ""
    death_day: str = ""

    # Additional info
    gender: str = None  # M, V, X, None
    face: bool = False
    note: str = ""

    # Other info
    date: str = field(
        init=False, default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    )
    obituary_id: str = field(init=False, default_factory=generate_rand)
    processing_time: float = 0

    # Set values for some variables based on other variables
    def __post_init__(self):
        self.folder_name, self.file_name = os.path.split(self.file_path)
        self.file_base_name, extension = os.path.splitext(self.file_name)
        # example:
        # folder_name    = "<workdir>\divisions\_ieper-diksmuide\Ieper-Diksmuide_2024_03"
        # file_name      = "Adam_Ginette_19570626_20240322.pdf"
        # file_base_name = "Adam_Ginette_19570626_20240322"
        self.obituary_id = f"{self.file_base_name}_{self.obituary_id}"
        self.new_file_name = f"{self.obituary_id}{extension}"
        self._get_box_number()
        self._get_document_number()
        self._set_obituary_type()
        self._set_division()

    def _get_box_number(self):
        # Dedicated to FV Brugge
        # Looks for 'doos ###' in filepath
        # Returns number '###'
        box_found = re.search(
            r"(?:doos\s*)(\d{1,}).*?[\\/]\d{1,}\.",
            self.file_path.lower(),
            flags=re.IGNORECASE,
        )
        if bool(box_found):
            if bool(box_found.group(1)):
                self.box_number = box_found.group(1)

    def _get_document_number(self):
        # Dedicated to FV Brugge
        # Looks for '\######.pdf' in filepath
        # Returns number '######'
        doc_found = re.search(
            r"(?:doos\s*)\d{1,}.*?[\\/](\d{1,})\.",
            self.file_path.lower(),
            flags=re.IGNORECASE,
        )
        if bool(doc_found):
            if bool(doc_found.group(1)):
                self.document_number = doc_found.group(1).zfill(7)

    def _set_obituary_type(self):
        lower_file_path = self.file_path.lower()
        file_keywords = {
            "bidprentje": "bp",
            "overlijdensbericht": "ob",
            "krantenbericht": "kb",
            "krantenoverlijdensbericht": "ko",
        }
        for keyword, obit_type in file_keywords.items():
            if keyword in lower_file_path:
                self.obituary_type = obit_type
                break
        # else:
        #     self.obituary_type = "rb"

    def _set_division(self):
        # Get division slug from file path to use for db lookup.
        # First look right after the divisions folder (.../divisions/_slug/),
        # then fall back to the first folder starting with "_".
        # Both / and \ are accepted, so it works on Windows and macOS.
        self.division_slug = ""
        regex = r"[\\/]divisions[\\/](_[^\\/]+)[\\/]"
        regex_return = find_regex_in_string(self.file_path.lower(), regex)
        if not regex_return:
            regex = r"[\\/](_.*?)[\\/]"
            regex_return = find_regex_in_string(self.file_path.lower(), regex)
        if bool(regex_return):
            if regex_return.group(1) not in ("_ignore", "_corrupt", "_failed"):
                self.division_slug = regex_return.group(1)
            return


@dataclass()
class ObituaryPost:
    """
    Obituary information we need to gather from the WP post
    """

    # All wordpress post data
    wp_post_data: dict

    # Post attributes
    wp_post_id: int = field(init=False)
    wp_post_status: str = field(init=False)
    wp_editor: int = field(init=False)
    wp_reviewer: int = field(init=False)
    wp_post_posted: bool = False
    wp_image_posted: bool = False
    wp_post_removed: bool = False
    wp_image_removed: bool = False
    wp_web_image_path: str = field(init=False)
    wp_featured_media: int = None
    wp_post_link: str = field(init=False)
    wp_edit_time: int = field(init=False)
    wp_review_time: int = field(init=False)
    wp_edited_on: datetime = field(init=False)
    wp_reviewed_on: datetime = field(init=False)
    wp_priority: int = field(init=False)

    # File attributes
    file_path: str = ""
    folder_name: str = field(init=False)
    file_name: str = field(init=False)
    file_base_name: str = ""
    new_file_name: str = ""
    review: bool = field(init=False)

    # Document attributes
    division_id: int = field(init=False)
    division_slug: str = field(init=False)
    obituary_type: str = field(init=False)
    box_number: str = field(init=False)
    document_number: str = field(init=False)

    # OCR attributes
    content: str = field(init=False)
    ocr_text: str = ""

    # Person attributes
    first_name: str = field(init=False)
    last_name: str = field(init=False)
    birth_place: str = field(init=False)
    birth_year: str = field(init=False)
    birth_month: str = field(init=False)
    birth_day: str = field(init=False)
    death_place: str = field(init=False)
    death_year: str = field(init=False)
    death_month: str = field(init=False)
    death_day: str = field(init=False)

    # Additional info
    gender: str = field(init=False)
    face: bool = field(init=False)
    note: str = field(init=False)

    # Other info
    # date: str = field(
    #     init=False, default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    # )
    obituary_id: str = field(init=False)
    processing_time: float = 0

    # Set values for some variables based on other variables
    def __post_init__(self):
        # Post attributes
        self.wp_post_id = self.wp_post_data["id"]
        self.obituary_id = self.wp_post_data["title"]["rendered"]
        self.wp_post_status = self.wp_post_data["acf"]["verwerkingsstatus"]
        self.wp_editor = self.wp_post_data["acf"]["bewerker"]
        self.wp_reviewer = self.wp_post_data["acf"]["verwerker"]
        self.wp_post_link = self.wp_post_data["_links"]["self"][0]["href"]
        self.wp_web_image_path = self.wp_post_data["_links"]["wp:featuredmedia"][0][
            "href"
        ]
        self.wp_edit_time = self.wp_post_data["acf"]["bewerkingstijd"]
        self.wp_review_time = self.wp_post_data["acf"]["verwerkingstijd"]
        iso_format = self.wp_post_data["acf"]["bewerkt_op"]
        self.wp_edited_on = datetime.fromisoformat(iso_format) if iso_format else None
        iso_format = self.wp_post_data["acf"]["verwerkt_op"]
        self.wp_reviewed_on = datetime.fromisoformat(iso_format) if iso_format else None
        self.wp_priority = self.wp_post_data["acf"]["prioriteit"]

        # File attributes
        self.folder_name = self.wp_post_data["acf"]["originele_folder"]
        self.file_name = self.wp_post_data["acf"]["originele_bestandsnaam"]
        self.review = self.wp_post_data["acf"]["nazicht"]

        # Document attributes
        self.division_id = self.wp_post_data["acf"]["afdeling"]
        self.division_slug = self.wp_post_data["acf"]["afdeling_fv_alternatief"]
        self.obituary_type = self.wp_post_data["acf"]["type_overlijdensbericht"]
        self.box_number = self.wp_post_data["acf"]["doos"]
        self.document_number = self.wp_post_data["acf"]["document_nummer"]

        # OCR attributes
        self.content = clean_html(self.wp_post_data["content"]["rendered"])

        # Person attributes
        self.first_name = self.wp_post_data["acf"]["voornaam"]
        self.last_name = self.wp_post_data["acf"]["familienaam"]
        self.birth_place = self.wp_post_data["acf"]["geboorteplaats"]
        self.birth_year = self.wp_post_data["acf"]["geboortedatum"]["geboortejaar"]
        self.birth_month = self.wp_post_data["acf"]["geboortedatum"]["geboortemaand"]
        self.birth_day = self.wp_post_data["acf"]["geboortedatum"]["geboortedag"]
        self.death_place = self.wp_post_data["acf"]["overlijdensplaats"]
        self.death_year = self.wp_post_data["acf"]["overlijdensdatum"][
            "overlijdensjaar"
        ]
        self.death_month = self.wp_post_data["acf"]["overlijdensdatum"][
            "overlijdensmaand"
        ]
        self.death_day = self.wp_post_data["acf"]["overlijdensdatum"]["overlijdensdag"]

        # Additional info
        self.gender = self.wp_post_data["acf"]["gender"]
        self.face = self.wp_post_data["acf"]["foto"]
        self.note = self.wp_post_data["acf"]["nota"]
