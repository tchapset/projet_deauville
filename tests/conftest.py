import pytest

from deauville import Artist, Festival, Solo, Venue


@pytest.fixture
def festival() -> Festival:
    """A small festival: 2 venues, 4 artists, one show."""
    festival = Festival("Test Fest", "2027-06-10", "2027-06-13")
    festival.add_venue(Venue("Le Kiosque", 120, "Beach"))
    festival.add_venue(Venue("La Cabane", 3, "Beach"))
    for name in ("Nora Lebrun", "Max Pellerin", "Tom Vasseur", "Élodie Marchal"):
        festival.add_artist(Artist(name))
    festival.add_performance(
        Solo("After Hours", "le-kiosque", "2027-06-12T01:00", 60, "nora-lebrun")
    )
    return festival
