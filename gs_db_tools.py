"""
Some database helper functions for genscan

Is also used standalone to populate empty database
"""

# import csv  # Used for csv import
import logging
import re
import sys

# import requests # Used for web scrapping
# from bs4 import BeautifulSoup # Used for web scrapping
from sqlalchemy import MetaData, Table
from sqlalchemy.exc import (
    IntegrityError,
    MultipleResultsFound,
    NoSuchTableError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import aliased, joinedload, sessionmaker

from gs_db_models import City, Division, Document, FirstName, Template, engine

# from gs_helpers import separator_msg
# from pprint import pprint


# import time


logger = logging.getLogger("gsw_logger")


def get_db_session():
    """
    Create a session to a database

    Parameters:
      db_engine (class): database to use

    Return:
      Session() (session)
    """

    Session = sessionmaker(autoflush=False, autocommit=False, bind=engine)

    # Test if database is reachable
    try:
        session = Session()

        # Reflect the table from the database
        metadata = MetaData()
        cities_table = Table("cities", metadata, autoload_with=engine)

        # Perform a query to check for at least one record in the Cities table
        session.query(cities_table).first()
        logger.debug("Database session created successfully.")

        return session
    except OperationalError as e:
        print(f"Failed to create a session or connect to the database: {e}")
        logger.error("Failed to create a session or connect to the database: %s", e)
    except NoSuchTableError:
        print("A required table does not exist in the database.")
        logger.error("A required table does not exist in the database.")

    logger.info("%s", "-----------------App terminated------------------")
    sys.exit(1)


def update_db_gender_by_name(db_session, db_record):
    """
    Update the gender of a record.
    Add if first name does not appear in database.

    Parameters:
      db_session (class): database session to use
      db_record (class): information to use in database
    """

    # Gender can be for M, V or X

    # Find first name in database
    logger.debug("%15s: %s", "DB search for", db_record.first_name.title())
    db_firstname = (
        db_session.query(FirstName)
        .filter_by(first_name=db_record.first_name.title())
        .one_or_none()
    )

    if db_firstname:
        # First name appears in database
        logger.debug("%15s: %s", "First name", db_firstname.first_name)
        if db_firstname.gender != db_record.gender:
            logger.debug(
                "%15s: %s != %s", "Match", db_firstname.gender, db_record.gender
            )
            logger.debug("First name is multi gender")
            db_firstname.gender = None
            db_session.commit()
        else:
            logger.debug(
                "%15s: %s = %s", "Match", db_firstname.gender, db_record.gender
            )
            logger.debug("First name gender update not required")


def add_db_name_with_gender(db_session, db_record):
    """
    Add a record to a database.
    If already in database a check to update is done.

    Parameters:
      db_session (class): database session to use
      db_record (class): information to create in database
    """

    try:
        db_session.add(db_record)
        db_session.commit()
        logger.debug("First name and gender added")
        logger.debug("%15s: %s", "First name", db_record.first_name)
        logger.debug("%15s: %s", "Gender", db_record.gender)

        return True
    except IntegrityError:
        logger.debug("First name and gender known")
        logger.debug("%15s: %s", "First name", db_record.first_name)
        logger.debug("%15s: %s", "Gender", db_record.gender)
        logger.debug("Check if update is required")
        db_session.rollback()
        # first name already registered, check the current gender
        update_db_gender_by_name(db_session, db_record)

        return False


def update_db_gender_from_obituary(obituary, db_session):
    """
    Update gender in database based on first name and gender in obituary
    M=male, V=female, None=unknown

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (class): database session to use

    """

    # Set record information for the first name only in a string of
    # first names separated by white space
    db_record = FirstName(
        first_name=obituary.first_name.split()[0].strip().title(),
        gender=obituary.gender,
    )

    # Add to database if not existing, otherwise update in database
    add_db_name_with_gender(db_session, db_record)


def set_obituary_gender_by_name(obituary, db_session):
    """
    Set obituary gender to match what is known in the database.
    Finds gender based on the first part of the first name,
    as it usually indicates the gender.

    Parameters:
        obituary (Obituary object): Initial obituary information.
        db_session (Session): Database session to use.

    Returns:
        Obituary object: Updated obituary information with gender
                         (M = male, V = female, None = unknown).
    """
    logger.debug("Start processing obituary gender")

    if not (obituary.first_name or "").strip():
        obituary.gender = None
        logger.debug("No first name provided, skipping gender lookup")

        return obituary

    # Extract the first meaningful part of the first name.
    first_part = obituary.first_name.split()[0].split("-")[0].title()

    if not first_part:
        obituary.gender = None
        logger.debug("Empty first part extracted, skipping gender lookup")

        return obituary

    logger.debug("Looking up gender for: %s", first_part)

    try:
        # Query the database for the gender associated with the first part of the name.
        db_person = (
            db_session.query(FirstName).filter_by(first_name=first_part).one_or_none()
        )

        if db_person and db_person.gender in {"M", "V"}:
            obituary.gender = db_person.gender
            logger.debug("Gender found: %s", obituary.gender)
        else:
            obituary.gender = None
            logger.debug("No gender found in the database for: %s", first_part)

    except Exception as e:
        obituary.gender = None
        logger.error("Error during gender lookup for %s: %s", first_part, str(e))

    return obituary


def set_division_id(obituary, db_session):
    """
    Set obituary division id to match what is known in database

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (class): database session to use

    Return:
      obituary (Obituary object): updated obituary information
    """

    division_slug = obituary.division_slug

    if len(division_slug) > 0:
        logger.debug("%15s: %s", "Lookup for", division_slug)

        db_division = (
            db_session.query(Division).filter_by(slug=division_slug).one_or_none()
        )

        if db_division:
            obituary.division_id = db_division.id
        else:
            obituary.division_id = None

        logger.debug("%15s: %s", "Found division ID", obituary.division_id)
    else:
        obituary.division_id = None
        logger.debug("%15s: %s", "Lookup", "no slug given, skipping")

    return obituary


def set_obituary_priority_by_slug(obituary, db_session):
    """
    Set obituary priority based on division priority known in database

    Parameters:
      obituary (Obituary object): initial obituary information
      db_session (class): database session to use

    Return:
      obituary (Obituary object): updated obituary information
    """

    division_slug = obituary.division_slug

    if len(division_slug) > 0:
        logger.debug("%15s: %s", "Lookup for", division_slug)

        db_division = (
            db_session.query(Division).filter_by(slug=division_slug).one_or_none()
        )

        if db_division:
            obituary.wp_priority = db_division.priority
        else:
            obituary.wp_priority = None

        logger.debug("%15s: %s", "Found priority", obituary.wp_priority)
    else:
        obituary.division_id = None
        logger.debug("%15s: %s", "Lookup", "no slug given, skipping")

    return obituary


def get_city_info(db_session, city):
    """
    Find city based on database containing city names and related country

    Parameters:
      db_session (class): database session to use
      city (string): name to find

    Return:
      city (string): city name fond or None
      country (string): country if known or None
    """

    db_city = db_session.query(City).filter_by(city=city).one_or_none()
    if db_city:
        logger.debug("Found city: %s", db_city)

        return db_city.city, db_city.country

    logger.debug("Found city: None")

    return None, None


def get_division_by_id(db_session, division_id):
    """
    Retrieve a division record from the database using its ID.

    Parameters:
        db_session (Session): The SQLAlchemy database session object.
        division_id (int): The ID of the division to retrieve.

    Returns:
        Division: The division record if found; otherwise, None.

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    # Validate division_id
    if not isinstance(division_id, int) or division_id <= 0:
        logger.error(
            "Invalid division_id: %s. Must be a positive integer.", division_id
        )
        db_division = None
    else:
        try:
            db_division = (
                db_session.query(Division).filter_by(id=division_id).one_or_none()
            )
            logger.debug("Division found: %s", db_division.name)

        except SQLAlchemyError as e:
            logger.error(
                "Database error occurred while retrieving division: %s", str(e)
            )
            db_division = None
        except Exception as e:
            logger.error("An unexpected error occurred: %s", str(e))
            db_division = None

    return db_division


def get_divisions_processed_count(db_session):
    """
    Retrieve all division slugs from the database with processed and web document count.

    Parameters:
        db_session (Session): The SQLAlchemy database session object.

    Returns:
        db_divisions (db records): The division records if found; otherwise, None.

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    try:
        db_divisions = db_session.query(
            Division.slug, Division.processed_last_run, Division.count_on_site
        ).all()
        logger.debug("%15s: %s", "Divisions found", len(db_divisions))

    except SQLAlchemyError as e:
        logger.error("Database error occurred while retrieving division: %s", str(e))
        db_divisions = None
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        db_divisions = None

    return db_divisions


def get_division_export(db_session, division_slug):
    """
    Get the status of index creation from database based on slug

    Parameters:
        db_session (class): database session to use
        division_slug (string): slug to find

    Return:
        db_division (record): database record for found division or None

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    try:
        db_division = (
            db_session.query(Division.slug, Division.export)
            .filter_by(slug=division_slug)
            .one_or_none()
        )
        logger.debug("Export found: %s", db_division.export)

    except SQLAlchemyError as e:
        logger.error("Database error occurred while retrieving division: %s", str(e))
        db_division = None

    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        db_division = None

    return db_division


def get_division_diacritics(db_session, division_slug):
    """
    Get the status of diacritics removal from database based on slug

    Parameters:
        db_session (class): database session to use
        division_slug (string): slug to find

    Return:
        change_diacritics (bool): True or False

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    change_diacritics = False
    try:
        db_division = get_division_by_slug(db_session, division_slug)
        change_diacritics = bool(db_division.remove_diacritics)

    except SQLAlchemyError as e:
        logger.error("Database error occurred while retrieving division: %s", str(e))
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))

    logger.debug("Diacritics required: %s", change_diacritics)
    return change_diacritics


def get_division_short_names(db_session, division_slug):
    """
    Get the status of short names use from database based on slug

    Parameters:
        db_session (class): database session to use
        division_slug (string): slug to find

    Return:
        use_short_names (bool): True or False

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    use_short_names = False
    try:
        db_division = get_division_by_slug(db_session, division_slug)
        use_short_names = bool(db_division.short_names)

    except SQLAlchemyError as e:
        logger.error("Database error occurred while retrieving division: %s", str(e))
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))

    logger.debug("Short names required: %s", use_short_names)
    return use_short_names


def get_division_by_slug(db_session, division_slug):
    """
    Find division in database based on slug

    Parameters:
        db_session (class): database session to use
        division_slug (string): slug to find

    Return:
        db_division (record): database record for found division or None

    Raises:
        SQLAlchemyError: If a database error occurs during the query.
    """

    try:
        db_division = (
            db_session.query(Division)
            .options(joinedload(Division.templates))
            .filter_by(slug=division_slug)
            .one_or_none()
        )
        logger.debug("Division found: %s", db_division.name)

    except SQLAlchemyError as e:
        logger.error("Database error occurred while retrieving division: %s", str(e))
        db_division = None
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        db_division = None

    return db_division


def get_file_template(db_session, obituary, action):
    """
    Find file template in database based on division slug and document type

    Parameters:
        db_session (class): database session to use
        obituary (class): obituary information
        action (string): read or write

    Return:
        file_template (string): the file template found or default
    """

    document_type = obituary.obituary_type
    division_slug = obituary.division_slug

    logger.debug("%15s: %s", "Division", division_slug)
    logger.debug("%15s: %s", "Doc type", document_type)
    logger.debug("%15s: %s", "Action", action)

    default_template = (
        r"{ln}_{fn}_{by}{bm}{bd}_{dy}{dm}{dd}"
        if action.lower() == "read"
        else r"{ln}_{fn}_{by|0000}{bm|00}{bd|00}_{dy|0000}{dm|00}{dd|00}"
    )

    TemplateAlias = aliased(Template)

    file_template = (
        db_session.query(TemplateAlias.format)
        .join(Division.templates.of_type(TemplateAlias))
        .filter(
            Division.slug == division_slug.lower(),
            TemplateAlias.type == document_type.lower(),
            TemplateAlias.source == "files",
            TemplateAlias.operation == action.lower(),
        )
        .one_or_none()
    )

    found_template = file_template[0] if file_template else None
    logger.debug("%15s: %s", "Template(found)", found_template)
    file_template = found_template if found_template else default_template
    logger.debug("%15s: %s", "Template(used)", file_template)

    return file_template


def increment_processed_counter(obituary, db_session):
    """
    Increase by one the number of documents downloaded for the division of the obituary

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        # Increment total documents processed for the division
        db_division.processed += 1
        logger.debug(
            "%20s: %s (%s)", "Total +1", db_division.name, db_division.processed
        )

        # Increment documents count of fully processed documents
        db_division.processed_last_run += 1
        logger.debug(
            "%20s: %s (%s)",
            "Down Last Run +1",
            db_division.name,
            db_division.processed_last_run,
        )

        update_record_in_db(db_session)


def decrement_processed_counter(obituary, db_session):
    """
    Decrease by one the number of documents downloaded for the division of the obituary

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        db_division.processed_last_run -= 1
        logger.debug(
            "%20s: %s (%s)",
            "Down Last Run -1",
            db_division.name,
            db_division.processed_last_run,
        )

        update_record_in_db(db_session)


def increment_site_counter(obituary, db_session):
    """
    Increase by 1 the number of documents available at the site for the division of the obituary

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        # Increment documents at the site for the division
        db_division.count_on_site += 1
        logger.debug(
            "%20s: %s (%s)", "On Site +1", db_division.name, db_division.count_on_site
        )

        update_record_in_db(db_session)


def decrement_site_counter(obituary, db_session):
    """
    Decrease by 1 the number of documents available at the site for the division of the obituary

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        # Decrement documents at the site for the division
        if db_division.count_on_site > 0:
            db_division.count_on_site -= 1
        logger.debug(
            "%20s: %s (%s)", "On Site -1", db_division.name, db_division.count_on_site
        )

        update_record_in_db(db_session)


def increment_uploaded_counter(obituary, db_session):
    """
    Increase by 1 the number of documents uploaded to the site during last run

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        # Increment total documents processed for the division
        db_division.uploaded_last_run += 1
        logger.debug(
            "%20s: %s (%s)",
            "Up Last Run +1",
            db_division.name,
            db_division.uploaded_last_run,
        )

        update_record_in_db(db_session)


def decrement_uploaded_counter(obituary, db_session):
    """
    Decrease by 1 the number of documents uploaded to the site during last run

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    db_division = get_division_by_slug(db_session, obituary.division_slug)
    if db_division:
        # Decrement total documents processed for the division
        db_division.uploaded_last_run -= 1
        logger.debug(
            "%20s: %s (%s)",
            "Up Last Run -1",
            db_division.name,
            db_division.uploaded_last_run,
        )

        update_record_in_db(db_session)


def reset_processed_last_run(db_session):  # Not used - 2024-09-28 - kdo
    """
    Resets the counter for the processed documents of the last run to zero for all divisions

    Parameters:
      db_session (class): database session to use

    """

    db_session.query(Division).update({"processed_last_run": 0})
    db_session.commit()


def add_record_to_db(db_session, db_record):
    """
    Add update a record to the database if unknown
    Updates record if known

    Parameters:
      db_session (class): database session to use
      db_record (class): record to create/update in database
    """

    try:
        db_session.add(db_record)
        db_session.commit()
        logger.debug("Record added")

        return True
    except IntegrityError as e:
        db_session.rollback()
        logger.error("%15s: %s", "Integrity error", e)
        logger.debug("Adding record failed")

        return False


def update_record_in_db(db_session):
    """
    Update a record to the database

    Parameters:
      db_session (class): database session to use
      db_record (class): information to create in database
    """

    try:
        db_session.commit()
        logger.debug("Record updated")

        return True
    except IntegrityError:
        db_session.rollback()
        logger.debug("Record update failed")

        return False


def update_division_in_db(db_session, post):
    """
    Update a division and related templates in the database

    Parameters:
      db_session (class): database session to use
      post (dict): WordPress post information
    """

    # Ugly routine, but it seems to work
    division = get_division_by_slug(db_session, post.get("slug"))

    # Does record exist in database or not
    if division is None:
        # Create record
        division = Division()

    # Add/Update data anyway
    division.id = post.get("id")
    division.name = post.get("acf").get("naam_afdeling")
    division.slug = post.get("slug")
    division.email = post.get("acf").get("email")
    division.single_check = post.get("acf").get("enkele_verificatie")
    division.short_names = post.get("acf").get("verkorte_naam")
    division.remove_diacritics = post.get("acf").get("vervang_diakritische_tekens")
    division.export = post.get("acf").get("export")
    division.last_names_capitalized = post.get("acf").get("familienaam_groot")
    division.last_names_no_diacritics = post.get("acf").get(
        "familienaam_zonder_diacritics"
    )
    division.first_names_no_diacritics = post.get("acf").get(
        "voornaam_zonder_diacritics"
    )
    division.priority = post.get("acf").get("prioriteit_afdeling")
    division.processed_last_run = 0
    division.uploaded_last_run = 0

    # Go thru all post templates
    for acf_template_type, acf_templates in post.get("acf").get("templates").items():
        for acf_source, acf_operations in acf_templates.items():
            for acf_operation, acf_format in acf_operations.items():

                # Go thru all db templates to verify if it exists already
                for db_template in division.templates:
                    # Update existing db template
                    if (
                        db_template.type == acf_template_type.lower()
                        and db_template.source == acf_source.lower()
                        and db_template.operation == acf_operation.lower()
                    ):
                        db_template.format = lowercase_within_brackets(acf_format)
                        break
                else:
                    # Add missing db template
                    db_template = Template()
                    db_template.type = acf_template_type.lower()
                    db_template.format = lowercase_within_brackets(acf_format)
                    db_template.source = acf_source.lower()
                    db_template.operation = acf_operation.lower()
                    division.templates.append(db_template)

    # Add to database if not exist. Updates if it does exist.
    add_record_to_db(db_session, division)


def lowercase_within_brackets(text):
    """
    Replaces uppercase letters between curly brackets with lower case ones,
    leaving other uppercase letters untouched

    Parameter:
      text (str): String to process
    """
    # With the help of chatgpt

    # Define the replacement function for matches
    def replace_uppercase(match):
        # Get the content inside the brackets
        content = match.group(1)

        # Transform uppercase letters to lowercase
        transformed = "".join(
            char.lower() if char.isupper() else char for char in content
        )

        # Return the modified content wrapped in curly braces
        return f"{{{transformed}}}"

    # Apply the regex pattern and replacement function
    return re.sub(r"\{([^\}\{}]*)\}", replace_uppercase, text)


def update_db_documents(obituary, db_session):
    """
    Update document information in the database

    Parameters:
      obituary (Obituary class): session to web site
      db_session (class): database session to use
    """

    # Assume record is known in database
    db_record_exists = True

    # Check for known database record
    db_document = (
        db_session.query(Document)
        .filter_by(wp_post_id=obituary.wp_post_id, obituary_id=obituary.obituary_id)
        .one_or_none()
    )

    if db_document is None:
        # Does not exist, create record
        db_document = Document()
        db_record_exists = False

        # Set some upload fields
        db_document.ocr_text = obituary.ocr_text
        db_document.file_path = obituary.file_path
        db_document.folder_name = obituary.folder_name
        db_document.file_base_name = obituary.file_base_name
        db_document.wp_featured_media = obituary.wp_featured_media
        db_document.wp_web_image_path = obituary.wp_web_image_path
        db_document.wp_image_posted = obituary.wp_image_posted
        db_document.wp_post_posted = obituary.wp_post_posted
        db_document.processing_time = obituary.processing_time
        db_document.wp_post_id = obituary.wp_post_id

    if db_record_exists:
        # Flag if certain fields changed from original
        if db_document.box_number != obituary.box_number:
            db_document.box_number_modified = True
        if db_document.document_number != obituary.document_number:
            db_document.document_number_modified = True
        if db_document.obituary_type != obituary.obituary_type.lower():
            db_document.obituary_type_modified = True
        if db_document.first_name != obituary.first_name:
            db_document.first_name_modified = True
        if db_document.last_name != obituary.last_name:
            db_document.last_name_modified = True
        if db_document.birth_place != obituary.birth_place:
            db_document.birth_place_modified = True
        if db_document.birth_year != obituary.birth_year:
            db_document.birth_year_modified = True
        if db_document.birth_month != obituary.birth_month:
            db_document.birth_month_modified = True
        if db_document.birth_day != obituary.birth_day:
            db_document.birth_day_modified = True
        if db_document.death_place != obituary.death_place:
            db_document.death_place_modified = True
        if db_document.death_year != obituary.death_year:
            db_document.death_year_modified = True
        if db_document.death_month != obituary.death_month:
            db_document.death_month_modified = True
        if db_document.death_day != obituary.death_day:
            db_document.death_day_modified = True
        if db_document.gender != obituary.gender:
            db_document.gender_modified = True
        if db_document.face != obituary.face:
            db_document.face_modified = True

        # Set some fields per existing data in database
        # db_document.ocr_text = db_document.ocr_text
        # db_document.file_path = db_document.file_path
        # db_document.folder_name = db_document.folder_name
        # db_document.file_base_name = db_document.file_base_name
        # db_document.wp_featured_media = db_document.wp_featured_media
        # db_document.wp_web_image_path = db_document.wp_web_image_path
        # db_document.wp_image_posted = db_document.wp_image_posted
        # db_document.wp_post_posted = db_document.wp_post_posted
        # db_document.processing_time = db_document.processing_time

    # Convert rest of obituary data to database record
    db_document.obituary_id = obituary.obituary_id
    db_document.wp_post_status = obituary.wp_post_status
    db_document.wp_editor = obituary.wp_editor
    db_document.wp_edited_on = obituary.wp_edited_on
    db_document.wp_edit_time = obituary.wp_edit_time
    db_document.wp_reviewer = obituary.wp_reviewer
    db_document.wp_reviewed_on = obituary.wp_reviewed_on
    db_document.wp_review_time = obituary.wp_review_time
    db_document.content = obituary.content
    db_document.file_name = obituary.file_name
    db_document.new_file_name = obituary.new_file_name
    db_document.box_number = obituary.box_number
    db_document.document_number = obituary.document_number
    db_document.obituary_type = obituary.obituary_type.lower()
    db_document.first_name = obituary.first_name
    db_document.last_name = obituary.last_name
    db_document.birth_place = obituary.birth_place
    db_document.birth_year = obituary.birth_year
    db_document.birth_month = obituary.birth_month
    db_document.birth_day = obituary.birth_day
    db_document.death_place = obituary.death_place
    db_document.death_year = obituary.death_year
    db_document.death_month = obituary.death_month
    db_document.death_day = obituary.death_day
    db_document.gender = obituary.gender
    db_document.face = obituary.face
    db_document.note = obituary.note
    db_document.division_id = obituary.division_id
    db_document.division_slug = obituary.division_slug
    db_document.wp_post_removed = obituary.wp_post_removed
    db_document.wp_image_removed = obituary.wp_image_removed
    db_document.wp_priority = obituary.wp_priority

    log_field_values(db_document)

    # Add to database if not exist or will update if it does exist.
    logger.debug("Try adding to documents database")
    db_result = add_record_to_db(db_session, db_document)
    if not db_result:
        logger.error("Failed adding to documents database")


def update_db_cities(city, country, db_session):
    """
    Find and update cities database if required

    Parameters:
        city (string)
        country (string)
        db_session (db session)

    Return:
        city (string): city name, possibly corrected
        country (string): 2-letter ISO code for country
    """

    city = city.capitalize()
    country = country.upper()

    # Check for known database record
    try:
        db_city = db_session.query(City).filter_by(city=city).one_or_none()
    except MultipleResultsFound:
        # Multiple cities in different countries found
        #
        logger.debug("City %s found in multiple countries", city)

        return city, country

    if db_city is None:
        # Does not exist, create record
        db_city = City(city=city, country=country)
    else:
        city = db_city.city
        country = db_city.country

    # Add to database if not exist or will update if it does exist.
    logger.debug("Try adding to cities database")
    db_result = add_record_to_db(db_session, db_city)
    if not db_result:
        logger.error("Failed adding to cities database")

    return city, country


def print_field_values(instance):
    """
    Print record fields

    Parameters:
      instance (sqlalchemy class): record to print
    """
    for key, value in instance.__dict__.items():
        if not key.startswith("_"):
            print(f"{key}: {value}")


def log_field_values(instance):
    """
    Log record fields

    Parameters:
      instance (sqlalchemy class): record to log
    """
    for key, value in instance.__dict__.items():
        if not key.startswith("_"):
            logger.debug("%25s:%8s: %s", key, type(value).__name__, value)


# def read_csv_file(filename):
#     """
#     Read a csv file

#     Parameters:
#         filename (string): path to csv file
#     """
#     data = []
#     with open(filename, "r", encoding="utf-8-sig") as csv_file:
#         csv_reader = csv.reader(csv_file, delimiter=";")
#         for row in csv_reader:
#             data.append(row)
#     return data


# def add_cities_to_db() -> None:
#     """
#     Adding cities and related country from csv file into database
#     """
#     filename = "Gemeentenlijst.csv"
#     csv_cities = read_csv_file(filename)

#     with get_db_session() as session:
#         for csv_city in csv_cities:
#             city = City(city=csv_city[0].strip(), country=csv_city[1].strip())
#             result = add_record_to_db(session, city)
#             print(city, result)


# def scrape_firstnames_with_gender() -> None:
#     """
#     Main routine that gets first names and the gender from internet to populate database
#     """

#     start = 0
#     end = 0  # see site for max entries
#     step = 100

#     if start == end:
#         return
#     with get_db_session() as session:
#         for page in range(start, end, step):
#             print(f"====== {page}/{end} ======")
#             url = f"http://names.be/voornamen.html?met=&sort=alpha&s={page}&limit=100"

#             result = requests.get(url, timeout=10)
#             doc = BeautifulSoup(result.text, "html.parser")
#             table = doc.find(["table"], class_="data")
#             trs = table.find_all("tr")

#             for tr in trs:
#                 image, name, count = tr.find_all("td")[1:4]

#                 if count.string[0].isdigit():
#                     if int(count.string[0:]) > 20:
#                         img_src = image.find("img")["src"]
#                         if img_src.startswith("male"):
#                             gender = "M"
#                         elif img_src.startswith("female"):
#                             gender = "V"
#                         else:
#                             gender = None
#                         print(
#                             f"    {name.string.strip()} : {gender} ({count.string.strip()})"
#                         )
#                         person = FirstName(
#                             first_name=name.string.strip(), gender=gender
#                         )
#                         # Add person's first name with gender to FirstNames table
#                         result = add_db_name_with_gender(session, person)

#             time.sleep(1)


if __name__ == "__main__":
    # Only used to populate empty database
    # scrape_firstnames_with_gender()
    # add_cities_to_db()
    pass
