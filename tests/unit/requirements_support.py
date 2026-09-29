"""A spec's Requirements list and the matrix rows citing it, for tests that
walk a run past `brainstorm`.

Spec `2026-09-29-spec-is-the-contract-design.md` §B: `## Requirements` is a
plain `R<n>. <text>` list with no gate on its content. What reads it is phase
sizing (a plan's agentic phases link rows citing `<spec>#R<n>`) and the PR
body's post-merge section, so a test that walks the shipped shape leaves a
spec with the list and a matrix row citing R1. Every file is written through
the real writers (journal serializer, matrix YAML), so the fixture is the real
shape rather than a guess at it.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, spec_journal_slug

MATRIX_REL = "docs/acceptance/matrix.yaml"
ORG = "t"
REPO = "t"

REQUIREMENTS_SECTION = """
## Requirements

R1. The widget is built.
"""


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def spec_ref(spec_rel: str) -> str:
    return f"{REPO}:{spec_rel}"


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
    """Give `spec_rel` a Requirements list and one matrix row (status
    `status`) citing R1 — what phase sizing and the post-merge section read."""
    spec = repo / spec_rel
    spec.parent.mkdir(parents=True, exist_ok=True)
    text = spec.read_text() if spec.exists() else "# spec\n"
    if "## Requirements" not in text:
        spec.write_text(text.rstrip("\n") + "\n" + REQUIREMENTS_SECTION)
    write_matrix(repo, [row(spec_rel, status=status)])


def write_phase_splits(repo: Path, spec_rel: str, plan_slug: str, reasons: dict[int, str]) -> None:
    """Record a `phase-split-<plan>-p<N>` spec-journal decision per phase
    (spec `2026-09-28-phase-sizing-design.md` §B): what lets a multi-phase toy
    plan whose phases link no requirement rows pass `fr plan self-review`'s
    sizing gate once `seed_requirements` gives its spec a Requirements list.
    Each title must start with a reason token (`tier:`, `risk-first:`,
    `review-size:`, or `ask:`)."""
    slug = spec_journal_slug(Path(spec_rel).stem)
    for n, title in sorted(reasons.items()):
        append_journal_entry(
            journal_path(repo, "spec", slug),
            slug,
            JournalEntry(
                kind="decision",
                scope="spec",
                id=f"phase-split-{plan_slug}-p{n}",
                created=now(),
                title=title,
            ),
        )
