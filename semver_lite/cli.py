"""Command-line interface for semver-lite.

Four subcommands are provided: ``parse``, ``compare``, ``sort`` and
``satisfies``. Exit codes are part of the interface:

======  =====================================================================
``0``   Success. For ``compare`` this also means A is greater than or equal
        to B; for ``satisfies`` it means the version is in the range.
``1``   The comparison came out "less" (``compare``), or the version does not
        satisfy the range (``satisfies``).
``2``   Usage error, or an invalid version or range.
======  =====================================================================
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from .ranges import InvalidRange, satisfies, sort_versions
from .version import InvalidVersion, compare, parse

__all__ = ["build_parser", "main"]

EXIT_OK = 0
EXIT_LESS_OR_UNSATISFIED = 1
EXIT_USAGE = 2

_EPILOG = """\
exit codes:
  0  success; for compare, A is greater than or equal to B
  1  for compare, A is less than B; for satisfies, V is outside RANGE
  2  usage error, invalid version or invalid range

examples:
  semver-lite parse 1.0.0-rc.1
  semver-lite compare 1.0.0-alpha 1.0.0
  semver-lite sort 1.10.0 1.9.0 1.0.0
  semver-lite satisfies 1.2.3 '^1.2.0'
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        The configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="semver-lite",
        description="Parse, compare, sort and test strict SemVer 2.0.0 versions.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    parse_command = subparsers.add_parser(
        "parse",
        help="print the canonical form of a version",
        description="Print the canonical form of a semantic version.",
    )
    parse_command.add_argument("version", help="the version to parse")

    compare_command = subparsers.add_parser(
        "compare",
        help="compare two versions",
        description=(
            "Compare two versions and print 'less', 'equal' or 'greater'. "
            "Exits 1 when the first version is less than the second."
        ),
    )
    compare_command.add_argument("left", help="the left version")
    compare_command.add_argument("right", help="the right version")

    sort_command = subparsers.add_parser(
        "sort",
        help="sort versions in ascending order",
        description=(
            "Print versions in ascending precedence order, one per line. "
            "Reads them from the arguments, or from stdin when none are given."
        ),
    )
    sort_command.add_argument(
        "versions",
        nargs="*",
        help="the versions to sort; omit to read them from stdin",
    )

    satisfies_command = subparsers.add_parser(
        "satisfies",
        help="test a version against a range",
        description=(
            "Print 'true' when the version satisfies the range, otherwise "
            "'false'. Exits 1 when it does not."
        ),
    )
    satisfies_command.add_argument("version", help="the version to test")
    satisfies_command.add_argument("range", help="the range expression to test against")

    return parser


def _read_versions(arguments: Sequence[str]) -> List[str]:
    """Return the versions to sort, reading stdin when no arguments were given.

    Args:
        arguments: the versions given on the command line.

    Returns:
        The versions to sort.

    Raises:
        InvalidVersion: if no versions were given on either the command line or
            stdin, since there is then nothing to do.
    """
    if arguments:
        return list(arguments)
    from_stdin = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    if not from_stdin:
        raise InvalidVersion(
            "no versions to sort: pass them as arguments or pipe them on stdin"
        )
    return from_stdin


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return its exit code.

    Args:
        argv: the argument list without the program name; defaults to
            :data:`sys.argv`.

    Returns:
        ``0`` on success, ``1`` when a comparison is "less" or a version falls
        outside its range, and ``2`` for a usage error or invalid input.
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.print_usage(sys.stderr)
        print("error: a command is required", file=sys.stderr)
        return EXIT_USAGE

    try:
        if arguments.command == "parse":
            print(parse(arguments.version).to_str())
            return EXIT_OK

        if arguments.command == "compare":
            order = compare(arguments.left, arguments.right)
            if order < 0:
                print("less")
                return EXIT_LESS_OR_UNSATISFIED
            print("equal" if order == 0 else "greater")
            return EXIT_OK

        if arguments.command == "sort":
            for version in sort_versions(_read_versions(arguments.versions)):
                print(version.to_str())
            return EXIT_OK

        if arguments.command == "satisfies":
            if satisfies(arguments.version, arguments.range):
                print("true")
                return EXIT_OK
            print("false")
            return EXIT_LESS_OR_UNSATISFIED

    except (InvalidVersion, InvalidRange) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE

    # argparse only dispatches the commands above, so this is unreachable.
    raise AssertionError(f"unhandled command {arguments.command!r}")


def run() -> None:
    """Entry point for the console script: run :func:`main` and exit."""
    sys.exit(main())


if __name__ == "__main__":
    run()