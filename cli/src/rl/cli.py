"""Command-line entrypoint for `rlite`."""

import argparse
import sys
from typing import NoReturn

from rl import __version__

EXIT_USAGE = 64


class _Parser(argparse.ArgumentParser):
    """Argument parser that exits with EX_USAGE (64) instead of argparse's default 2.

    Exit code 2 is not used for usage errors so Claude never confuses a flag typo
    with a plan validation error (see the exit code table in the docs).
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser. Subcommands are added phase by phase (see ROADMAP.md)."""
    parser = _Parser(prog="rlite", description="Resonance Lite CLI")
    parser.add_argument("--version", action="version", version=f"rlite {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
