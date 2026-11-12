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


class _NoAliases(yaml.SafeDumper):
    """A shared list (one `origin` tuple reused across rows) is written out each time."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


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


def _raw_blocks(text: str) -> list[str]:
    """*text*'s top-level list items, each verbatim (the first item's indent)."""
    import re

    lines = text.splitlines(keepends=True)
    first = next((ln for ln in lines if re.match(r"^\s*- ", ln)), None)
    if first is None:
        return []
    indent = first[: len(first) - len(first.lstrip())]
    blocks: list[str] = []
    for ln in lines:
        if ln.startswith(indent + "- ") and (not indent or not ln[len(indent)].isspace()):
            blocks.append(ln)
        elif blocks:
            blocks[-1] += ln
    return blocks


def write_fragments(
    root: Path,
    rows: str | Iterable[Mapping[str, Any]],
    *,
    repo: str = "o/r",
    feature: str | None = None,
) -> list[Path]:
    """Write *rows* as fragments under *root*, one per origin spec (`legacy` for the
    rest) unless *feature* names the one.

    *rows* is YAML list-item text (each item kept byte for byte, as a hand-shaped
    fixture means it) or row mappings (dumped). Returns the fragment paths written.
    With no rows, nothing is written unless *feature* is given (an empty fragment
    carries the repo's identity)."""
    folder = root / FRAGMENTS_REL
    folder.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[str]] = {}
    if isinstance(rows, str):
        blocks = _raw_blocks(rows)
        items = [(yaml.safe_load(b) or [{}])[0] for b in blocks]
        texts = [b if b.endswith("\n") else b + "\n" for b in blocks]
    else:
        items = [dict(r) for r in rows]
        texts = []
        for r in items:
            dumped = yaml.dump([r], Dumper=_NoAliases, default_flow_style=False, sort_keys=False)
            texts.append("".join(f"  {ln}\n" if ln else "\n" for ln in dumped.splitlines()))
    if feature is not None:
        groups[feature] = texts
    else:
        for item, text in zip(items, texts, strict=True):
            groups.setdefault(_feature_of(item), []).append(text)
    written: list[Path] = []
    for name, group in sorted(groups.items()):
        path = folder / f"{name}.yaml"
        path.write_text(fragment_text(name, "".join(group), repo=repo))
        written.append(path)
    return written


def write_matrix_fragments(root: Path, matrix_text: str) -> list[Path]:
    """*matrix_text* in the retired `matrix.yaml` shape (`org`/`repo`/`rows`), written
    as fragments with each row's text kept verbatim: what a fixture that used to write
    the matrix writes now."""
    import re

    try:
        data = yaml.safe_load(matrix_text) or {}
    except yaml.YAMLError:
        data = None
    if not isinstance(data, dict) or set(data) - {"schema_version", "org", "repo", "rows"}:
        # A fixture that means "an unreadable matrix" is an unreadable fragment now.
        broken = root / FRAGMENTS_REL / "broken.yaml"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text(matrix_text)
        return [broken]
    org, name = data.get("org"), data.get("repo")
    repo = f"{org}/{name}" if org and name else "o/r"
    found = re.search(r"(?m)^rows:[^\n]*\n", matrix_text)
    rows_text = matrix_text[found.end() :] if found else ""
    later = re.search(r"(?m)^[A-Za-z_][\w-]*\s*:", rows_text)  # a key after `rows:`
    if later:
        rows_text = rows_text[: later.start()]
    if not data.get("rows"):
        # An empty matrix that named its repo keeps that identity in an empty fragment.
        return write_fragments(root, [], repo=repo, feature="legacy") if org and name else []
    if re.search(r"(?m)[&*]id\d+\b", rows_text):
        # A dumped fixture shares objects through anchors: split rows, not text.
        return write_fragments(root, data["rows"], repo=repo)
    return write_fragments(root, rows_text, repo=repo)


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


RETIRED_MATRIX_REL = "docs/acceptance/matrix.yaml"


def make_matrix_repo(
    tmp_path: Path, matrix_rows: str, *, header: str = MATRIX_HEADER, **kwargs: Any
) -> Path:
    """`make_repo`, but holding the RETIRED v5 `matrix.yaml` instead of fragments: for
    the tests of the matrix kind's own migrations and repairs, which keep that shape on
    purpose (spec 2026-11-04 R19)."""
    root = make_repo(tmp_path, matrix_rows, header=header, **kwargs)
    for path in (root / FRAGMENTS_REL).glob("*.yaml"):
        path.unlink()
    stamp = "" if "schema_version" in header else "schema_version: 5\n"
    (root / RETIRED_MATRIX_REL).write_text(stamp + header + matrix_rows)
    return root


def matrix_registry_up_to_v5() -> Any:
    """A migration registry holding the matrix kind as it stood at version 5 (not
    retired) and the shipped matrix hops up to 5: what the tests of the 1 → … → 5
    hops run, so a migrated matrix is still there to read. The 5 → 6 split is
    `test_migration_matrix_fragments.py`'s subject."""
    from dataclasses import replace

    import fr.artifacts  # noqa: F401  (registration rides on the package import)
    from fr.artifacts.registry import ARTIFACT_KINDS
    from fr.artifacts.runner import MIGRATIONS, MigrationRegistry

    kind = replace(ARTIFACT_KINDS["matrix"], current_version=5, retired=False)
    reg = MigrationRegistry(kinds={"matrix": kind})
    for step in MIGRATIONS.schema_migrations("matrix"):
        if step.to_version <= 5:
            reg.register(step)
    return reg


def fragments_text(root: Path) -> str:
    """Every fragment's text, in name order: what a test that compared the retired
    matrix's bytes compares now."""
    return "".join(p.read_text() for p in sorted((root / FRAGMENTS_REL).glob("*.yaml")))
