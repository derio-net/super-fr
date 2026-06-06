"""`vk repair` library — idempotent stale-ref normalization.

Walks the superpowers tree rewriting plan/spec refs to the canonical
lifecycle-independent form (2026-06-06 spec-path-repair design):

- spec-table File cells → backticked bare slug, annotation tail and all
  other columns preserved byte-for-byte;
- plan `_meta.yaml` `parent_plan:` / `prior_rework:` → bare slug;
  `spec:` (same-repo only) → bare filename.

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

from vk import refs
from vk._urls import is_cross_repo_spec
from vk.refs import RefResolution

_META_REF_FIELDS = ("parent_plan", "prior_rework", "spec")
_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_PLACEHOLDERS = ("—", "-", "", "null", "~")  # incl. YAML nulls in _meta fields


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


def _warn_unresolved(
    out: RepairResult, file: Path, what: str, ref: str, res: RefResolution
) -> None:
    tried = ", ".join(str(p) for p in res.tried)
    out.warnings.append(
        f"{file.name}: {what} {ref!r} does not resolve — tried: {tried}. "
        "Left untouched; if this is a cross-repo row, run `vk repair` in its own repo."
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
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("## Implementation Plans"):
            in_table = True
            continue
        if not in_table:
            continue
        stripped = line.strip()
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
        token_slug = refs.plan_slug(file_cell)
        if not token_slug:
            continue  # placeholder row
        res = refs.resolve_plan_ref(file_cell, repo_root)
        if res.path is None:
            _warn_unresolved(out, spec_path, f"File cell (row {name!r})", file_cell, res)
            continue
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
    return out
