"""`fr-herdr` — the herdr adapter's console script (spec 2026-10-06 §A, R1/R4/R5).

One subcommand, `restart-idle`: resume idle Claude or freshly recover managed OpenCode,
so the sessions pick up the plugins `post_merge` just installed. argparse, no Typer:
`fr-herdr` depends only on `fr` and `fr-dispatch`.

Exit codes (R4): 0 when no pane failed, 1 when any pane failed, 2 on a refusal (outside
a herdr session, or herdr could not be asked).
"""

from __future__ import annotations

import argparse
import sys

from fr_herdr import restart
from fr_herdr._herdr import HerdrError
from fr_herdr.runner import HerdrRunner


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fr-herdr", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    idle = sub.add_parser(
        "restart-idle",
        help="resume idle Claude or recover managed OpenCode fresh (dry run without --yes)",
    )
    idle.add_argument("--yes", action="store_true", help="restart; without it, print the plan")
    idle.add_argument(
        "--exclude", action="append", default=[], metavar="PANE", help="skip this pane (repeatable)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # The runner's own predicate: herdr is never driven from outside a session (R5).
    refusal = HerdrRunner().preflight([])
    if refusal:
        print(f"fr-herdr: {refusal}", file=sys.stderr)
        return 2
    try:
        report = restart.restart_idle(yes=args.yes, exclude=tuple(args.exclude))
    except HerdrError as exc:
        print(f"fr-herdr: {exc}", file=sys.stderr)
        return 2
    for line in report.lines:
        print(line.render())
        if line.resume:
            print(f"  resume: {line.resume}")
    if report.dry_run:
        print("dry run: nothing was sent; pass --yes to restart")
    print(report.summary())
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
