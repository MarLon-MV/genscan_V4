"""Tests for the AI result -> Obituary mapping (gs_ai_tools.apply_ai_result)."""

import pytest

import gs_ai_tools
from gs_classes import Obituary


@pytest.fixture
def obituary():
    return Obituary()


def test_fills_empty_fields(obituary):
    result = {
        "voornaam": "Joseph", "achternaam": "ARDENOIS",
        "geboortedatum": "1923-02-06", "overlijdensdatum": "2002-11-20",
        "geboorteplaats": "Brugge", "overlijdensplaats": "Gent",
    }
    gs_ai_tools.apply_ai_result(obituary, result)
    assert (obituary.first_name, obituary.last_name) == ("Joseph", "ARDENOIS")
    assert (obituary.birth_year, obituary.birth_month, obituary.birth_day) == (1923, 2, 6)
    assert obituary.death_year == 2002


def test_filename_data_has_priority(obituary):
    obituary.first_name = "Jan"
    gs_ai_tools.apply_ai_result(obituary, {"voornaam": "Piet", "achternaam": "X"})
    assert obituary.first_name == "Jan"
    assert obituary.last_name == "X"


def test_impossible_year_is_dropped(obituary):
    gs_ai_tools.apply_ai_result(obituary, {"overlijdensdatum": "2099-01-01"})
    assert obituary.death_year is None
    assert obituary.death_month is None


def test_unknown_dates_are_none_not_empty_string(obituary):
    gs_ai_tools.apply_ai_result(obituary, {"geboortedatum": "onbekend"})
    assert obituary.birth_year is None


def test_guessed_fields_are_not_uploaded_by_default(obituary):
    result = {"voornaam": "Jan", "gegokt_velden": ["voornaam"]}
    gs_ai_tools.apply_ai_result(obituary, result)
    assert obituary.first_name == ""
    gs_ai_tools.apply_ai_result(obituary, result, upload_guesses=True)
    assert obituary.first_name == "Jan"


class _Post:
    file_name = "RB_ANZEGEM-R0005.pdf"
    last_name = "ARDENOIS"
    first_name = "Joseph (Jos)"
    birth_year, birth_month, birth_day = 1923, 2, 6
    death_year, death_month, death_day = 2002, None, None


def test_default_file_name_format():
    from gs_helpers import create_default_file_name

    post = create_default_file_name(_Post())
    assert post.new_file_name == "ARDENOIS_Joseph_1923-02-06_2002.pdf"


def test_default_file_name_unknown_parts():
    from gs_helpers import create_default_file_name

    post = _Post()
    post.first_name, post.birth_year = "", None
    assert create_default_file_name(post).new_file_name == (
        "ARDENOIS_onbekend_onbekend_2002.pdf"
    )
