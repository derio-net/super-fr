"""Rework-plan scaffolding, Origin-table I/O, and numbering helpers.

Sister module to ``src/vk/plan/convert.py`` and ``src/vk/plan/format.py``. The
command-level wrappers in ``src/vk/commands/plan_cmd.py`` delegate here; this
module has no typer dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vk.plan.filename import derive_slug
from vk.plan.parser import parse_plan

_REWORK_NUM_RE = re.compile(r"-rework-(\d+)\.md$")
_TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)
_SPEC_RE = re.compile(r"^\*\*Spec:\*\*\s*`([^`]+)`", re.MULTILINE)
_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)

# Warning text — substrings of these are part of the CLI contract that
# Phases 4 (rework-add) and 5 (rework-list) will grep against. Don't rephrase
# the leading clause without updating downstream consumers and their tests.
_WARN_NO_H1 = "parent has no H1 title; using slug-derived fallback."
_WARN_NOT_ARCHIVED = (
    "parent is not yet archived; Parent plan header points at plans/. Update when parent is moved."
)


def next_rework_number(parent_path: Path, *, repo_root: Path) -> int:
    """Return the next available rework number for ``parent_path``.

    Scans ``docs/superpowers/plans/`` and ``docs/superpowers/archived-plans/``
    for files matching ``<date>-<slug>-rework-<N>.md``. Raises ``ValueError``
    on the same ``N`` appearing in both directories (spec D10 / §4), or when
    ``parent_path`` does not exist on disk.
    Tolerates gaps — returns ``max(N) + 1`` over the combined set.
    """
    if not parent_path.exists():
        raise ValueError(f"parent plan does not exist: {parent_path}")
    slug = derive_slug(parent_path)
    date_prefix = parent_path.stem[:10]  # YYYY-MM-DD
    prefix = f"{date_prefix}-{slug}"

    plans_dir = repo_root / "docs/superpowers/plans"
    archived_dir = repo_root / "docs/superpowers/archived-plans"

    def _scan(dir_: Path) -> set[int]:
        if not dir_.is_dir():
            return set()
        out: set[int] = set()
        for p in dir_.iterdir():
            if not p.is_file() or not p.name.startswith(prefix):
                continue
            m = _REWORK_NUM_RE.search(p.name)
            if m:
                out.add(int(m.group(1)))
        return out

    in_plans = _scan(plans_dir)
    in_archived = _scan(archived_dir)

    collision = in_plans & in_archived
    if collision:
        n = sorted(collision)[0]
        raise ValueError(
            f"ambiguous rework state: rework-{n} exists in both plans/ and "
            f"archived-plans/. Resolve manually before scaffolding."
        )

    combined = in_plans | in_archived
    return max(combined) + 1 if combined else 1


# The blockquote line intentionally wraps past 100 cols — it must render as a single
# markdown line so the GitHub blockquote ``>`` stays intact in the rendered plan.
_SCAFFOLD_TEMPLATE = """\
# {title}

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

{spec_line}**Parent plan:** `{parent_rel_path}` {parent_annotation}
{prior_rework_line}**Status:** Not Started

**Goal:** [Address rework items on {parent_slug_date} without reopening the parent.]

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|

---

## Definition of Done

- [ ] TODO: echo each resolved origin item here when the rework completes.
"""  # noqa: E501


def render_scaffold(
    *,
    parent_title: str,
    parent_slug_date: str,
    spec: str | None,
    parent_rel_path: str,
    parent_archived: bool,
    n: int,
    prior_rework_rel_path: str | None,
) -> str:
    """Render the rework scaffold per spec §3.

    Interpolation rules (spec §3):
    - ``spec``: if ``None``, the whole ``**Spec:** ...`` line is omitted.
    - ``parent_annotation``: ``(merged + archived)`` or ``(not yet archived)``.
    - ``prior_rework_rel_path``: if ``None``, the line is omitted entirely
      (not rendered with ``—``).
    - ``title``: falls back to ``"Rework N for <slug>"`` when
      ``parent_title`` is empty.
    """
    title = f"{parent_title} — Rework {n}" if parent_title else f"Rework {n} for {parent_slug_date}"
    annotation = "(merged + archived)" if parent_archived else "(not yet archived)"
    spec_line = f"**Spec:** `{spec}`\n" if spec else ""
    prior_line = f"**Prior rework:** `{prior_rework_rel_path}`\n" if prior_rework_rel_path else ""
    return _SCAFFOLD_TEMPLATE.format(
        title=title,
        spec_line=spec_line,
        parent_rel_path=parent_rel_path,
        parent_annotation=annotation,
        prior_rework_line=prior_line,
        parent_slug_date=parent_slug_date,
    )


_EXPECTED_ORIGIN_HEADER = "| # | Item | Source | Track |"
_ORIGIN_HEADING_RE = re.compile(r"^## Origin\s*$", re.MULTILINE)


@dataclass(frozen=True, kw_only=True)
class OriginRow:
    number: int
    item: str
    source: str
    track: str


def parse_origin_table(path: Path) -> list[OriginRow]:
    """Parse the Origin table from a rework plan file.

    Raises ValueError on: missing ``## Origin`` heading, malformed header row.
    Empty table (header + separator, no data rows) returns ``[]``. Unescapes
    ``\\|`` back to ``|`` per spec §6.1.
    """
    text = path.read_text(encoding="utf-8")
    heading_match = _ORIGIN_HEADING_RE.search(text)
    if not heading_match:
        raise ValueError(
            f"plan has no ## Origin section. Was this scaffolded via 'vk plan rework'? ({path})"
        )
    after = text[heading_match.end() :]
    lines = after.splitlines()

    # Locate the header row (first non-blank, non-divider line).
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or lines[idx].strip() != _EXPECTED_ORIGIN_HEADER:
        raise ValueError(f"Origin table header malformed. Expected: {_EXPECTED_ORIGIN_HEADER}")
    idx += 1
    # Separator row (| --- | --- | --- | --- |). Skip whatever is there.
    idx += 1

    rows: list[OriginRow] = []
    while idx < len(lines):
        line = lines[idx].rstrip()
        if not line.startswith("|"):
            break  # end of table
        # Split on non-escaped pipes: first replace \| with a sentinel.
        sentinel = "\x00"
        encoded = line.replace(r"\|", sentinel)
        parts = [p.strip().replace(sentinel, "|") for p in encoded.strip("|").split("|")]
        if len(parts) != 4:
            raise ValueError(f"Origin table row has {len(parts)} cells, expected 4: {line!r}")
        try:
            n = int(parts[0])
        except ValueError as e:
            raise ValueError(f"Origin table row # column is not an int: {line!r}") from e
        rows.append(OriginRow(number=n, item=parts[1], source=parts[2], track=parts[3]))
        idx += 1
    return rows


def append_origin_row(path: Path, row: OriginRow) -> None:
    """Append a single row to the Origin table in ``path``.

    Preserves every byte outside the Origin table when line endings are LF.
    (``Path.read_text`` / ``Path.write_text`` apply universal-newline decoding,
    so a CRLF input would be silently LF-normalised on write. Plan files under
    ``docs/superpowers/plans/`` are LF-only, so this is acceptable for the
    scaffold / rework-add flow.)

    Escapes ``|`` in ``item`` and ``source`` by replacing with ``\\|``. Writes
    the file back via ``path.write_text`` (no temp-file rename — single-file
    scaffolds, no reader concurrency concern in CLI contexts).
    """
    text = path.read_text(encoding="utf-8")
    heading_match = _ORIGIN_HEADING_RE.search(text)
    if not heading_match:
        raise ValueError(
            f"plan has no ## Origin section. Was this scaffolded via 'vk plan rework'? ({path})"
        )
    after_heading = heading_match.end()
    lines = text[after_heading:].splitlines(keepends=True)

    # Walk forward to the header; then past separator; then past any data rows.
    abs_offset = after_heading
    idx = 0
    # Skip blanks.
    while idx < len(lines) and lines[idx].strip() == "":
        abs_offset += len(lines[idx])
        idx += 1
    if idx >= len(lines) or lines[idx].strip() != _EXPECTED_ORIGIN_HEADER:
        raise ValueError(f"Origin table header malformed. Expected: {_EXPECTED_ORIGIN_HEADER}")
    abs_offset += len(lines[idx])  # consume header
    idx += 1
    if idx >= len(lines):
        raise ValueError("Origin table truncated after header.")
    abs_offset += len(lines[idx])  # consume separator
    idx += 1
    # Advance past any existing data rows.
    while idx < len(lines) and lines[idx].startswith("|"):
        abs_offset += len(lines[idx])
        idx += 1

    # Build the new row, escaping pipes.
    def _esc(s: str) -> str:
        return s.replace("|", r"\|")

    new_line = f"| {row.number} | {_esc(row.item)} | {_esc(row.source)} | {row.track} |\n"
    # S1 guard: if the preceding byte isn't a newline (e.g. operator-edited file
    # whose separator row lacks a trailing ``\n``), prepend one so the new row
    # doesn't concatenate onto the previous line.
    if abs_offset > 0 and text[abs_offset - 1] != "\n":
        new_line = "\n" + new_line

    new_text = text[:abs_offset] + new_line + text[abs_offset:]
    path.write_text(new_text, encoding="utf-8")


def scaffold_rework(parent_path: Path, *, repo_root: Path) -> tuple[Path, list[str]]:
    """Scaffold a rework plan for ``parent_path``. Returns (output_path, warnings).

    Raises ValueError on structural refusals (spec §7). Callers translate to
    typer.Exit(2). Warnings are stderr-destined strings — caller emits them.
    """
    parent_path = parent_path.resolve()
    if not parent_path.exists():
        raise ValueError(f"parent plan not found: {parent_path}")

    repo_root = repo_root.resolve()
    plans_dir = (repo_root / "docs/superpowers/plans").resolve()
    archived_dir = (repo_root / "docs/superpowers/archived-plans").resolve()
    is_in_plans = parent_path.is_relative_to(plans_dir)
    is_in_archived = parent_path.is_relative_to(archived_dir)
    if not (is_in_plans or is_in_archived):
        raise ValueError(
            "parent plan must live in docs/superpowers/plans/ or "
            f"docs/superpowers/archived-plans/. Got: {parent_path}"
        )

    warnings: list[str] = []
    # Read title/spec directly: rework scaffolding must work even on minimal
    # stub parents that the full plan parser would refuse (no Phase headers).
    # Normalise CRLF before regexing so Windows-edited parents don't smuggle
    # a trailing \r into the captured title (which then lands in the H1 of
    # the rendered scaffold).
    parent_text = parent_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    title_match = _TITLE_RE.search(parent_text)
    title = title_match.group(1).strip() if title_match else ""
    spec_match = _SPEC_RE.search(parent_text)
    spec = spec_match.group(1) if spec_match else None
    if not title:
        warnings.append(_WARN_NO_H1)

    n = next_rework_number(parent_path, repo_root=repo_root)

    slug = derive_slug(parent_path)
    date_prefix = parent_path.stem[:10]
    parent_slug_date = f"{date_prefix}-{slug}"

    # Prior rework: highest archived N lower than the new N.
    prior = _highest_archived_prior(repo_root=repo_root, prefix=parent_slug_date, below=n)

    if is_in_plans:
        warnings.append(_WARN_NOT_ARCHIVED)

    rendered = render_scaffold(
        parent_title=title,
        parent_slug_date=parent_slug_date,
        spec=spec,
        parent_rel_path=str(parent_path.relative_to(repo_root)),
        parent_archived=is_in_archived,
        n=n,
        prior_rework_rel_path=str(prior.relative_to(repo_root)) if prior else None,
    )

    out_path = plans_dir / f"{parent_slug_date}-rework-{n}.md"
    if out_path.exists():
        raise ValueError(f"output path already exists: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    return out_path, warnings


def _highest_archived_prior(*, repo_root: Path, prefix: str, below: int) -> Path | None:
    archived_dir = repo_root / "docs/superpowers/archived-plans"
    if not archived_dir.is_dir():
        return None
    best_n = -1
    best_path: Path | None = None
    for p in archived_dir.iterdir():
        if not p.is_file() or not p.name.startswith(prefix):
            continue
        m = _REWORK_NUM_RE.search(p.name)
        if not m:
            continue
        n = int(m.group(1))
        if n < below and n > best_n:
            best_n = n
            best_path = p
    return best_path


@dataclass(frozen=True)
class ReworkRecord:
    """A single row in ``vk plan rework-list`` output.

    ``parent_path`` is reserved for a future resolver — the list command
    currently leaves it ``None`` because the parent plan reference is a
    relative path inside the rework body, not derivable from the rework
    filename alone. ``spec_path`` mirrors the rework plan's ``**Spec:**``
    header verbatim when present.
    """

    parent_slug: str
    rework_number: int
    status: str
    open_steps: int
    origin_items: int
    by_track: dict[str, int]
    path: str
    parent_path: str | None
    spec_path: str | None


def list_reworks(
    *,
    repo_root: Path,
    include_archived: bool = False,
) -> tuple[list[ReworkRecord], list[str]]:
    """Return ``(records, warnings)``.

    ``records`` is the list of rework plans found under
    ``docs/superpowers/plans/`` (plus ``archived-plans/`` when
    ``include_archived`` is true). ``warnings`` is one human-readable string
    per file that was skipped because it matched the ``*-rework-*.md`` glob
    but could not be parsed as a rework plan — typically a missing or
    malformed ``## Origin`` section.
    """
    dirs = [repo_root / "docs/superpowers/plans"]
    if include_archived:
        dirs.append(repo_root / "docs/superpowers/archived-plans")

    records: list[ReworkRecord] = []
    warnings: list[str] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*-rework-*.md")):
            try:
                records.append(_record_for(p, repo_root))
            except Exception as exc:
                # Use repo-relative paths so warnings match the table's
                # ``path`` column convention; fall back to the absolute
                # path if the file somehow lives outside ``repo_root``.
                try:
                    rel = p.relative_to(repo_root)
                except ValueError:
                    rel = p
                warnings.append(f"skipping {rel}: {exc}")
    return records, warnings


def _record_for(path: Path, repo_root: Path) -> ReworkRecord:
    full_slug = derive_slug(path)
    m = _REWORK_NUM_RE.search(path.name)
    if not m:
        raise ValueError(f"rework file has no -rework-N suffix: {path.name}")
    n = int(m.group(1))
    parent_slug = re.sub(r"-rework-\d+$", "", full_slug)

    # ``parse_plan`` requires at least one Phase or Task header, which
    # scaffold-only rework plans don't yet have. Fall back to scanning the
    # raw header for Status/Spec in that case so the rework still shows up
    # in the list before its phases are written.
    text = path.read_text(encoding="utf-8")
    status = "Not Started"
    spec: str | None = None
    open_steps = 0
    try:
        plan = parse_plan(path)
    except ValueError:
        status_match = _STATUS_RE.search(text)
        if status_match:
            status = status_match.group(1).strip()
        spec_match = _SPEC_RE.search(text)
        if spec_match:
            spec = spec_match.group(1).strip()
    else:
        status = plan.status
        spec = plan.spec
        open_steps = sum(1 for t in plan.all_tasks for s in t.steps if s.state == " ")

    # Let ``parse_origin_table`` errors propagate to ``list_reworks`` —
    # a missing or malformed ``## Origin`` section means the file isn't a
    # rework plan, and it should surface as a skip warning, not a silent
    # zero-row entry.
    rows = parse_origin_table(path)
    by_track: dict[str, int] = {}
    for r in rows:
        by_track[r.track] = by_track.get(r.track, 0) + 1
    return ReworkRecord(
        parent_slug=parent_slug,
        rework_number=n,
        status=status,
        open_steps=open_steps,
        origin_items=len(rows),
        by_track=by_track,
        path=str(path.relative_to(repo_root)),
        parent_path=None,
        spec_path=spec,
    )
