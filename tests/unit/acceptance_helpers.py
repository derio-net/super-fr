"""Shared fixture builders for the acceptance-matrix test files.

Acceptance rows live in per-feature fragments under `docs/acceptance/features/`
(spec 2026-11-04-repo-feature-settings R16, R19); `write_fragments` is the ONE
place a test states that shape. The matrix-migration tests keep the retired
`matrix.yaml` shape on purpose and do not use it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

FRAGMENTS_REL = "docs/acceptance/features"


def _feature_of(row: Mapping[str, Any]) -> str:
    """The fragment a row belongs in: its one origin spec's slug, else `legacy`
    (the migration's rule, `fr.artifacts.matrix_fragments`)."""
    from fr.acceptance.logical import is_logical, parse_logical, to_logical

    slugs = set()
    for origin in row.get("origin") or ():
        ref = to_logical(str(origin))
        if is_logical(ref):
            parsed = parse_logical(ref)
            if parsed.kind == "spec":
                slugs.add(parsed.slug)
    return next(iter(slugs)) if len(slugs) == 1 else "legacy"


def fragment_text(feature: str, rows_text: str, *, repo: str = "o/r") -> str:
    """One fragment's text around *rows_text* (YAML list items under `rows:`)."""
    return f"schema_version: 1\nfeature: {feature}\nrepo: {repo}\nrows:\n{rows_text}"


def write_fragments(
    root: Path,
    rows: str | Iterable[Mapping[str, Any]],
    *,
    repo: str = "o/r",
    feature: str | None = None,
) -> list[Path]:
    """Write *rows* (YAML list-item text, or row mappings) as fragments under *root*,
    one per origin spec (`legacy` for the rest) unless *feature* names the one.

    Returns the fragment paths written. With no rows, nothing is written unless
    *feature* is given (an empty fragment carries the repo's identity)."""
    if isinstance(rows, str):
        parsed = yaml.safe_load(rows) if rows.strip() else []
        items: list[Mapping[str, Any]] = list(parsed or [])
    else:
        items = list(rows)
    folder = root / FRAGMENTS_REL
    folder.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[Mapping[str, Any]]] = {}
    if feature is not None:
        groups[feature] = items
    else:
        for item in items:
            groups.setdefault(_feature_of(item), []).append(item)
    written: list[Path] = []
    for name, group in sorted(groups.items()):
        body = (
            yaml.safe_dump([dict(r) for r in group], default_flow_style=False, sort_keys=False)
            if group
            else ""
        )
        text = fragment_text(
            name, "".join(f"  {ln}\n" if ln else "\n" for ln in body.splitlines()), repo=repo
        )
        path = folder / f"{name}.yaml"
        path.write_text(text)
        written.append(path)
    return written


def write_matrix_fragments(root: Path, matrix_text: str) -> list[Path]:
    """*matrix_text* in the retired `matrix.yaml` shape (`org`/`repo`/`rows`), written
    as fragments: what a fixture that used to write the matrix writes now."""
    data = yaml.safe_load(matrix_text) or {}
    org, name = data.get("org"), data.get("repo")
    repo = f"{org}/{name}" if org and name else "o/r"
    rows = data.get("rows") or []
    return write_fragments(root, rows, repo=repo, feature=None if rows else "legacy")


def fragment_rows(root: Path) -> dict[str, dict[str, Any]]:
    """Every row in *root*'s fragments, by id, as written (no fold)."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((root / FRAGMENTS_REL).glob("*.yaml")):
        for r in (yaml.safe_load(path.read_text()) or {}).get("rows") or []:
            out[str(r["id"])] = r
    return out


def fragment_of(root: Path, row_id: str) -> Path:
    """The fragment file that holds *row_id*."""
    for path in sorted((root / FRAGMENTS_REL).glob("*.yaml")):
        rows = (yaml.safe_load(path.read_text()) or {}).get("rows") or []
        if any(str(r.get("id")) == row_id for r in rows):
            return path
    raise AssertionError(f"no fragment holds row {row_id}")


MATRIX_HEADER = "org: derio-net\nrepo: own\nrows:\n"

ROW_TMPL = """\
  - id: {id}
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: [{origin}]
    levels:
      unit: [{unit}]
    status: {status}
    notes: "n"
"""


def row(
    id: str = "r1",
    origin: str = '"own:docs/superpowers/specs/s.md"',
    unit: str = '"own:tests/test_a.py"',
    status: str = "ci",
) -> str:
    return ROW_TMPL.format(id=id, origin=origin, unit=unit, status=status)


def make_repo(
    tmp_path: Path,
    matrix_rows: str,
    *,
    name: str = "own",
    git: bool = True,
    header: str = MATRIX_HEADER,
    ci: bool = True,
) -> Path:
    """A minimal fr-shaped repo: matrix, one Test-Plan spec, one test file.

    ``ci`` adds a GitHub Actions workflow, so a row may move to `ci` (gh#775:
    a repo with no CI config refuses that status)."""
    root = tmp_path / name
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / "docs" / "superpowers" / "implemented" / "specs").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "docs" / "superpowers" / "specs" / "s.md").write_text("# s\n\n## Test Plan\n\n1. x\n")
    (root / "tests" / "test_a.py").write_text("def test_a(): pass\n")
    write_matrix_fragments(root, header + matrix_rows)
    if git:
        (root / ".git").mkdir()
    if ci:
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    return root
