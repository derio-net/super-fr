#!/usr/bin/env python3
"""Keep the README's generated tables and the CLI command tree in step with the code.

Three blocks, each between `<!-- generated:NAME -->` and `<!-- /generated:NAME -->`
markers, are rewritten from their real sources (spec 2026-11-11-docs-currency R21):

- `README.md` `skills`: every `plugins/*/skills/*/SKILL.md`, as name (linked to the
  published page that covers it), plugin and its line in
  `scripts/readme-skill-summaries.yaml` (the first sentence of its `description`
  where the repo has no such file);
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
SUMMARIES = "scripts/readme-skill-summaries.yaml"
EXPLAINERS = "docs/explainers"
SITE = "https://derio-net.github.io/super-fr"
CELL_LIMIT = 150
UTF8 = "utf-8"


class SourceError(Exception):
    """A source the tables are generated from is unusable; the message names it."""


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


def _front_matter(path: Path, root: Path) -> dict[str, Any]:
    """The YAML front matter of `path`, or a `SourceError` naming the file."""
    rel = path.relative_to(root).as_posix()
    m = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", path.read_text(encoding=UTF8), re.DOTALL)
    if m is None:
        raise SourceError(f"{rel} has no front matter")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as err:
        raise SourceError(f"{rel}: front matter is not YAML ({err})") from err
    if not isinstance(meta, dict):
        raise SourceError(f"{rel}: front matter is not a mapping")
    return meta


def _summaries(root: Path) -> dict[str, str] | None:
    path = root / SUMMARIES
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding=UTF8))
    if not isinstance(data, dict) or not all(isinstance(v, str) and v for v in data.values()):
        raise SourceError(f"{SUMMARIES} must map each skill name to one line of text")
    return data


def skill_rows(root: Path) -> list[tuple[str, str, str]]:
    """(name, plugin, one line), sorted by name.

    The line is the skill's entry in `SUMMARIES`; a repo without that file gets
    the first sentence of each `description`. With the file, a skill with no
    entry and an entry naming no skill are both `SourceError`s.
    """
    summaries = _summaries(root)
    rows = []
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        meta = _front_matter(path, root)
        rel = path.relative_to(root).as_posix()
        name, description = meta.get("name"), meta.get("description")
        if not isinstance(name, str) or not isinstance(description, str) or not description:
            raise SourceError(f"{rel}: front matter needs a `name` and a `description`")
        if summaries is None:
            line = first_sentence(description)
        elif name in summaries:
            line = " ".join(summaries[name].split())
        else:
            raise SourceError(f"{SUMMARIES} has no line for skill {name!r} ({rel})")
        rows.append((name, path.parts[-4], line))
    if summaries is not None:
        unknown = sorted(set(summaries) - {n for n, _, _ in rows})
        if unknown:
            raise SourceError(f"{SUMMARIES} names no shipped skill: {', '.join(unknown)}")
    return sorted(rows)


def skill_pages(root: Path) -> dict[str, str]:
    """Skill name -> published URL of the explainer that covers it.

    The page named after the skill wins; otherwise the first explainer whose
    `covers` matches the skill's SKILL.md. A skill no explainer covers has no link.
    """
    from fr.docs.globs import match
    from fr.docs.model import Page, parse_page

    pages = []
    for path in sorted((root / EXPLAINERS).glob("*.md")):
        parsed = parse_page(path.relative_to(root).as_posix(), path.read_text(encoding=UTF8))
        if isinstance(parsed, Page):
            pages.append((path.stem, parsed.covers))
    out: dict[str, str] = {}
    for skill in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        name, rel = skill.parent.name, skill.relative_to(root).as_posix()
        covering = [stem for stem, covers in pages if any(match(g, rel) for g in covers)]
        if covering:
            stem = name if name in covering else covering[0]
            out[name] = f"{SITE}/{stem}.html"
    return out


def skills_table(rows: list[tuple[str, str, str]], pages: dict[str, str] | None = None) -> str:
    pages = pages or {}
    lines = ["| Skill | Plugin | What it is for |", "|---|---|---|"]
    for n, p, d in rows:
        name = f"[`{n}`]({pages[n]})" if n in pages else f"`{n}`"
        lines.append(f"| {name} | {p} | {_cell(d)} |")
    return "\n".join(lines)


def _root(app: Any) -> click.Group:
    import typer.main

    return typer.main.get_command(app)  # type: ignore[return-value]


# A parenthetical that only points at an issue, a spec or a requirement: noise to a
# reader of the published tables, who has neither.
_INTERNAL_REF = re.compile(r"\s*\((?=[^()]*(?:gh#\d|#\d{2,}|\bspec \d{4}-|§|\bR\d+\b))[^()]*\)")
_TRAILING_SPEC = re.compile(r"\s+—\s+spec\b.*\Z", re.DOTALL)
NO_LIMIT = 10_000


def _help(cmd: click.Command, limit: int = CELL_LIMIT) -> str:
    paragraph = (cmd.help or "").strip().split("\n\n")[0]
    paragraph = _TRAILING_SPEC.sub("", _INTERNAL_REF.sub("", paragraph))
    return first_sentence(paragraph, limit).rstrip(".")


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
            help_ = _help(c, NO_LIMIT)
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
    readme = (root / README).read_text(encoding=UTF8)
    readme = replace_block(readme, "skills", skills_table(skill_rows(root), skill_pages(root)))
    readme = replace_block(readme, "cli", cli_table(cli_rows(app)))
    page = replace_block((root / CLI_PAGE).read_text(encoding=UTF8), "cli-tree", cli_tree(app))
    return {README: readme, CLI_PAGE: page}


def _fr_app() -> Any:
    from fr.cli import app

    return app


def find_drift(root: Path = REPO_ROOT, app: Any = None) -> list[str]:
    app = app or _fr_app()
    try:
        want = build(root, app)
    except (MarkerError, SourceError, FileNotFoundError) as err:
        return [str(err)]
    return [
        f"{p} is out of date" for p, t in want.items() if (root / p).read_text(encoding=UTF8) != t
    ]


def write_all(root: Path = REPO_ROOT, app: Any = None) -> None:
    for path, text in build(root, app or _fr_app()).items():
        (root / path).write_text(text, encoding=UTF8)


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
    try:
        write_all()
    except (MarkerError, SourceError, FileNotFoundError) as err:
        print(f"scripts/sync-readme.py: {err}", file=sys.stderr)
        return 1
    print(f"Synced the generated blocks in {README} and {CLI_PAGE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
