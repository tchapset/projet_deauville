"""Command line: programme of a day, artists, what is on stage now.

Run it with ``uv run deauville --help``. It only displays: every rule is
checked by the festival.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from .exceptions import FestivalError
from .festival import Festival
from .performance import Performance
from .storage import open_storage
from .utils import parse_day, parse_moment

DEFAULT_DATA = "data/festival.json"


def format_line(festival: Festival, performance: Performance) -> str:
    """``21:00 | Le Kiosque | After Hours (solo)``."""
    venue = festival.get_venue(performance.venue)
    time = f"{performance.start:%H:%M}"
    if performance.start.date() != performance.festival_day:
        time += " (+1)"
    return f"{time} | {venue.name} | {performance.title} ({performance.kind})"


def format_moment_line(festival: Festival, performance: Performance) -> str:
    """Same as :func:`format_line` with the full date, for ``now``."""
    venue = festival.get_venue(performance.venue)
    return (
        f"{performance.start:%Y-%m-%d %H:%M}-{performance.end:%H:%M} | "
        f"{venue.name} | {performance.title} ({performance.kind})"
    )


def show_programme(festival: Festival, day_text: str) -> None:
    day = parse_day(day_text)
    if day not in festival.days:
        days = ", ".join(str(d) for d in festival.days)
        raise FestivalError(f"{day} is not a day of the festival. Days: {days}.")
    performances = festival.performances(day=day)
    print(f"Programme for {day}:")
    if not performances:
        print("  Nothing is scheduled this day.")
    for performance in performances:
        print(f"  {format_line(festival, performance)}")


def show_artists(festival: Festival) -> None:
    for artist, count in festival.show_counts():
        word = "show" if count == 1 else "shows"
        print(f"{artist.name}: {count} {word}")


def show_now(festival: Festival, at_text: str | None) -> None:
    at = (
        parse_moment(at_text, "--at")
        if at_text
        else datetime.now().replace(second=0, microsecond=0)
    )
    playing, coming = festival.now(at)
    print(f"At {at:%Y-%m-%d %H:%M}")
    print("On stage:")
    for performance in playing:
        print(f"  {format_moment_line(festival, performance)}")
    if not playing:
        print("  Nothing.")
    print("Up next:")
    for performance in coming:
        print(f"  {format_moment_line(festival, performance)}")
    if not coming:
        print("  Nothing.")


def convert_data(festival: Festival, target: str) -> None:
    """Write the festival to ``target`` (JSON or SQLite, from its extension)."""
    if Path(target).exists():
        raise FestivalError(f"{target} already exists: it is not overwritten.")
    open_storage(target).save(festival)
    print(f"Saved to {target}.")


def serve(data: str, host: str, port: int) -> None:
    """Start the web server: API under /api, websites at / and /admin/."""
    import uvicorn  # imported here: the other commands do not need the server

    from .api import create_app

    app = create_app(data)  # a broken data file stops here, with a sentence
    print(f"Serving on http://{host}:{port}/  (admin: /admin/, docs: /docs)")
    uvicorn.run(app, host=host, port=port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deauville", description="Deauville Festival du Rire."
    )
    parser.add_argument(
        "--data", default=DEFAULT_DATA, help=f"data file (default: {DEFAULT_DATA})"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    programme = commands.add_parser("programme", help="programme of a festival day")
    programme.add_argument("day", help="a day, such as 2027-06-11")
    commands.add_parser("artists", help="artists with their number of shows")
    convert = commands.add_parser(
        "convert", help="copy the data to another file (.json or .db)"
    )
    convert.add_argument("target", help="new file, such as data/festival.db")
    now = commands.add_parser("now", help="on stage now, and the next 3 shows")
    now.add_argument("--at", help="a moment, such as 2027-06-11T21:00")
    server = commands.add_parser("serve", help="start the web server")
    server.add_argument("--host", default="127.0.0.1", help="default: 127.0.0.1")
    server.add_argument("--port", type=int, default=8000, help="default: 8000")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        festival = open_storage(args.data).load()
        if args.command == "programme":
            show_programme(festival, args.day)
        elif args.command == "artists":
            show_artists(festival)
        elif args.command == "convert":
            convert_data(festival, args.target)
        elif args.command == "serve":
            serve(args.data, args.host, args.port)
        else:
            show_now(festival, args.at)
    except FestivalError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
