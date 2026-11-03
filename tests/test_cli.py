from pathlib import Path

from deauville.cli import main

DATA = str(Path(__file__).parent.parent / "data" / "festival.json")


def test_programme(capsys):
    assert main(["--data", DATA, "programme", "2027-06-11"]) == 0
    out = capsys.readouterr().out
    assert "After Hours" in out  # starts at 01:00 on the 12th, still the 11th
    assert out.index("Improv for Beginners") < out.index("After Hours")


def test_programme_unknown_day(capsys):
    assert main(["--data", DATA, "programme", "2027-07-01"]) == 1
    assert "not a day of the festival" in capsys.readouterr().err


def test_programme_bad_date(capsys):
    assert main(["--data", DATA, "programme", "June 11"]) == 1
    assert "Error:" in capsys.readouterr().err


def test_artists(capsys):
    assert main(["--data", DATA, "artists"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 12
    assert lines[0].startswith("Élodie Marchal")  # sorted by slug


def test_now(capsys):
    assert main(["--data", DATA, "now", "--at", "2027-06-11T21:00"]) == 0
    out = capsys.readouterr().out
    assert "Tall Tales" in out and "Up next" in out


def test_missing_data_file(capsys, tmp_path):
    assert main(["--data", str(tmp_path / "x.json"), "artists"]) == 1
    assert "Cannot read" in capsys.readouterr().err
