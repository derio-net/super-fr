#!/usr/bin/env python3
"""Keep the README's generated tables and the CLI command tree in step with the code.

Three blocks, each between `<!-- generated:NAME -->` and `<!-- /generated:NAME -->`
markers, are rewritten from their real sources (spec 2026-11-11-docs-currency R21):

- `README.md` `skills`: every `plugins/*/skills/*/SKILL.md`, as name, plugin and the
  first sentence of its `description` front matter;
- `README.md` `cli`: every top-level `fr` command and its help line;
- `docs/reference/cli.md` `cli-tree`: every command and subcommand of `fr.cli:app`.

Nothing outside the markers is touched, so each page's prose and front matter stay
hand-owned. Hidden commands are never listed. Run it with the workspace environment
(it imports `fr`, `typer` and `yaml`).

Usage:
    uv run python scripts/sync-readme.py          # rewrite the blocks
    uv run python scripts/sync-readme.py --check  # exit non-zero on drift, no writes
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import click
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
README = "README.md"
CLI_PAGE = "docs/reference/cli.md"
CELL_LIMIT = 150


class MarkerError(Exception):
    """A generated block's markers are missing or out of order."""


def first_sentence(text: str, limit: int = CELL_LIMIT) -> str:
    """The first sentence of `text` on one line; if long, drop parentheticals, then cut a clause."""
    flat = " ".join(text.split())
    m = re.search(r"[.!?](?=\s|$)", flat)
    out = flat[: m.end()] if m else flat
    if len(out) <= limit:
        return out
    out = re.sub(r"\s*\([^)]*\)", "", out)
    if len(out) <= limit:
        return out
    head = out[:limit]
    cut = max(head.rfind(", "), head.rfind("; "), head.rfind(": "))
    if cut < limit // 2:
        cut = head.rfind(" ")
    return head[:cut].rstrip(" ,;:") + "…"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def skill_rows(root: Path) -> list[tuple[str, str, str]]:
    """(name, plugin, first sentence of description), sorted by name."""
    rows = []
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        front = path.read_text().split("---")[1]
        meta = yaml.safe_load(front)
        rows.append((meta["name"], path.parts[-4], first_sentence(meta["description"])))
    return sorted(rows)


def skills_table(rows: list[tuple[str, str, str]]) -> str:
    lines = ["| Skill | Plugin | What it is for |", "|---|---|---|"]
    lines += [f"| `{n}` | {p} | {_cell(d)} |" for n, p, d in rows]
    return "\n".join(lines)


def _root(app: Any) -> click.Group:
    import typer.main

    return typer.main.get_command(app)  # type: ignore[return-value]


def _help(cmd: click.Command) -> str:
    paragraph = (cmd.help or "").strip().split("\n\n")[0]
    return first_sentence(paragraph).rstrip(".")


def _visible(group: click.Group) -> list[click.Command]:
    return [c for c in group.commands.values() if not c.hidden]


def cli_rows(app: Any) -> list[tuple[str, str]]:
    return [(c.name or "", _help(c)) for c in _visible(_root(app))]


def cli_table(rows: list[tuple[str, str]]) -> str:
    lines = ["| Command | What it does |", "|---|---|"]
    lines += [f"| `fr {n}` | {_cell(h)}. |" if h else f"| `fr {n}` | |" for n, h in rows]
    return "\n".join(lines)


def cli_tree(app: Any) -> str:
    """Every command and subcommand, nested, with its help line."""
    lines: list[str] = []

    def walk(group: click.Group, prefix: str, depth: int) -> None:
        for c in _visible(group):
            path = f"{prefix} {c.name}"
            help_ = _help(c)
            lines.append(f"{'  ' * depth}- `{path}`" + (f": {_cell(help_)}." if help_ else ""))
            if isinstance(c, click.Group):
                walk(c, path, depth + 1)

    walk(_root(app), "fr", 0)
    return "\n".join(lines)


def replace_block(text: str, name: str, body: str) -> str:
    start, end = f"<!-- generated:{name} -->", f"<!-- /generated:{name} -->"
    i, j = text.find(start), text.find(end)
    if i < 0 or j < i:
        raise MarkerError(f"missing or misordered markers for block {name!r}")
    return f"{text[: i + len(start)]}\n{body}\n{text[j:]}"


def build(root: Path, app: Any) -> dict[str, str]:
    """The expected text of each generated file, keyed by repo-relative path."""
    readme = (root / README).read_text()
    readme = replace_block(readme, "skills", skills_table(skill_rows(root)))
    readme = replace_block(readme, "cli", cli_table(cli_rows(app)))
    page = replace_block((root / CLI_PAGE).read_text(), "cli-tree", cli_tree(app))
    return {README: readme, CLI_PAGE: page}


def _fr_app() -> Any:
    from fr.cli import app

    return app


def find_drift(root: Path = REPO_ROOT, app: Any = None) -> list[str]:
    app = app or _fr_app()
    try:
        want = build(root, app)
    except (MarkerError, FileNotFoundError) as err:
        return [str(err)]
    return [f"{p} is out of date" for p, t in want.items() if (root / p).read_text() != t]


def write_all(root: Path = REPO_ROOT, app: Any = None) -> None:
    for path, text in build(root, app or _fr_app()).items():
        (root / path).write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit non-zero on drift; no writes.")
    args = parser.parse_args()
    if args.check:
        drift = find_drift()
        if drift:
            print("scripts/sync-readme.py --check: drift detected:", file=sys.stderr)
            for line in drift:
                print(f"  - {line}", file=sys.stderr)
            print(
                "Run `uv run python scripts/sync-readme.py` (no --check) to fix.", file=sys.stderr
            )
            return 1
        print("scripts/sync-readme.py --check: README and cli.md blocks are in sync.")
        return 0
    write_all()
    print(f"Synced the generated blocks in {README} and {CLI_PAGE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
