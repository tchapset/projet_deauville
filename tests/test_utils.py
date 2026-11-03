from datetime import date, datetime

import pytest

from deauville import InvalidValueError
from deauville.utils import (
    check_int,
    clean_name,
    festival_day,
    parse_moment,
    slugify,
)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Théâtre des Planches", "theatre-des-planches"),
        ("Élodie  Marchal !", "elodie-marchal"),
        ("  Le Kiosque  ", "le-kiosque"),
        ("A -- B", "a-b"),
    ],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_slugify_refuses_a_name_without_letters():
    with pytest.raises(InvalidValueError):
        slugify("!!!")


def test_clean_name_strips_and_refuses_empty():
    assert clean_name("  Hugo ") == "Hugo"
    with pytest.raises(InvalidValueError, match="cannot be empty"):
        clean_name("   ")


def test_check_int_refuses_bool_and_out_of_range():
    assert check_int(5, "x", 1, 10) == 5
    with pytest.raises(InvalidValueError):
        check_int(True, "x", 0, 10)
    with pytest.raises(InvalidValueError):
        check_int(11, "x", 1, 10)


def test_a_festival_day_ends_at_six():
    assert festival_day(datetime(2027, 6, 12, 0, 30)) == date(2027, 6, 11)
    assert festival_day(datetime(2027, 6, 12, 5, 59)) == date(2027, 6, 11)
    assert festival_day(datetime(2027, 6, 12, 6, 0)) == date(2027, 6, 12)


def test_parse_moment_errors():
    with pytest.raises(InvalidValueError):
        parse_moment("June 11")
    with pytest.raises(InvalidValueError, match="time zone"):
        parse_moment("2027-06-11T21:00+02:00")
