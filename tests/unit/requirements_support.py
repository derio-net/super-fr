"""A sound requirements capture for tests that walk a run past `brainstorm`.

Spec `2026-09-28-requirements-traceability-design.md` §C/§D/§F: the shipped
`fr-goal` shape derives `requirements` on `brainstorm` and `spec-review`,
`coverage` on `spec-review` and `requirement-rows` on `deliver`. A test that
walks that shape has to leave what a real brainstorm leaves: a spec with a
`## Requirements` table, an `input` entry in the spec journal the quotes
match, and a matrix row citing each requirement. Every file is written
through the real writers (journal serializer, matrix YAML), so the fixture is
the real shape rather than a guess at it.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, spec_journal_slug

INPUT_TEXT = "build the widget so it counts from 1–20"
QUOTE = "build the widget"
MATRIX_REL = "docs/acceptance/matrix.yaml"
ORG = "t"
REPO = "t"

REQUIREMENTS_SECTION = f"""
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | The widget is built. | input "{QUOTE}" |
"""

COVERAGE_BLOCK = f"""```input-coverage
| span | coverage |
|---|---|
| "{QUOTE}" | R1 |
| "so it counts from 1–20" | context |
```
"""


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def spec_ref(spec_rel: str) -> str:
    return f"{REPO}:{spec_rel}"


def write_input_entry(repo: Path, spec_rel: str, *, body: str = INPUT_TEXT) -> None:
    slug = spec_journal_slug(Path(spec_rel).stem)
    append_journal_entry(
        journal_path(repo, "spec", slug),
        slug,
        JournalEntry(
            kind="discovery",
            scope="spec",
            id="input-1",
            created=now(),
            title="operator input",
            body=body,
            input=True,
        ),
    )


def write_matrix(repo: Path, rows: list[dict[str, object]]) -> Path:
    """The matrix as `fr acceptance init` + `add` leave it: a stamped head,
    then one `render_row_block` per row under a bare `rows:`."""
    from fr.acceptance.edit import render_row_block
    from fr.acceptance.model import Row
    from fr.artifacts.registry import ARTIFACT_KINDS

    path = repo / MATRIX_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    head = yaml.safe_dump(
        {"schema_version": ARTIFACT_KINDS["matrix"].current_version, "org": ORG, "repo": REPO},
        sort_keys=False,
    )
    body = "".join(render_row_block(Row.model_validate(r)) for r in rows)
    path.write_text(f"{head}rows:\n{body}")
    return path


def row(
    spec_rel: str,
    *,
    rid: str = "req-r1",
    fragment: str = "R1",
    status: str = "skipped",
    verify: str | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "id": rid,
        "capability": "Widget",
        "acceptance": f"{rid} acceptance",
        "origin": [f"{spec_ref(spec_rel)}#{fragment}" if fragment else spec_ref(spec_rel)],
        "status": status,
    }
    if verify is not None:
        out["verify"] = verify
    return out


def seed_requirements(repo: Path, spec_rel: str, *, status: str = "skipped") -> None:
    """Make `spec_rel` pass the §C gate: a Requirements section appended to
    the spec, an input entry, and one matrix row (status `status`) citing R1."""
    spec = repo / spec_rel
    spec.parent.mkdir(parents=True, exist_ok=True)
    text = spec.read_text() if spec.exists() else "# spec\n"
    if "## Requirements" not in text:
        spec.write_text(text.rstrip("\n") + "\n" + REQUIREMENTS_SECTION)
    write_input_entry(repo, spec_rel)
    write_matrix(repo, [row(spec_rel, status=status)])
