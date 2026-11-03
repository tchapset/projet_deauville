import pytest

from deauville import (
    InvalidValueError,
    Lineup,
    Performance,
    Solo,
    Venue,
    Workshop,
    WorkshopFullError,
)
from deauville.exceptions import AlreadyExistsError


def solo(**changes):
    values = dict(
        title="Show",
        venue="le-kiosque",
        start="2027-06-12T01:00",
        duration_minutes=60,
        artist="nora-lebrun",
    )
    return Solo(**{**values, **changes})


def test_id_and_end_and_festival_day():
    show = solo()
    assert show.id == "le-kiosque-2027-06-12-0100"
    assert show.end.isoformat() == "2027-06-12T02:00:00"
    assert str(show.festival_day) == "2027-06-11"


def test_describe_is_readable():
    assert (
        solo(title="After Hours").describe() == "After Hours (2027-06-12 01:00-02:00)"
    )


@pytest.mark.parametrize("duration", [0, 361, -5, 60.5, "60"])
def test_duration_range(duration):
    with pytest.raises(InvalidValueError):
        solo(duration_minutes=duration)


def test_title_is_stripped_and_not_empty():
    assert solo(title="  Hi ").title == "Hi"
    with pytest.raises(InvalidValueError):
        solo(title=" ")


@pytest.mark.parametrize("age", [-1, 19])
def test_solo_age_range(age):
    with pytest.raises(InvalidValueError):
        solo(min_age=age)


def lineup(**changes):
    values = dict(
        title="Gala",
        venue="le-kiosque",
        start="2027-06-10T20:30",
        duration_minutes=36,
        host="tom-vasseur",
        acts=["nora-lebrun", "max-pellerin", "elodie-marchal"],
    )
    return Lineup(**{**values, **changes})


def test_lineup_minimum_duration():
    assert Lineup.minimum_duration(3) == 36
    assert lineup().duration_minutes == 36
    with pytest.raises(InvalidValueError, match="at least 36"):
        lineup(duration_minutes=35)


def test_lineup_rules():
    with pytest.raises(InvalidValueError, match="at least 2"):
        lineup(acts=["nora-lebrun"])
    with pytest.raises(InvalidValueError, match="only once"):
        lineup(acts=["nora-lebrun", "nora-lebrun"])
    with pytest.raises(InvalidValueError, match="host"):
        lineup(acts=["tom-vasseur", "nora-lebrun"])


def test_lineup_artists_in_order_of_appearance():
    assert lineup().artist_slugs == (
        "tom-vasseur",
        "nora-lebrun",
        "max-pellerin",
        "elodie-marchal",
    )


def workshop(**changes):
    values = dict(
        title="Improv",
        venue="la-cabane",
        start="2027-06-11T10:30",
        duration_minutes=120,
        teacher="nora-lebrun",
        max_participants=12,
    )
    return Workshop(**{**values, **changes})


def test_workshop_capacity_is_the_smaller_of_both():
    small = Venue("La Cabane", 3)
    assert workshop().capacity(small) == 3
    assert workshop(max_participants=2).capacity(small) == 2


def test_workshop_registration_ignores_case_and_stops_when_full():
    cabane = Venue("La Cabane", 2)
    shop = workshop()
    shop.register("  Camille R. ", cabane)
    with pytest.raises(AlreadyExistsError):
        shop.register("camille r.", cabane)
    shop.register("Yanis", cabane)
    with pytest.raises(WorkshopFullError):
        shop.register("Lou", cabane)
    assert shop.participants == ("Camille R.", "Yanis")


def test_workshop_refuses_twice_the_same_participant():
    with pytest.raises(InvalidValueError):
        workshop(participants=["Lou", "LOU"])
    with pytest.raises(InvalidValueError):
        workshop(max_participants=0)


@pytest.mark.parametrize("make", [solo, lineup, workshop])
def test_to_dict_from_dict_round_trip(make):
    original = make()
    copy = Performance.from_dict(original.to_dict())
    assert type(copy) is type(original)
    assert copy.to_dict() == original.to_dict()


def test_from_dict_errors_are_sentences():
    with pytest.raises(InvalidValueError, match="Missing field 'artist'"):
        Performance.from_dict(
            {
                "kind": "solo",
                "title": "x",
                "venue": "v",
                "start": "2027-06-10T20:00",
                "duration_minutes": 60,
            }
        )
    with pytest.raises(InvalidValueError, match="Unknown kind"):
        Performance.from_dict({"kind": "circus"})
