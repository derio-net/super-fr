"""`fr repair` library — idempotent stale-ref normalization.

Walks the superpowers tree rewriting plan/spec refs to the canonical
lifecycle-independent form (2026-06-06 spec-path-repair design):

- spec-table File cells → backticked bare slug, annotation tail and all
  other columns preserved byte-for-byte;
- plan `_meta.yaml` `parent_plan:` / `prior_rework:` → bare slug;
  `spec:` (same-repo only) → bare filename.
- spec-table `## Implementation Plans` headers → the canonical
  `Plan | Repo | File | Depends on` column labels (2026-07-06
  spec-table-header-guard design): `_append_spec_row` writes repo/file/
  depends-on into columns 2-4 unconditionally, so a differently-labeled
  header (hand-authored, no canonical template exists) leaves a table
  that lies about what it holds even though parsing is positional and
  unaffected. Repair walks both active and implemented specs, so a
  header mislabeled at authoring time or carried into an archived spec
  is fixed either way.

A ref is rewritten ONLY when it resolves via `vk.refs`; anything
unresolvable produces a loud warning naming the file, the row/field,
and every path tried — and is left untouched. Running twice is a no-op
(the canonical form is the fixed point). This consciously reverses
2.5.0's "spec tables are never rewritten" doctrine: normalize once,
idempotently, instead of tolerating stale paths forever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fr import refs
from fr._urls import is_cross_repo_spec
from fr.plan_config import strip_dead_keys
from fr.refs import RefResolution

_META_REF_FIELDS = ("parent_plan", "prior_rework", "spec")
_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_PLACEHOLDERS = ("—", "-", "", "null", "~", "none")  # incl. YAML nulls + the 'none' sentinel

_CANONICAL_HEADER_CELLS = ("plan", "repo", "file", "depends on")
_CANONICAL_HEADER_LINE = "| Plan | Repo | File | Depends on |\n"


@dataclass(frozen=True)
class Rewrite:
    """One applied (or planned) ref normalization."""

    file: Path
    field: str  # "File cell (row <name>)" or the _meta field name
    old: str
    new: str


@dataclass
class RepairResult:
    rewrites: list[Rewrite] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def _warn_ambiguous(out: RepairResult, file: Path, what: str, res: RefResolution) -> None:
    matched = ", ".join(str(p) for p in res.matches)
    out.warnings.append(
        f"{file.name}: {what} {res.slug!r} is ambiguous — present under multiple "
        f"lifecycle roots ({matched}); resolved to the active one."
    )


def _warn_unresolved(
    out: RepairResult, file: Path, what: str, ref: str, res: RefResolution
) -> None:
    tried = ", ".join(str(p) for p in res.tried)
    out.warnings.append(
        f"{file.name}: {what} {ref!r} does not resolve — tried: {tried}. "
        "Left untouched; if this is a cross-repo row, run `fr repair` in its own repo."
    )


def _canonical_cell(cell: str, slug: str) -> str:
    """Backticked slug + preserved annotation tail."""
    s = cell.strip()
    m = re.search(r"`[^`]*`", s)
    tail = s[m.end() :].strip() if m else " ".join(s.split()[1:])
    canonical = f"`{slug}`"
    return f"{canonical} {tail}".strip()


def _repair_spec_table(spec_path: Path, repo_root: Path, out: RepairResult, *, write: bool) -> None:
    text = spec_path.read_text()
    if "## Implementation Plans" not in text:
        return
    lines = text.splitlines(keepends=True)
    in_table = False
    seen_header = False
    in_fence = False
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("## Implementation Plans"):
            in_table = True
            continue
        if not in_table:
            continue
        stripped = line.strip()
        # Code fences can abut the table with no blank line — their
        # pipe-shaped contents are NOT rows (review finding 2, 2026-06-06).
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped.startswith("|"):
            if seen_header and not stripped:
                in_table = False
            continue
        seen_header = True
        cells = stripped.strip("|").split("|")
        if len(cells) != 4:
            continue
        name, _repo, file_cell = cells[0].strip(), cells[1].strip(), cells[2].strip()
        if name.lower() == "plan" or set(name) <= {"-", " ", ":"}:
            continue  # header / separator
        if refs.is_pending_placeholder(file_cell):
            continue  # intentional pending-slice placeholder (#351/#359) — not a ref
        token_slug = refs.plan_slug(file_cell)
        if not token_slug:
            continue  # placeholder row
        res = refs.resolve_plan_ref(file_cell, repo_root)
        if res.path is None:
            _warn_unresolved(out, spec_path, f"File cell (row {name!r})", file_cell, res)
            continue
        if len(res.matches) > 1:
            _warn_ambiguous(out, spec_path, f"File cell (row {name!r})", res)
        canonical = _canonical_cell(file_cell, res.slug)
        if file_cell == canonical:
            continue  # already canonical — idempotent fixed point
        cells[2] = f" {canonical} "
        lines[i] = "|" + "|".join(cells) + "|\n"
        out.rewrites.append(
            Rewrite(file=spec_path, field=f"File cell (row {name!r})", old=file_cell, new=canonical)
        )
        changed = True
    if changed and write:
        spec_path.write_text("".join(lines))


def _repair_spec_table_header(spec_path: Path, out: RepairResult, *, write: bool) -> None:
    """Normalize a mislabeled `## Implementation Plans` header.

    Only exact 4-column headers are touched — a different column count
    (e.g. the pre-migrate `Status` column) is `migrate.py`'s shape to
    change, not a mislabeling this repair corrects. The row data is
    never touched; only the header line's text.
    """
    text = spec_path.read_text()
    if "## Implementation Plans" not in text:
        return
    lines = text.splitlines(keepends=True)
    in_table = False
    in_fence = False
    for i, line in enumerate(lines):
        if line.startswith("## Implementation Plans"):
            in_table = True
            continue
        if not in_table:
            continue
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped.startswith("|"):
            continue  # blank line / prose before the header — keep scanning
        # First pipe row after the heading is the header.
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 4:
            return  # different column count — out of scope for this repair
        if tuple(c.lower() for c in cells) == _CANONICAL_HEADER_CELLS:
            return  # already canonical — fixed point
        if line == _CANONICAL_HEADER_LINE:
            return
        lines[i] = _CANONICAL_HEADER_LINE
        out.rewrites.append(
            Rewrite(
                file=spec_path,
                field="Implementation Plans header",
                old=line.strip(),
                new=_CANONICAL_HEADER_LINE.strip(),
            )
        )
        if write:
            spec_path.write_text("".join(lines))
        return


def _repair_meta(meta_path: Path, repo_root: Path, out: RepairResult, *, write: bool) -> None:
    text = meta_path.read_text()
    lines = text.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        m = re.match(r"^(parent_plan|prior_rework|spec):\s*(.+?)\s*$", line)
        if not m:
            continue
        fname, raw = m.group(1), m.group(2)
        value = raw.strip("\"'")
        if value in _PLACEHOLDERS:
            continue
        if fname == "spec":
            if is_cross_repo_spec(value):
                continue  # cross-repo notation is canonical as-is
            res = refs.resolve_spec_ref(value, repo_root)
        else:
            res = refs.resolve_plan_ref(value, repo_root)
        if res.path is None:
            _warn_unresolved(out, meta_path, f"{fname}:", value, res)
            continue
        if len(res.matches) > 1:
            _warn_ambiguous(out, meta_path, f"{fname}:", res)
        canonical = res.path.name
        if value == canonical:
            continue
        lines[i] = f"{fname}: {canonical}\n"
        out.rewrites.append(Rewrite(file=meta_path, field=fname, old=value, new=canonical))
        changed = True
    if changed and write:
        meta_path.write_text("".join(lines))


def repair_repo(repo_root: Path, *, write: bool) -> RepairResult:
    """Repair every spec table and plan `_meta.yaml` under the tree.

    `write=False` plans only (dry-run); the returned rewrites are what
    `write=True` would apply. Per-file failures accumulate — one broken
    file never aborts the walk (apply's doctrine).
    """
    sp = repo_root / "docs" / "superpowers"
    out = RepairResult()
    spec_dirs = (sp / "specs", sp / "implemented" / "specs")
    plan_dirs = (sp / "plans", sp / "implemented" / "plans")
    for d in spec_dirs:
        if not d.is_dir():
            continue
        for spec_path in sorted(d.glob("*.md")):
            try:
                _repair_spec_table_header(spec_path, out, write=write)
                _repair_spec_table(spec_path, repo_root, out, write=write)
            except OSError as e:  # pragma: no cover - exercised via failures test
                out.failures.append(f"{spec_path}: {e}")
    for d in plan_dirs:
        if not d.is_dir():
            continue
        for meta_path in sorted(d.glob("*/_meta.yaml")):
            try:
                _repair_meta(meta_path, repo_root, out, write=write)
            except OSError as e:  # pragma: no cover
                out.failures.append(f"{meta_path}: {e}")
    try:
        _repair_plan_config(sp / "plan-config.yaml", out, write=write)
    except OSError as e:  # pragma: no cover
        out.failures.append(f"{sp / 'plan-config.yaml'}: {e}")
    return out


def _repair_plan_config(cfg: Path, out: RepairResult, *, write: bool) -> None:
    """Strip dead keys (`plan.save_to`, the `dispatch:` block) from a repo's
    plan-config.yaml. Each removal is reported as a `Rewrite`; the file is
    written only when `write=True` and something is actually dead."""
    if not cfg.is_file():
        return
    text = cfg.read_text()
    new_text, removals = strip_dead_keys(text)
    for key in removals:
        out.rewrites.append(
            Rewrite(file=cfg, field="plan-config dead key", old=key, new="(removed)")
        )
    if write and removals and new_text != text:
        cfg.write_text(new_text)
