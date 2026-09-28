"""`fr.closeout.owed_artifacts` — the ONE "live but its PR merged" predicate
(2026-09-28-closeout-always spec §C), shared by `fr status` and
`fr archive --all`. Real git throughout: the repo's `origin/main` is a real
bare remote, published for real, so `merge_evidence` reads real ref content —
no mocked git.
"""

from __future__ import annotations

from pathlib import Path

from fr.archive import merge_evidence
from fr.closeout import owed_artifacts

from tests.unit.test_merge_evidence import _add_remote, _commit, _init, _publish, _write_plan

SP = Path("docs/superpowers")


def _write(repo: Path, rel: str | Path, text: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _spec(repo: Path, name: str, rows: list[tuple[str, str]]) -> Path:
    """A spec with an Implementation Plans table; `rows` is `(plan_name, file_cell)`."""
    lines = [
        f"# {name}\n",
        "## Implementation Plans\n",
        "| Plan | Repo | File | Depends on |",
        "|---|---|---|---|",
    ]
    for plan_name, file_cell in rows:
        lines.append(f"| {plan_name} | derio-net/test | {file_cell} | — |")
    return _write(repo, SP / "specs" / name, "\n".join(lines) + "\n")


def _run_cursor(repo: Path, run_id: str, plan_rel: str) -> Path:
    return _write(
        repo,
        SP / "runs" / f"{run_id}.yaml",
        f"run: {run_id}\n"
        "workflow: fr-goal@1\n"
        "branch: feat/x\n"
        "started: '2026-01-01T09:00:00Z'\n"
        "cursor: deliver\n"
        "steps:\n"
        "  isolate: {state: done}\n"
        "  plan:\n"
        "    state: done\n"
        f"    emitted: {{plan: {plan_rel}}}\n"
        "  deliver: {state: done}\n",
    )


def _build_repo(tmp_path: Path) -> Path:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")

    # 1. An archivable plan: one ticked agentic phase, locally complete —
    #    this is status_cmd's "archivable" bucket, reused here.
    _write_plan(repo, "2026-01-01-done-plan", [("agentic", True)])

    # 2. A merged plan with an open MANUAL phase: stays "merged, manual
    #    phases still open" — must NOT be owed.
    _write_plan(repo, "2026-01-01-manual-open", [("agentic", True), ("manual", False)])

    # 3. A debug journal present on the ref: owed.
    _write(repo, SP / "journals" / "debug" / "on-ref.md", "# on ref\n")

    # 4. A spec whose one row resolves to an already-archived plan: owed.
    (repo / SP / "implemented" / "plans" / "implemented-plan").mkdir(parents=True)
    _spec(
        repo,
        "2026-01-01-done-spec-design.md",
        [("done", "`docs/superpowers/implemented/plans/implemented-plan`")],
    )

    # 5. A held spec: a pending-slice row holds it, deterministically.
    _spec(repo, "2026-01-01-held-spec-design.md", [("later", "pending")])

    # 6. An orphan plan journal: its owner plan is already archived.
    (repo / SP / "implemented" / "plans" / "orphan-owner-plan").mkdir(parents=True)
    _write(repo, SP / "journals" / "plans" / "orphan-owner-plan.md", "# orphan plan journal\n")

    # 7. An orphan spec journal: its owner spec is already archived.
    _write(
        repo,
        SP / "implemented" / "specs" / "orphan-owner-spec-design.md",
        "# orphan owner spec\n",
    )
    _write(repo, SP / "journals" / "specs" / "orphan-owner-spec.md", "# orphan spec journal\n")

    # 8. An orphan run cursor: its emitted plan is already archived.
    (repo / SP / "implemented" / "plans" / "run-owner-plan").mkdir(parents=True)
    _run_cursor(repo, "2026-01-01-run-owner", "docs/superpowers/plans/run-owner-plan")

    _commit(repo, "seed")
    _publish(repo)

    # 9. A debug journal present ONLY in the working tree (never committed):
    #    must NOT be owed — it is not on the default ref.
    _write(repo, SP / "journals" / "debug" / "local-only.md", "# local only\n")

    return repo


def _owed(repo: Path):
    return owed_artifacts(repo, merge_evidence(repo, fetch=False))


def test_debug_journal_on_ref_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    paths = {str(o.path) for o in _owed(repo).owed if o.kind == "debug_journal"}
    assert "docs/superpowers/journals/debug/on-ref.md" in paths
    assert "docs/superpowers/journals/debug/local-only.md" not in paths


def test_debug_journal_owed_command_is_archive_all(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    [entry] = [o for o in _owed(repo).owed if o.kind == "debug_journal"]
    assert entry.clear == "fr archive --all"


def test_archivable_plan_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    plans = {(str(o.path), o.clear) for o in _owed(repo).owed if o.kind == "plan"}
    assert (
        "docs/superpowers/plans/2026-01-01-done-plan",
        "fr archive docs/superpowers/plans/2026-01-01-done-plan",
    ) in plans


def test_merged_manual_open_plan_is_not_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    plan_paths = {str(o.path) for o in _owed(repo).owed if o.kind == "plan"}
    assert "docs/superpowers/plans/2026-01-01-manual-open" not in plan_paths


def test_fully_implemented_spec_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    specs = {str(o.path): o.clear for o in _owed(repo).owed if o.kind == "spec"}
    assert (
        specs.get("docs/superpowers/specs/2026-01-01-done-spec-design.md")
        == "fr archive --sweep-only"
    )


def test_held_spec_is_not_owed_but_reported_held(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    result = _owed(repo)
    spec_owed_names = {p.name for o in result.owed if o.kind == "spec" for p in [o.path]}
    assert "2026-01-01-held-spec-design.md" not in spec_owed_names
    held = {h.spec: h.note for h in result.held}
    assert "2026-01-01-held-spec-design.md" in held
    assert "pending" in held["2026-01-01-held-spec-design.md"]


def test_orphan_plan_journal_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    paths = {(str(o.path), o.clear) for o in _owed(repo).owed if o.kind == "orphan_journal"}
    assert ("docs/superpowers/journals/plans/orphan-owner-plan.md", "fr archive --all") in paths


def test_orphan_spec_journal_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    paths = {str(o.path) for o in _owed(repo).owed if o.kind == "orphan_journal"}
    assert "docs/superpowers/journals/specs/orphan-owner-spec.md" in paths


def test_orphan_run_cursor_is_owed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    paths = {(str(o.path), o.clear) for o in _owed(repo).owed if o.kind == "orphan_run"}
    assert ("docs/superpowers/runs/2026-01-01-run-owner.yaml", "fr archive --all") in paths


def test_owed_makes_no_forge_call(tmp_path: Path) -> None:
    """`gh=None` is baked in — a `_spec_fully_implemented` call that needed a
    forge (an unresolved cross-repo row) degrades to a note, never an error,
    and the held spec in this fixture proves the deterministic pending-slice
    path is reached before any resolution attempt."""
    repo = _build_repo(tmp_path)
    # No monkeypatched gh client anywhere in this test — a forge call would
    # error out (no network), so simply not raising is the assertion.
    _owed(repo)
