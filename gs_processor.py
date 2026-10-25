"""
GenScan files processing tools
"""

import logging
import os
import string

from codetiming import Timer, TimerError

import gs_config
from gs_ai_tools import (
    AIServiceError,
    ai_enabled,
    check_ai_service,
    clear_failure,
    extract_with_ai,
    register_failure,
)
from gs_classes import Obituary, ObituaryPost
from gs_db_tools import (
    decrement_site_counter,
    get_division_by_slug,
    get_divisions_processed_count,
    increment_processed_counter,
    increment_site_counter,
    set_division_id,
    set_obituary_gender_by_name,
    set_obituary_priority_by_slug,
    update_db_documents,
    update_db_gender_from_obituary,
    update_division_in_db,
)
from gs_file_tools import (
    count_files_in_folders,
    create_base_folders,
    create_simple_folder,
    delete_file,
    get_file_paths,
    move_corrupt_file,
    move_file,
)
from gs_helpers import (
    clean_ocr_text,
    clean_up_text,
    convert_diacritics,
    find_info_in_filepath,
    find_life_info,
    get_name,
    get_note_info,
    join_data,
    log_info_results,
    normalize_city_names,
    readable_ocr_text,
    separator_msg,
    set_new_file_name,
)
from gs_image_tools import (
    create_images_with_pdf2im,
    create_working_images,
    extract_text_with_pypdf2,
    has_face,
    is_large_image_pil,
    is_valid_pdf,
    open_image,
    save_image_as_pdf,
    save_web_image,
)
from gs_ocr_tools import extract_ocr_data
from gs_wp_tools import (
    delete_wp_post,
    get_custom_api_values,
    get_post_count,
    get_posts_to_process,
    process_upload,
)
from gs_xl_tools import add_row_to_index

# Load FVO specific function(s) if module exists
try:
    from gs_xl_tools_FVO import add_row_to_index as add_row_to_index_fvo

    RUN_FVO_FUNCTIONS = True
except ModuleNotFoundError:
    RUN_FVO_FUNCTIONS = False

# import sys
# from pprint import pprint


# Activate logger
logger = logging.getLogger("gsw_logger")


def print_info_results(info):
    """
    Printing all information to console in debug mode.

    Parameters:
      info (class): The collected information
    """

    if isinstance(info, Obituary) and logger.level <= logging.INFO:
        print(f"   afdeling : {info.division_slug[1:].upper()}")
        print(f"     folder : {os.path.basename(os.path.normpath(info.folder_name))}")
        print(
            f"       naam : \033[32m{info.first_name}, {info.last_name}\033[0m",
            flush=True,
        )
        birth_date = "0000-" if info.birth_year is None else f"{info.birth_year}-"
        birth_date += (
            "00-" if info.birth_month is None else f"{str(info.birth_month):0>2}-"
        )
        birth_date += "00" if info.birth_day is None else f"{str(info.birth_day):0>2}"
        print(
            f"    geboren : \033[33m{info.birth_place} ({birth_date})\033[0m",
            flush=True,
        )
        death_date = "0000-" if info.death_year is None else f"{info.death_year}-"
        death_date += (
            "00-" if info.death_month is None else f"{str(info.death_month):0>2}-"
        )
        death_date += "00" if info.death_day is None else f"{str(info.death_day):0>2}"
        print(
            f"  overleden : \033[34m{info.death_place} ({death_date})\033[0m",
            flush=True,
        )
        print(f"     gender : \033[35m{info.gender}\033[0m", flush=True)
        print(f"       foto : \033[36m{info.face}\033[0m", flush=True)
        print(f"       note : \033[37m{info.note}\033[0m", flush=True)
        # print(f"ocr text : {info.ocr_text}", flush=True)


def log_timer_info(timer):
    """
    Log the timer information.

    Parameters:
      timer (class): A timer
    """

    if not isinstance(timer, Timer) or not -1 < logger.level <= logging.INFO:
        logger.debug("No timer info available")
        return

    logger.info(separator_msg(timer.name))

    try:
        logger.info("%15s : %s", "Processed", Timer.timers.count(timer.name))
    except KeyError:
        logger.debug("No time registered for %s", timer.name)
        return

    logger.info("%15s : %.2fs", "Total time", Timer.timers.total(timer.name))
    logger.info("%15s : %.2fs", "Minimum", Timer.timers.min(timer.name))
    logger.info("%15s : %.2fs", "Maximum", Timer.timers.max(timer.name))
    logger.info("%15s : %.2fs", "Average", Timer.timers.mean(timer.name))
    logger.info("%15s : %.2fs", "Median", Timer.timers.median(timer.name))
    logger.info("%15s : %.2fs", "Std.Dev", Timer.timers.stdev(timer.name))

    logger.info(separator_msg(timer.name))


def log_timer_info_csv(timer):
    """
    Log the timer information in CSV style.

    Parameters:
        timer (Timer): A timer instance.
    """
    if not isinstance(timer, Timer) or not -1 < logger.level <= logging.INFO:
        logger.debug("No timer info available")
        return

    try:
        count = Timer.timers.count(timer.name)
        total = Timer.timers.total(timer.name)
        min_time = Timer.timers.min(timer.name)
        max_time = Timer.timers.max(timer.name)
        mean_time = Timer.timers.mean(timer.name)
        median_time = Timer.timers.median(timer.name)
        stdev_time = Timer.timers.stdev(timer.name)
    except KeyError:
        logger.debug("No time registered for %s", timer.name)
        return

    # Use a list for efficient string construction
    log_values = [
        timer.name,
        str(count),
        f"{total:.2f}",
        f"{min_time:.2f}",
        f"{max_time:.2f}",
        f"{mean_time:.2f}",
        f"{median_time:.2f}",
        f"{stdev_time:.2f}",
    ]
    timer_log_line = ",".join(log_values)

    logger.info(timer_log_line)


def process_prep(web_session, db_session):
    """
    Setting up some stuff before actually processing documents

    Parameters:
      web_session (web_session object): Request web_session object
      db_session (sql session): SQLAlchemy session

    """

    logger.info("%s", separator_msg("Pre-processing", "_"))
    print(f'\033[34m{separator_msg("Pre-processing", "-", 30)}\033[0m', flush=True)

    # Create base folders
    create_base_folders(gs_config.APP_CONFIG["working_folder"])
    print("Basis folders zijn aanwezig")

    # Check website status
    site_url = gs_config.APP_CONFIG["wp_site"]

    # Get list of divisions ready for processing
    divisions = get_posts_to_process(web_session, site_url, "afdeling")
    divisions_count = len(divisions)
    logger.debug("Divisions on site: %s", divisions_count)
    if divisions_count == 0:
        print("Geen afdelingen beschikbaar op website")
        logger.debug("No afdelingen available on site... skipping")

        return

    # Update divisions information in local database
    for division in reversed(divisions):

        logger.info("Updating division: %s", division.get("acf").get("naam_afdeling"))
        update_division_in_db(db_session, division)

        # Create division folder
        create_simple_folder(
            os.path.normpath(
                os.path.join(
                    gs_config.APP_CONFIG["working_folder"],
                    "divisions",
                    division.get("slug"),
                )
            )
        )

    logger.info("Updated divisions in database")
    print("Divisie database is aangepast")
    logger.info("Verified division folders")
    print("Divisie folders zijn aanwezig")


def process_downloads(web_session, db_session):
    """
    Get info from website to update files

    Parameters:
      web_session (session object): Request session object
      db_session (sql session): SQLAlchemy session
    """

    if gs_config.APP_CONFIG["run_action"] not in {"download", "both"}:
        logger.info("%s", separator_msg("Skipping download", "_"))
        print(
            f"\033[32m{separator_msg('Skipping Download', '<', 30)}\033[0m", flush=True
        )
        return

    logger.info("%s", separator_msg("Processing info for download", "_"))
    print(f"\033[32m{separator_msg('Download', '<', 30)}\033[0m", flush=True)

    # Check website status --- kdo 2025-02-20: nodig?
    site_url = gs_config.APP_CONFIG["wp_site"]
    total_post_count = get_post_count(web_session, site_url, "rouwberichten")

    match total_post_count:
        case total if total < 0:
            logger.info("Connection failure... skipping downloads")
            return
        case 0:
            logger.info("No posts on site")
            print("Geen documenten aanwezig op website")
            return
        case 1:
            logger.debug("One post on site")
            print("1 document aanwezig op website")
        case _:
            logger.debug("%s posts on site", total_post_count)
            print(f"{total_post_count} documenten aanwezig op website")

    # Get list of obituary posts ready for processing
    posts_to_process = get_posts_to_process(
        web_session, site_url, "rouwberichten", "verwerkingsstatus=Verwerkt"
    )
    match len(posts_to_process):
        case 0:
            logger.info("No posts ready to process for download")
            print(
                "Er zijn geen verwerkte documenten beschikbaar om op te halen",
                flush=True,
            )
            return
        case 1:
            print(
                "1 document klaar om op te halen",
                flush=True,
            )
        case _:
            print(
                f"{len(posts_to_process)} documenten klaar om op te halen",
                flush=True,
            )

    # Reorder posts by priority and post id
    posts_to_process = sorted(
        posts_to_process, key=lambda x: (x["acf"]["prioriteit"], x["id"])
    )

    #   Add timer
    t_download = Timer(name="ProcessingDownloadTime", logger=None)
    session_count = 0
    max_per_cycle = gs_config.APP_CONFIG["max_per_cycle"]

    # Walk thru each post to get information
    for post_to_process in posts_to_process:
        # Limit downloads during one session
        if session_count >= max_per_cycle:
            print("Limiet van download cyclus bereikt")
            logger.debug("Cycle limit reached")

            try:
                t_download.stop()
            except TimerError:
                # Timer wasn't started yet
                pass

            # Exit the for loop
            break

        t_download.start()

        logger.info(
            "%s", separator_msg("Process Post " + str(post_to_process["id"]), "~")
        )

        # Create obituary data set for the post information
        obituary_post = ObituaryPost(wp_post_data=post_to_process)

        # Create new file name based on returned information
        set_new_file_name(obituary_post, db_session)

        # Normalize city names
        normalize_city_names(obituary_post, db_session)

        # Clean up note text
        obituary_post.note = obituary_post.note.replace("oud", "Oud")
        obituary_post.note = obituary_post.note.replace("Oudst", "Oud-st")

        log_info_results(obituary_post)
        line_to_print = f"{obituary_post.wp_post_id} || {obituary_post.division_slug} ||"
        line_to_print += f" {obituary_post.file_name} || {obituary_post.new_file_name}"
        print(
            f"{line_to_print}",
            flush=True,
        )

        # File path where temp processed file was stored
        processed_file_path = os.path.normpath(
            os.path.join(
                obituary_post.folder_name,
                gs_config.APP_CONFIG["processed_folder"],
                obituary_post.file_name,
            )
        )

        logger.debug("%15s: %s", "Review", obituary_post.review)
        # If review marker is set, create the move to review folder path
        if obituary_post.review:
            move_to_file_path = os.path.normpath(
                os.path.join(
                    obituary_post.folder_name,
                    gs_config.APP_CONFIG["review_folder"],
                    obituary_post.new_file_name,
                )
            )
        else:
            # Create normal move destination folder path
            move_to_file_path = os.path.normpath(
                os.path.join(
                    obituary_post.folder_name,
                    gs_config.APP_CONFIG["renamed_folder"],
                    obituary_post.obituary_type,
                    obituary_post.new_file_name,
                )
            )

        logger.info("Moving file to folder")
        move_result, move_to_file_path = move_file(
            processed_file_path,
            move_to_file_path,
            gs_config.APP_CONFIG["file_overwrite"],
        )

        if move_result:
            logger.info("File successfully moved")

            # Convert image files to PDF file if required
            if gs_config.APP_CONFIG["save_to_pdf"]:
                obituary_post.new_file_name = save_image_as_pdf(
                    move_to_file_path,
                    keep_original=gs_config.APP_CONFIG["keep_original"],
                )
            else:
                _, obituary_post.new_file_name = os.path.split(
                    move_to_file_path
                )  # eg. xxxxxx.pdf

            # Add obituary to inventory excel document if XL export is required
            # Get divisions data from database
            division_data = get_division_by_slug(
                db_session, obituary_post.division_slug
            )

            # Continue if there is division data
            if division_data is not None:
                # Continue if data needs to be exported to an index file
                if division_data.export:
                    # First modify some data for export depending on division requirements
                    if division_data.last_names_capitalized:
                        obituary_post.last_name = (obituary_post.last_name).upper()

                    obituary_post.last_name = convert_diacritics(
                        obituary_post.last_name, division_data.last_names_no_diacritics
                    )

                    obituary_post.first_name = convert_diacritics(
                        obituary_post.first_name,
                        division_data.first_names_no_diacritics,
                    )

                    # Then add to index file
                    add_row_to_index(obituary_post)

                    if RUN_FVO_FUNCTIONS:
                        add_row_to_index_fvo(obituary_post)

            # Increase the processed last run counter for the division
            increment_processed_counter(obituary_post, db_session)

            # Delete post from site
            if delete_wp_post(web_session, obituary_post.wp_post_link):
                logger.info("Post deleted from site")
                obituary_post.wp_post_removed = True

                # Decrease the number of documents known to be on the site for the division
                decrement_site_counter(obituary_post, db_session)

                # Delete featured image on site
                # _, featured_image = os.path.split(obituary_post.wp_web_image_path)
                # image_deleted = delete_wp_image(web_session, site_url, featured_image)
                if delete_wp_post(web_session, obituary_post.wp_web_image_path):
                    obituary_post.wp_image_removed = True
                    logger.info("Image deleted from site")
                else:
                    obituary_post.wp_image_removed = False
                    logger.info("Image not deleted from site")
            else:
                obituary_post.wp_post_removed = False
                obituary_post.wp_image_removed = False
                logger.info("Post and image not deleted from site")
        else:
            if os.path.exists(move_to_file_path):
                logger.debug(
                    "File already moved on previous run, but post still on site"
                )
                # Retry delete post from site, might be still on site
                if delete_wp_post(web_session, obituary_post.wp_post_link):
                    logger.info("Post deleted from site")
                    obituary_post.wp_post_removed = True

                    # Decrease the number of documents known to be on the site for the division
                    decrement_site_counter(obituary_post, db_session)

                    # Delete featured image on site
                    # _, featured_image = os.path.split(obituary_post.wp_web_image_path)
                    # image_deleted = delete_wp_image(
                    # web_session, site_url, featured_image
                    # )
                    if delete_wp_post(web_session, obituary_post.wp_web_image_path):
                        obituary_post.wp_image_removed = True
                        logger.info("Image deleted from site")
                    else:
                        obituary_post.wp_image_removed = False
                        logger.info("Image not deleted from site")
                else:
                    obituary_post.wp_post_removed = False
                    obituary_post.wp_image_removed = False
                    logger.info("Post and image not deleted from site")
            else:
                logger.info("File move failed")

        # Update/Add obituary info to database
        update_db_documents(obituary_post, db_session)

        # Update/Add first name with gender to database
        update_db_gender_from_obituary(obituary_post, db_session)

        session_count += 1

        t_download.stop()

    log_timer_info_csv(t_download)
    Timer.timers.clear()


def process_uploads(web_session, db_session):
    """
    Get files to process and loop thru them

    Parameters:
      web_session (web_session object): Request web_session object
      db_session (sql session): SQLAlchemy session
    """

    if gs_config.APP_CONFIG["run_action"] not in {"upload", "both"}:
        logger.info("%s", separator_msg("Skipping upload", "_"))
        print(f"\033[33m{separator_msg('Skipping Upload', '<', 30)}\033[0m", flush=True)
        return

    logger.info("%s", separator_msg("Processing files for upload", "_"))
    print(f"\033[33m{separator_msg('Upload', '>', 30)}\033[0m", flush=True)

    # Website to use
    site_url = gs_config.APP_CONFIG["wp_site"]

    # Check website disk space and website db space usage
    site_parameters = get_custom_api_values(
        web_session,
        site_url,
        "system-status",
    )
    # On no data returned bail early, there might be site issue
    if len(site_parameters) == 0:
        return

    # Bail if disk usage reached limit
    if (
        site_parameters.get("disk_used_mb", 0)
        > gs_config.APP_CONFIG["wp_max_disk_used"]
    ):
        logger.info("Reached website disk usage limit. Bailing.")
        logger.debug(
            "%15s: %s", "disk usage (MB)", site_parameters.get("disk_used_mb", 0)
        )
        logger.debug(
            "%15s: %s", "max allowed(MB)", gs_config.APP_CONFIG["wp_max_disk_used"]
        )
        print(
            "\033[31mWebsite disk limiet bereikt\033[0m",
            flush=True,
        )
        return

    # Bail if database usage reached limit
    if site_parameters.get("db_used_mb", 0) > gs_config.APP_CONFIG["wp_max_db_used"]:
        logger.info("Reached website database usage limit. Bailing.")
        logger.debug("%15s: %s", "db usage (MB)", site_parameters.get("db_used_mb", 0))
        logger.debug(
            "%15s: %s", "max allowed(MB)", gs_config.APP_CONFIG["wp_max_db_used"]
        )
        print(
            "\033[31mWebsite database limiet bereikt\033[0m",
            flush=True,
        )
        return

    logger.debug("%15s: %sMB", "max disk", gs_config.APP_CONFIG["wp_max_disk_used"])
    logger.debug("%15s: %sMB", "max db", gs_config.APP_CONFIG["wp_max_db_used"])

    # Get count of all local files
    local_document_count = count_files_in_folders(
        os.path.normpath(
            os.path.join(
                gs_config.APP_CONFIG["working_folder"],
                gs_config.APP_CONFIG["divisions_folder"],
            )
        )
    )
    if not local_document_count:
        print("Geen lokale documenten beschikbaar")
        logger.debug("No local files to process")

        return

    # Get count of last processed documents for all division from database
    divisions_processed_count = get_divisions_processed_count(db_session)
    if not divisions_processed_count:
        logger.debug("No data returned from database")

        return

    # AI: check Ollama once per cycle. If it is down, skip the uploads of
    # this cycle and try again next cycle (documents stay where they are).
    if ai_enabled():
        ai_ok, ai_message = check_ai_service()
        if not ai_ok:
            print(f"\033[31m{ai_message}\033[0m", flush=True)
            print("Upload overgeslagen; volgende cyclus opnieuw", flush=True)
            return
        print(ai_message, flush=True)
    ai_service_down = False

    # # Using API, get count of documents per division already posted on website
    # divisions_document_count = get_custom_api_values(
    #     web_session,
    #     site_url,
    #     endpoint="counts-by-division",
    # )
    # if len(divisions_document_count) == 0:
    #     print("No data returned from website")
    #     logger.debug("No data returned from website")
    #
    #     return

    # Add timer
    t_upload = Timer(name="ProcessingUploadTime")

    # Process each division separately
    for division, processed_count, division_web_count in divisions_processed_count:
        # Stop the cycle if Ollama went down during processing
        if ai_service_down:
            break

        # Initial values
        readable_division = string.capwords(division[1:], sep="-")
        division_local_count = local_document_count.get(division, 0)
        # division_web_count = divisions_document_count.get(division, 0)
        division_max_count = gs_config.APP_CONFIG["wp_max_uploads"]
        session_count = 0
        max_per_cycle = gs_config.APP_CONFIG["max_per_cycle"]

        logger.info("%s", f"Processing files for {readable_division}")

        match division_local_count:
            case 0:
                logger.debug("No local files to process")
                continue
            case 1:
                logger.debug("One local file to process")
                print(f"{separator_msg(readable_division, '.')}", flush=True)
                print("1 lokaal document beschikbaar")
            case _:
                logger.debug("%s local files to process", division_local_count)
                print(f"{separator_msg(readable_division, '.')}", flush=True)
                print(f"{division_local_count} lokale documenten beschikbaar")

        if division_web_count >= division_max_count:
            logger.info("Division quota reached; can't add more for now. Bailing.")
            print(
                "Quota divisie bereikt; kan voorlopig niks meer toevoegen", flush=True
            )
            continue

        match division_web_count:
            case 0:
                logger.debug("No documents on website")
                print("Geen website documenten beschikbaar", flush=True)
            case 1:
                logger.debug("One document on website")
                print("1 website document beschikbaar")
            case _:
                logger.debug("%s documents on website", division_web_count)
                print(
                    f"{division_web_count} documenten op website",
                    flush=True,
                )

        print(
            f"{gs_config.APP_CONFIG['wp_max_uploads']} maximum toegestaan op website",
            flush=True,
        )

        print(
            f"{processed_count} document(en) verwerkt tijdens vorige download",
            flush=True,
        )

        # Initial values
        file_paths_to_process = ""
        root_file_path = os.path.join(
            gs_config.APP_CONFIG["working_folder"],
            gs_config.APP_CONFIG["divisions_folder"],
            division,
        )

        # Get all file paths of the division for processing
        file_paths_to_process = get_file_paths(
            root_file_path, file_patterns=["*.pdf", "*.jpg", "*.jpeg"]
        )

        # Next division if no files found
        if len(file_paths_to_process) == 0:
            continue

        # Process all found file paths
        for file_to_process in file_paths_to_process:
            logger.info("%s", separator_msg("Process Document", "~"))
            logger.debug("Processing %s", file_to_process)

            # Limit uploads during one session for current division
            if session_count >= max_per_cycle:
                print("Limiet van upload cyclus bereikt")
                logger.debug("Cycle limit reached")
                break

            # Check if pdf or jpg
            file_extension = file_to_process.split(".")[-1].lower()
            logger.debug("%15s: %s", "Extension", file_extension)

            # Check if document is a valid PDF
            if file_extension == "pdf" and not is_valid_pdf(file_to_process):
                move_corrupt_file(file_to_process)
                continue

            # Get the site disk space and database sizes
            site_parameters = get_custom_api_values(
                web_session,
                site_url,
                "system-status",
            )
            # Bail if no data returned, could be communications fault
            if len(site_parameters) == 0:
                continue

            # Bail if disk usage reached limit
            if (
                site_parameters.get(
                    "disk_used_mb", gs_config.APP_CONFIG["wp_max_disk_used"]
                )
                >= gs_config.APP_CONFIG["wp_max_disk_used"]
            ):
                logger.info("Reached website disk usage limit. Bailing.")
                logger.debug(
                    "%15s: %s",
                    "disk usage (MB)",
                    site_parameters.get(
                        "disk_used_mb", gs_config.APP_CONFIG["wp_max_disk_used"]
                    ),
                )
                logger.debug(
                    "%15s: %s",
                    "max allowed(MB)",
                    gs_config.APP_CONFIG["wp_max_disk_used"],
                )
                print(
                    "\033[31mWebsite disk limiet bereikt\033[0m",
                    flush=True,
                )
                break

            # Bail if database usage reached limit
            if (
                site_parameters.get(
                    "db_used_mb", gs_config.APP_CONFIG["wp_max_db_used"]
                )
                >= gs_config.APP_CONFIG["wp_max_db_used"]
            ):
                logger.info("Reached website database usage limit. Bailing.")
                logger.debug(
                    "%15s: %s",
                    "db usage (MB)",
                    site_parameters.get(
                        "db_used_mb", gs_config.APP_CONFIG["wp_max_db_used"]
                    ),
                )
                logger.debug(
                    "%15s: %s",
                    "max allowed(MB)",
                    gs_config.APP_CONFIG["wp_max_db_used"],
                )
                print(
                    "\033[31mWebsite database limiet bereikt\033[0m",
                    flush=True,
                )
                break

            # Check website status for current division post count
            if division_web_count >= division_max_count:
                logger.info("Division quota reached; can't add more for now. Bailing.")
                print(
                    "Quota divisie bereikt; kan voorlopig niks meer toevoegen",
                    flush=True,
                )

                try:
                    t_upload.stop()
                except TimerError:
                    # Timer wasn't started yet
                    pass

                # Exit the for loop
                break

            t_upload.start()

            # logger.info("%s", separator_msg("Process Document", "~"))

            # Create obituary dataset for the file to keep track of information
            obituary = Obituary(file_path=file_to_process)
            # logger.debug("Processing %s", obituary.file_path)

            # Create temporary file name
            # obituary.obituary_id = f"{obituary.file_base_name}_{obituary.obituary_id}"
            print_message = f"-- {obituary.file_name} "
            print_message += f"{'-' * (44 - len(obituary.file_name))}"
            print(
                f"\033[36m{print_message}\033[0m",
                flush=True,
            )

            embedded_text = None
            match file_extension:
                case "pdf":
                    # Extract images from the pdf
                    # 2026-01-18 KDO: useless routine, does not seem to get any
                    # pil_images = extract_images_with_pypdf2(obituary.file_path)

                    # Try again if no images found
                    # if len(pil_images) == 0:
                    pil_images = create_images_with_pdf2im(obituary.file_path)

                    # If still no images found then document can't be properly processed
                    if len(pil_images) == 0:
                        move_corrupt_file(obituary.file_path)
                        logger.debug("PDF document can't be properly processed")
                        obituary.processing_time = t_upload.stop()
                        continue

                    # Extract text from searchable pdf
                    embedded_text = extract_text_with_pypdf2(obituary.file_path)

                case "jpg" | "jpeg":
                    # Get the jpg, jpeg image
                    pil_images = open_image(obituary.file_path)
                    # If no image found then document can't be properly processed
                    if len(pil_images) == 0:
                        move_corrupt_file(obituary.file_path)
                        logger.debug("JPG document can't be properly processed")
                        obituary.processing_time = t_upload.stop()
                        continue

                case _:
                    # Bail if not an allowed file extension
                    logger.debug("%15s: %s", "Wrong extension", file_extension)
                    continue

            # Create web and ocr image
            web_image, ocr_image = create_working_images(
                pil_images, obituary.obituary_type
            )

            # Bail if image is not big enough
            if not is_large_image_pil(
                web_image, min_size=gs_config.APP_CONFIG["minimum_size"]
            ):
                move_corrupt_file(obituary.file_path)
                logger.debug("Web image not big enough")
                obituary.processing_time = t_upload.stop()
                continue

            # Save image to be used on website
            watermark = get_division_by_slug(db_session, obituary.division_slug)
            obituary.wp_web_image_path = save_web_image(
                image_path=gs_config.APP_CONFIG["uploads_folder"],
                file_name=f"{obituary.obituary_id}.webp",
                web_image=web_image,
                text=watermark.name,
            )

            # Update Obituary object with information that could be embedded in the filename
            find_info_in_filepath(obituary, db_session)

            if ai_enabled():
                # AI replaces Tesseract + get_name + find_life_info.
                # Only fields still empty after the file name are filled.
                try:
                    extract_with_ai(obituary, pil_images, embedded_text)
                    clear_failure(file_to_process)
                except AIServiceError as error:
                    logger.error("AI service unavailable: %s", error)
                    print(f"\033[31m{error}\033[0m", flush=True)
                    print("Upload gestopt; volgende cyclus opnieuw", flush=True)
                    delete_file(obituary.wp_web_image_path)
                    obituary.processing_time = t_upload.stop()
                    ai_service_down = True
                    break
                except Exception as error:  # pylint: disable=broad-except
                    logger.exception("AI analysis failed for %s", file_to_process)
                    print(f"\033[31mAI-analyse mislukt: {error}\033[0m", flush=True)
                    delete_file(obituary.wp_web_image_path)
                    obituary.processing_time = t_upload.stop()
                    if register_failure(file_to_process):
                        print("Document verplaatst naar _failed", flush=True)
                    continue

            # Do OCR on document if PDF has no embedded text or names were not found in filename
            elif embedded_text is None or not obituary.first_name or not obituary.last_name:
                if embedded_text is None:
                    logger.debug("No embedded text in PDF found, trying OCR.")
                if not obituary.first_name or not obituary.last_name:
                    logger.debug("No name found in filename, trying OCR")

                # Extract text from big image
                ocr_dict = extract_ocr_data(ocr_image)

                # Clean up OCR data
                clean_ocr_dict = dict(clean_ocr_text(ocr_dict) if ocr_dict else None)

                # Flatten OCR text data into string
                obituary.ocr_text = join_data(clean_ocr_dict["text"])
                obituary.content = readable_ocr_text(clean_ocr_dict)

                # Find line with tallest text, usually that is the name of the deceased
                if not obituary.first_name or not obituary.last_name:
                    logger.debug("Getting names from OCR")
                    returned_first_name, returned_last_name = get_name(clean_ocr_dict)

                if not obituary.first_name:
                    obituary.first_name = returned_first_name
                    logger.debug("Using first name from OCR")
                else:
                    logger.debug("Using first name from filename")

                if not obituary.last_name:
                    logger.debug("Using last name from OCR")
                    obituary.last_name = returned_last_name
                else:
                    logger.debug("Using last name from filename")

                logger.debug("%15s: %s","last_name",obituary.last_name)
                logger.debug("%15s: %s","first_name",obituary.first_name)

            if not ai_enabled():
                # Continue using embedded text if it is available
                if embedded_text:
                    logger.debug("Using embedded text to continue")
                    obituary.content = clean_up_text(embedded_text)
                    obituary.ocr_text = join_data(obituary.content)

                # Update Obituary object with birth and death information from OCR
                find_life_info(obituary, db_session)

            # Check if picture with face is included
            has_face(obituary, ocr_image)

            # Extract extra notes
            get_note_info(obituary)

            # Extract gender based on first name
            set_obituary_gender_by_name(obituary, db_session)

            # Set division ID
            set_division_id(obituary, db_session)

            # Set obituary priority
            set_obituary_priority_by_slug(obituary, db_session)

            # Upload to website
            upload_status = process_upload(obituary, web_session)

            # Processing time
            obituary.processing_time = t_upload.stop()

            # Check status
            match upload_status:
                case -1:
                    logger.info("Upload failed. Cleaning up.")
                    # Delete local image file, but keep original document
                    delete_file(obituary.wp_web_image_path)
                case 0:
                    logger.info("Site saturated. Bailing.")
                    logger.info("End")
                    break
                case 1:
                    # Move processed document
                    logger.info("Data posted to site.")
                    processed_file_path = os.path.normpath(
                        os.path.join(
                            obituary.folder_name,
                            gs_config.APP_CONFIG["processed_folder"],
                            f"{obituary.obituary_id}.{file_extension}",
                        )
                    )
                    # copy_file(file_to_process, processed_file_path)
                    logger.info("Moving original file.")
                    move_file(file_to_process, processed_file_path, overwrite=True)
                    delete_file(obituary.wp_web_image_path)

                    # Save information
                    division_web_count += 1
                    session_count += 1
                    increment_site_counter(obituary, db_session)
                    update_db_documents(obituary, db_session)
                    print_info_results(obituary)
                    log_info_results(obituary)

    log_timer_info_csv(t_upload)
    Timer.timers.clear()


def process_test(web_session, db_session):
    """
    Testing stuff temporarily

    Parameters:
      web_session (web_session object): Request web_session object
      db_session (sql session): SQLAlchemy session

    """
    # Nothing to test, modify as needed
    if not web_session:
        return
    if not db_session:
        return
