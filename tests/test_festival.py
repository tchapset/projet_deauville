from datetime import datetime

import pytest

from deauville import (
    AlreadyExistsError,
    Artist,
    ArtistBusyError,
    InvalidValueError,
    Lineup,
    NotFoundError,
    OutsideFestivalError,
    Solo,
    Venue,
    VenueBusyError,
    Workshop,
    WorkshopFullError,
)


def solo(start, venue="le-kiosque", artist="max-pellerin", minutes=60):
    return Solo("Show", venue, start, minutes, artist)


def test_venue_and_artist_slugs_must_be_unique(festival):
    with pytest.raises(AlreadyExistsError):
        festival.add_venue(Venue("LE  KIOSQUE", 10))
    with pytest.raises(AlreadyExistsError):
        festival.add_artist(Artist("nora   lebrun"))


def test_artists_are_sorted_by_slug_venues_by_insertion(festival):
    assert [a.slug for a in festival.artists()] == [
        "elodie-marchal",
        "max-pellerin",
        "nora-lebrun",
        "tom-vasseur",
    ]
    assert [v.slug for v in festival.venues()] == ["le-kiosque", "la-cabane"]


def test_venue_needs_30_minutes_between_two_shows(festival):
    # After Hours ends at 02:00 in Le Kiosque
    with pytest.raises(VenueBusyError, match="Le Kiosque is busy with After Hours"):
        festival.add_performance(solo("2027-06-12T02:20"))
    festival.add_performance(solo("2027-06-12T02:30"))


def test_venue_message_is_the_one_of_the_brief(festival):
    with pytest.raises(VenueBusyError) as error:
        festival.add_performance(solo("2027-06-12T01:30"))
    assert str(error.value) == (
        "Le Kiosque is busy with After Hours (2027-06-12 01:00-02:00). "
        "Leave 30 minutes between two shows."
    )


def test_a_show_just_before_is_also_refused(festival):
    with pytest.raises(VenueBusyError):
        festival.add_performance(solo("2027-06-12T00:00"))  # ends 01:00, gap 0
    festival.add_performance(solo("2027-06-11T23:30"))  # ends 00:30, gap 30


def test_artist_needs_30_minutes_in_any_venue(festival):
    with pytest.raises(ArtistBusyError, match="Nora Lebrun"):
        festival.add_performance(solo("2027-06-12T02:10", "la-cabane", "nora-lebrun"))
    festival.add_performance(solo("2027-06-12T02:30", "la-cabane", "nora-lebrun"))


def test_artist_busy_in_any_role(festival):
    gala = Lineup(
        "Gala",
        "la-cabane",
        "2027-06-12T01:30",
        60,
        "tom-vasseur",
        ["nora-lebrun", "max-pellerin"],
    )
    with pytest.raises(ArtistBusyError):
        festival.add_performance(gala)


def test_unknown_references(festival):
    with pytest.raises(NotFoundError, match="Unknown venue"):
        festival.add_performance(solo("2027-06-11T20:00", "nowhere"))
    with pytest.raises(NotFoundError, match="Unknown artist"):
        festival.add_performance(solo("2027-06-11T20:00", artist="ghost"))
    with pytest.raises(NotFoundError):
        festival.get_performance("nothing")


def test_performance_must_be_in_a_festival_day(festival):
    with pytest.raises(OutsideFestivalError):
        festival.add_performance(solo("2027-06-09T20:00"))
    with pytest.raises(OutsideFestivalError):  # 03:00 on the 10th is still the 9th
        festival.add_performance(solo("2027-06-10T03:00"))
    with pytest.raises(OutsideFestivalError):
        festival.add_performance(solo("2027-06-14T06:30"))
    # 00:30 on the 14th belongs to the 13th, the last day: allowed
    festival.add_performance(solo("2027-06-14T00:30"))


def test_failed_change_changes_nothing(festival):
    before = [p.id for p in festival.performances()]
    with pytest.raises(VenueBusyError):
        festival.add_performance(solo("2027-06-12T01:30"))
    assert [p.id for p in festival.performances()] == before


def test_move_a_performance_changes_its_id(festival):
    moved = festival.replace_performance(
        "le-kiosque-2027-06-12-0100",
        solo("2027-06-12T03:00", artist="nora-lebrun"),
    )
    assert moved.id == "le-kiosque-2027-06-12-0300"
    assert [p.id for p in festival.performances()] == [moved.id]


def test_move_may_overlap_its_own_old_slot(festival):
    festival.replace_performance(
        "le-kiosque-2027-06-12-0100",
        solo("2027-06-12T01:15", artist="nora-lebrun"),
    )


def test_move_onto_a_busy_slot_leaves_it_where_it_was(festival):
    festival.add_performance(solo("2027-06-12T04:00"))
    with pytest.raises(VenueBusyError):
        festival.replace_performance(
            "le-kiosque-2027-06-12-0100",
            solo("2027-06-12T04:10", artist="nora-lebrun"),
        )
    assert festival.get_performance("le-kiosque-2027-06-12-0100")


def test_remove_performance(festival):
    festival.remove_performance("le-kiosque-2027-06-12-0100")
    assert festival.performances() == []
    with pytest.raises(NotFoundError):
        festival.remove_performance("le-kiosque-2027-06-12-0100")


def test_workshop_registration_through_the_festival(festival):
    shop = Workshop("Improv", "la-cabane", "2027-06-11T10:30", 120, "tom-vasseur", 12)
    festival.add_performance(shop)  # La Cabane has 3 seats
    for name in ("A", "B", "C"):
        festival.register_participant(shop.id, name)
    with pytest.raises(WorkshopFullError):
        festival.register_participant(shop.id, "D")
    assert len(festival.get_performance(shop.id).participants) == 3
    with pytest.raises(InvalidValueError, match="not a workshop"):
        festival.register_participant("le-kiosque-2027-06-12-0100", "A")


def test_workshop_with_too_many_participants_is_refused(festival):
    shop = Workshop(
        "Improv",
        "la-cabane",
        "2027-06-11T10:30",
        120,
        "tom-vasseur",
        12,
        ["A", "B", "C", "D"],
    )
    with pytest.raises(WorkshopFullError):
        festival.add_performance(shop)


def test_programme_order_day_and_filters(festival):
    festival.add_performance(solo("2027-06-11T20:00", "la-cabane"))
    festival.add_performance(solo("2027-06-11T20:00", "le-kiosque", "tom-vasseur"))
    day = festival.performances(day="2027-06-11")
    # same start: ordered by venue name (La Cabane before Le Kiosque)
    assert [p.venue for p in day[:2]] == ["la-cabane", "le-kiosque"]
    assert day[-1].id == "le-kiosque-2027-06-12-0100"  # after midnight, same day
    assert all(p.venue == "la-cabane" for p in festival.performances(venue="la-cabane"))
    with pytest.raises(NotFoundError):
        festival.performances(venue="nowhere")


def test_now_and_up_next(festival):
    for hour in (3, 5, 7, 9):
        festival.add_performance(solo(f"2027-06-12T0{hour}:00"))
    playing, coming = festival.now(datetime(2027, 6, 12, 1, 30))
    assert [p.id for p in playing] == ["le-kiosque-2027-06-12-0100"]
    assert len(coming) == 3
    assert festival.now(datetime(2027, 6, 12, 2, 0))[0] == []  # end is exclusive


def test_show_counts_include_artists_without_show(festival):
    counts = {a.slug: n for a, n in festival.show_counts()}
    assert counts["nora-lebrun"] == 1 and counts["tom-vasseur"] == 0
