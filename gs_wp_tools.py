"""
Some Wordpress helper functions for genscan
"""

import base64
import json
import logging
import os
import time

import emoji
from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import HTTPError, RequestException, Timeout

import gs_config
from gs_db_tools import log_field_values

logger = logging.getLogger("gsw_logger")


def create_wp_header():
    """
    Create WP post header.

    Parameters: none

    Return:
      header (string): Header for the POST command
    """

    logger.debug("Creating WP header")

    header = None
    user = os.getenv("WP_USER", None)
    password = os.getenv("WP_API", None)
    log_message = "No environment variables set"

    if user and password:
        credentials = user + ":" + password
        token = base64.b64encode(credentials.encode())
        logger.debug("WP token created")
#        header = {"Authorization": "Basic " + token.decode("utf-8")}
        header = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            'Authorization': 'Basic ' + token.decode('utf-8'),
        }
        log_message = f"WP header created for {user}"

    logger.debug(log_message)

    return header


def create_web_session():
    """
    Create a Requests session with a persistent header, a timeout of 30 seconds,
    and a default URL if provided.

    Returns:
    - session: A Requests session object with a persistent header, timeout.

    """

    session = None
    header = create_wp_header()

    if header is None:
        logger.debug("Can't create session for site, header missing")
    else:
        session = Session()
        session.headers.update(header)
        session.timeout = 10  # Set timeout to 10 seconds

        logger.debug("Web session created")

    return session


def upload_wp_image(session=None, site_url=None, obituary=None):
    """
    Upload an image to Wordpress.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      obituary (Obituary object): Obituary data

    Return:
      (string): Image ID received with successful upload, None if failed

    """

    image_path = obituary.wp_web_image_path
    if None in (session, site_url, image_path, obituary):
        logger.debug("Can't start uploading image to site: Missing parameters")

        return None

    tail = os.path.basename(image_path)
    logger.debug("%15s: %s", "Uploading image", tail)
    logger.debug("%15s: %s", "to site", site_url)

    image_endpoint = f"{site_url}/wp-json/wp/v2/media"

    # Upload image to post
    with open(image_path, "rb") as file:
        media = {
            "file": file,
        }

        try:
            response = session.post(image_endpoint, files=media)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            # Get post-id out of the response
            post_id = str(json.loads(response.content.decode("utf-8"))["id"])

        except RequestException as req_err:
            if isinstance(req_err, HTTPError):
                logger.debug("Failed to upload image %s", tail)
                logger.debug("%15s: %s", "Status code", req_err.response.status_code)
                logger.debug(req_err.response.text)
            elif isinstance(req_err, ConnectionError):
                logger.debug("Failed to establish a connection to the site.")
            elif isinstance(req_err, Timeout):
                logger.debug("Connection to the site timed out.")
            else:
                logger.debug("Request exception occurred: %s", req_err)
            print(
                "\033[1;36m Some communication error occurred, check logs! \033[0m",
                flush=True,
            )

            return None

    logger.debug("%15s: %s", "Image uploaded", tail)
    logger.debug("%15s: %s", "  to site", site_url)

    return post_id


def delete_wp_image(session=None, site_url=None, image_id=None, max_retries=3):
    """
    Delete an image from Wordpress.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      image_id (string): Wordpress ID of image to delete
      max_retries (int): Maximum number of retries on errors

    Return:
      (boolean): True (Success), False (Failure)

    """
    # No longer needed - kdo 2025-02-27

    if None in (session, site_url, image_id):
        logger.debug("Deleting image from site failed: Missing required parameters")

        return False

    image_endpoint = f"{site_url}/wp-json/wp/v2/media/{image_id}"
    logger.debug("Deleting image from site: %s", image_endpoint)

    params = {"force": "true"}
    attempt = 0

    while attempt < max_retries:
        # Try to delete image
        try:
            response = session.delete(image_endpoint, params=params)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            logger.debug("Image deleted successfully!")

            return True

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            logger.error("Unexpected HTTP error: %s", http_err.response.text)

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        print(
            "\033[1;36m Some communication error occurred, check logs! \033[0m",
            flush=True,
        )

    return False


def delete_wp_post(session=None, endpoint_url=None, max_retries=3):
    """
    Delete a post (or image) from Wordpress site.

    Parameters:
      session (session object): Request session object
      endpoint_url (string): URL of post endpoint to delete
      max_retries (int): Maximum number of retries on errors

    Return:
      (boolean): True (Success), False (Failure)

    """

    if None in (session, endpoint_url):
        logger.debug("Deleting post from site failed: Missing required parameters")

        return False

    #    logger.info("Deleting post from site: %s", endpoint_url)
    #
    #    params = {"force": "true"}
    #    attempt = 0
    #
    #    while attempt < max_retries:
    #        # Try to delete post
    #        try:
    #            response = session.delete(endpoint_url, params=params)
    #            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
    #            logger.debug("%15s: %s", "Response", response)
    #            logger.debug("%15s: %s", "Elapsed time", response.elapsed)
    #
    #            logger.debug("Post deleted successfully: %s", endpoint_url)
    #
    #            return True
    attempt = 0
    endpoint_type = "post"
    params = {"force": "true"}
    if "media" in endpoint_url:
        params = {"force": "true"}
        endpoint_type = "image"

    logger.info("Deleting %s from site: %s", endpoint_type, endpoint_url)

    while attempt < max_retries:
        # Try to delete post
        try:
            response = session.delete(endpoint_url, params=params)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            logger.debug(
                "%s deleted successfully: %s", endpoint_type.title(), endpoint_url
            )

            return True

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title:
                    logger.warning(
                        "HTTP error encountered: %s - Retrying...", soup.title.string
                    )
                else:
                    logger.error("HTTP error encountered: Aborting retries.")

            except Exception as parse_err:
                logger.error(
                    "HTTP error encountered: Failed to parse error response: %s",
                    parse_err,
                )

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        # Exponential backoff before retrying after failures
        attempt += 1
        sleep_time = 5**attempt  # Exponential backoff (5, 25, 125, ...)
        logger.debug(
            "Retrying in %d seconds (attempt %d/%d)...",
            sleep_time,
            attempt,
            max_retries,
        )
        time.sleep(sleep_time)

    print(
        "\033[1;36m Some communication error occurred, check logs! \033[0m",
        flush=True,
    )

    logger.error("Failed to delete post after %d attempts.", attempt)

    return False


def upload_wp_data(
    session=None, site_url=None, post_endpoint=None, post_data=None, max_retries=3
):
    """
    Upload data to WP post.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      post_endpoint (string): Name of post to upload
      post_data (string): Data to attach to post
      max_retries (int): Maximum number of retries on errors

    Return:
      (string): Post ID received with successful upload, None if failed

    """

    if None in (session, site_url, post_endpoint, post_data):
        logger.debug("Can't start post creation: Missing required parameters")

        return None

    logger.info("Creating post")

    post_endpoint = f"{site_url}/wp-json/wp/v2/{post_endpoint}"
    attempt = 0

    while attempt < max_retries:
        # Send a POST request to create the new post.
        try:
            response = session.post(post_endpoint, json=post_data)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            # Get post-id out of the response
            post_id = str(json.loads(response.content.decode("utf-8"))["id"])

            logger.debug("Post (wp_id:%s) created successfully", post_id)

            return post_id

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title:
                    logger.warning(
                        "HTTP error encountered: %s - Retrying...", soup.title.string
                    )
                else:
                    logger.error("HTTP error encountered: Aborting retries.")

            except Exception as parse_err:
                logger.error(
                    "HTTP error encountered: Failed to parse error response: %s",
                    parse_err,
                )

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        # Exponential backoff before retrying after failures
        attempt += 1
        sleep_time = 5**attempt  # Exponential backoff (5, 25, 125, ...)
        logger.debug(
            "Retrying in %d seconds (attempt %d/%d)...",
            sleep_time,
            attempt,
            max_retries,
        )
        time.sleep(sleep_time)

    print(
        "\033[1;36m Some communication error occurred, check logs! \033[0m",
        flush=True,
    )

    logger.error("Failed to create post after %d attempts.", attempt)

    return None


def upload_wp_post(session=None, site_url=None, obituary=None, max_retries=3):
    """
    Upload obituary data to WP post 'rouwbrieven'.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      obituary (Obituary object): Data to attach to post
      max_retries (int): Maximum number of retries on errors

    Return:
      (string): Post ID received with successful upload, None if failed

    """

    if None in (session, site_url, obituary):
        logger.debug("Can't start post creation: Missing required parameters")

        return None

    logger.info("Creating rouwbericht post")
    log_field_values(obituary)
    post_endpoint = f"{site_url}/wp-json/wp/v2/rouwberichten"

    # Prepare the obituary post
    post_data = {
        "title": obituary.obituary_id,
        "content": emoji.replace_emoji(obituary.content, replace=""),
        "featured_media": obituary.wp_featured_media,
        "acf": {
            "type_overlijdensbericht": obituary.obituary_type.upper(),
            "voornaam": obituary.first_name,
            "familienaam": obituary.last_name,
            "gender": obituary.gender,
            "geboorteplaats": obituary.birth_place,
            "geboortedatum": {
                "geboortejaar": (obituary.birth_year),
                "geboortemaand": (obituary.birth_month),
                "geboortedag": obituary.birth_day,
            },
            "overlijdensplaats": obituary.death_place,
            "overlijdensdatum": {
                "overlijdensjaar": (obituary.death_year),
                "overlijdensmaand": (obituary.death_month),
                "overlijdensdag": (obituary.death_day),
            },
            "foto": obituary.face,
            "nota": emoji.replace_emoji(obituary.note, replace=""),
            "doos": obituary.box_number,
            "document_nummer": obituary.document_number,
            "afdeling": obituary.division_id,
            "afdeling_fv_alternatief": obituary.division_slug,
            "verwerkingsstatus": "Nieuw",
            "originele_bestandsnaam": obituary.new_file_name,
            "originele_folder": obituary.folder_name.replace("\\", "/"),
            "prioriteit": obituary.wp_priority,
        },
        "status": "publish",
    }
    logger.debug("%15s: %s", "post_data", post_data)
    attempt = 0

    while attempt < max_retries:
        # Send a POST request to create the new post.
        try:
            response = session.post(post_endpoint, json=post_data)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            # Get post-id out of the response
            post_id = str(json.loads(response.content.decode("utf-8"))["id"])

            logger.debug("%15s: wp_id(%s)", "Post created", post_id)

            return post_id

        except HTTPError as http_err:
            logger.error("%15s: %s", "HTTP error", http_err)

            # Try to parse response text as JSON
            try:
                error_data = json.loads(response.text)
                logger.error("%15s: %s", "Error code", error_data.get("code"))
                logger.error("%15s: %s", "Error message", error_data.get("message"))
                if "data" in error_data:
                    logger.error("%15s: %s", "Error details", error_data["data"])

                # Extract and log 'data -> params -> acf', raises error if missing keys
                acf_message = error_data["data"]["params"]["acf"]
                logger.error("%15s: %s", "ACF Message", acf_message)

            except KeyError as key_err:
                logger.error("Key not found in JSON response: %s", key_err)
            except json.JSONDecodeError:
                logger.warning("Response is not JSON. Attempting to parse as HTML...")

                # Fallback to parsing as HTML
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                    logger.error("%15s: %s", "Soup content", soup)
                    if soup.title:
                        logger.warning(
                            "HTTP error encountered: %s - Retrying...",
                            soup.title.string,
                        )
                    else:
                        logger.error("HTTP error encountered: Aborting retries.")

                except Exception as parse_err:
                    logger.error(
                        "HTTP error encountered: Failed to parse error response: %s",
                        parse_err,
                    )

            except Exception as e:
                logger.error("Unexpected error while processing response: %s", e)

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        # Exponential backoff before retrying after failures
        attempt += 1
        sleep_time = 5**attempt  # Exponential backoff (5, 25, 125, ...)
        logger.debug(
            "Retrying in %d seconds (attempt %d/%d)...",
            sleep_time,
            attempt,
            max_retries,
        )
        time.sleep(sleep_time)

    print(
        "\033[1;36m Some communication error occurred, check logs! \033[0m",
        flush=True,
    )
    logger.error("Failed to create post after %d attempts.", attempt)

    return None


def get_post_count(
    session=None,
    site_url=None,
    post_endpoint=None,
    post_filter="",
    count_type="X-WP-Total",
    max_retries=3,
):
    """
    Count number of posts on WP site for specific post type

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      post_endpoint (string): Name of post to query
      post_filter (string): empty or Wordpress JSON formatted filter,
                            e.g. &verwerkingsstatus=Verwerkt
      count_type (string): type of count to retrieve, default is posts (i.e X-WP-Total)
                           For pages use X-WP-TotalPages
      max_retries (int): Maximum number of retries on errors

    Return:
      post_count (int): number of posts found or -1 for error

    """

    post_count = -1

    if None in (session, site_url, post_endpoint):
        logger.debug("Getting post count from site failed: Missing required parameters")

        return post_count

    if count_type not in ("X-WP-Total", "X-WP-TotalPages"):
        count_type = "X-WP-Total"

    if len(post_filter) > 0 and not post_filter.startswith("&"):
        post_filter = f"&{post_filter}"

    logger.debug("Getting %s count from site %s", count_type, site_url)

    post_endpoint = f"{site_url}/wp-json/wp/v2/{post_endpoint}"
    post_endpoint += f"?status=publish&page=1&_fields=id{post_filter}"
    logger.debug("%15s: %s", "Endpoint", post_endpoint)

    attempt = 0

    while attempt < max_retries:
        # Send a GET request to get info.
        try:
            response = session.get(post_endpoint)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            if len(response.headers[count_type]) > 0:
                post_count = int(response.headers[count_type])

            logger.debug("%15s: %s", count_type, post_count)

            return post_count

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title:
                    logger.warning(
                        "HTTP error encountered: %s - Retrying...", soup.title.string
                    )
                else:
                    logger.error("HTTP error encountered: Aborting retries.")

            except Exception as parse_err:
                logger.error(
                    "HTTP error encountered: Failed to parse error response: %s",
                    parse_err,
                )

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        # Exponential backoff before retrying after failures
        attempt += 1
        sleep_time = 5**attempt  # Exponential backoff (5, 25, 125, ...)
        logger.debug(
            "Retrying in %d seconds (attempt %d/%d)...",
            sleep_time,
            attempt,
            max_retries,
        )
        time.sleep(sleep_time)

    print(
        "\033[1;36m Some communication error occurred, check logs! \033[0m",
        flush=True,
    )

    logger.error("Failed to get count of posts after %d attempts.", attempt)

    return -1


def get_posts_to_process(session=None, site_url=None, endpoint=None, post_filter=""):
    """
    Get posts on WP site for specific post type

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      endpoint (string): Name of post to query
      post_filter (string): empty or Wordpress JSON formatted filter,
                            e.g. &verwerkingsstatus=Verwerkt

    Return:
      all_page_items_json (list): all data from available posts
    """

    logger.info("Checking site status")

    if None in (session, site_url, endpoint):
        logger.debug("Getting posts data from site failed: Missing required parameters")

        return ""

    total_pages = get_post_count(
        session, site_url, endpoint, post_filter, "X-WP-TotalPages"
    )

    # Add ampersand when post_filter is available but does not start with it
    if len(post_filter) > 0 and not post_filter.startswith("&"):
        post_filter = f"&{post_filter}"

    logger.debug("Getting posts from site %s", site_url)

    post_url = f"{site_url}/wp-json/wp/v2/{endpoint}?status=publish{post_filter}"

    current_page = 1
    all_page_items_json = []

    while current_page <= total_pages:
        api_url = f"{post_url}&page={current_page}"
        logger.debug("%15s: %s", "Endpoint", api_url)

        try:
            response = session.get(api_url)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            page_items_json = response.json()
            all_page_items_json.extend(page_items_json)
            current_page += 1

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            logger.error("Unexpected HTTP error: %s", http_err.response.text)

            break

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

            break

        except Timeout:
            logger.error("Connection to the site timed out.")

            break

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)
            print(
                "\033[1;36m Some communication error occurred, check logs! \033[0m",
                flush=True,
            )

            break

    logger.info("%15s: %s of %s pages", "Retrieved", current_page - 1, total_pages)
    logger.info("%15s: %s posts", "Found", len(all_page_items_json))

    return all_page_items_json


def get_available_post_count(session=None, site_url=None, post_endpoint=None):
    """
    Check if site has enough post slots available.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of Wordpress site
      post_endpoint (string): Name of post to query

    Return:
      available_post_count (int): Count of posts that can be added

    """

    logger.info("Checking site status")
    available_post_count = -1

    if None not in (session, site_url, post_endpoint):
        max_post_count_allowed = int(gs_config.APP_CONFIG["wp_max_uploads"])
        current_post_count = get_post_count(session, site_url, post_endpoint)

        if current_post_count < 0:  # An error occurred
            logger.debug("Can't get current post count.")
        else:
            available_post_count = max_post_count_allowed - current_post_count
            logger.debug("Post count available: %s", available_post_count)

    return available_post_count


def process_upload(obituary, wp_session):
    """
    Massage data before uploading to Wordpress.

    Parameters:
      obituary (Obituary object): Obituary data
      wp_session (session object): Request session object

    Return:
      status (int): Max reached (0), Uploaded (1), No count (-1), Failed upload (-2)

    """

    # Initial values
    site_url = gs_config.APP_CONFIG["wp_site"]
    status = -1

    available_post_count = 2  # temp workaround
    match available_post_count:
        case -1:
            logger.debug("Can't get current post count.")
        case 0:
            logger.debug("Max posts reached.")
            status = 0
        case _:
            # Perform upload
            logger.debug(
                "Uploading data for %s to site %s", obituary.file_name, site_url
            )

            # First upload the image associated with post
            image_id = upload_wp_image(wp_session, site_url, obituary)

            # Image was successfully uploaded
            if image_id:
                obituary.wp_featured_media = image_id
                obituary.wp_image_posted = True
                logger.debug("%15s: wp_id(%s)", "Image uploaded", image_id)
                logger.debug("Now creating post")

                # Try to upload data
                post_id = upload_wp_post(wp_session, site_url, obituary)
                # post_id = upload_wp_data(
                #     wp_session, site_url, "rouwberichten", post_data
                # )

                if post_id is not None:
                    obituary.wp_post_id = post_id
                    obituary.wp_post_status = "Nieuw"
                    obituary.wp_post_posted = True
                    logger.info("%15s: wp_id(%s)", "Post created", post_id)
                    status = 1
                else:
                    logger.error("Post creation failed")
                    logger.debug("%15s: wp_id(%s)", "Removing image", image_id)
                    # image_delete_result = delete_wp_image(
                    #     wp_session, site_url, image_id
                    # )
                    image_endpoint = f"{site_url}/wp-json/wp/v2/media/{image_id}"
                    obituary.wp_post_posted = False
                    obituary.wp_image_posted = False
                    if delete_wp_post(wp_session, image_endpoint):
                        logger.debug("%15s: wp_id(%s)", "Image removed", image_id)
                    else:
                        logger.debug("%15s: wp_id(%s)", "Removal failed", image_id)
                    status = -1
            else:
                logger.debug("Post creation failed. Image not uploaded.")
                status = -1

    return status


def get_custom_api_values(
    session=None, site_url=None, endpoint=None, custom_filter="", max_retries=3
):
    """
    Get the value(s) for a custom API endpoint on web site.

    Parameters:
      session (session object): Request session object
      site_url (string): URL of site
      endpoint (string): name of custom endpoint
      custom_filter (string): empty or Wordpress JSON formatted filter
      max_retries (int): Maximum number of retries on errors

    Return:
      result_dict (dictionary): Value(s) returned by API call converted to dictionary

    """

    result_dict = {}

    if len(custom_filter) > 0 and not custom_filter.startswith("?"):
        custom_filter = f"?{custom_filter}"

    endpoint_url = f"{site_url}/wp-json/custom/v1/{endpoint}/{custom_filter}"

    logger.debug("Getting custom API endpoint value(s)")
    logger.debug("%15s: %s", "Endpoint", endpoint_url)

    if None in (session, site_url, endpoint):
        logger.debug("Can't get custom API value(s): Missing required parameters")

        return result_dict

    attempt = 0
    while attempt < max_retries:
        try:
            # Send a GET request to get info.
            response = session.get(endpoint_url)
            response.raise_for_status()  # Raises HTTPError for 4xx or 5xx responses
            logger.debug("%15s: %s", "Response", response)
            logger.debug("%15s: %s", "Elapsed time", response.elapsed)

            # Convert the JSON response to a dictionary
            result_dict = response.json()
            # Access data from the dictionary
            # Crashes if not a dict but a list - need to fix
            # for key, value in result_dict.items():
            #     logger.debug("%15s: %s", key, value)

            return result_dict

        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title:
                    logger.warning(
                        "HTTP error encountered: %s - Retrying...", soup.title.string
                    )
                else:
                    logger.error("HTTP error encountered: Aborting retries.")

            except Exception as parse_err:
                logger.error(
                    "HTTP error encountered: Failed to parse error response: %s",
                    parse_err,
                )

        except ConnectionError:
            logger.error("Failed to establish a connection to the site.")

        except Timeout:
            logger.error("Connection to the site timed out.")

        except RequestException as req_err:
            logger.error("Unexpected request exception: %s", req_err)

        # Exponential backoff before retrying after failures
        attempt += 1
        sleep_time = 5**attempt  # Exponential backoff (5, 25, 125, ...)
        logger.debug(
            "Retrying in %d seconds (attempt %d/%d)...",
            sleep_time,
            attempt,
            max_retries,
        )
        time.sleep(sleep_time)

    print(
        "\033[1;36m Some communication error occurred, check logs! \033[0m",
        flush=True,
    )

    logger.error("Failed to get custom API after %d attempts.", attempt)

    return result_dict
