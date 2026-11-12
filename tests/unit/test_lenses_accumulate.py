"""The feature's lens set (spec 2026-11-12-review-lenses R7, §3.B): every lens an agent
added in the run's spec and plan journals, plus every lens a path rule in force
requires for the files the feature changed, restricted to effective lenses."""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.lenses.accumulate import lens_set, lens_set_for

from tests.unit.lens_repo import commit_all, lens_repo

AUTH_RULE = "require:\n  - paths: ['src/auth/**']\n    lenses: [security]\n"
SPEC, PLAN = "2026-11-12-x", "2026-11-12-x"


def _add(root: Path, scope: str, n: int, lens: str, why: str, step: str | None) -> None:
    append_journal_entry(
        journal_path(root, scope, SPEC if scope == "spec" else PLAN),  # type: ignore[arg-type]
        SPEC,
        JournalEntry(
            kind="lens",
            scope=scope,  # type: ignore[arg-type]
            id=f"lens-{lens}-{n}",
            created="2026-11-12T00:00:00+00:00",
            phase=1 if scope == "plan" else None,
            title=why,
            lens=lens,
            step=step,
        ),
    )


def _set(root: Path):
    return lens_set_for(root, spec_slug=SPEC, plan_slug=PLAN)


def test_an_empty_journal_and_no_rule_is_an_empty_set(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    got = _set(root)
    assert got.lenses == () and got.warnings == ()


def test_lenses_from_both_journals_keep_every_reason_and_step(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _add(root, "spec", 1, "security", "takes a token from the operator", "brainstorm")
    _add(root, "plan", 1, "security", "builds a shell command", "implement-phase")
    _add(root, "plan", 1, "tests", "only the happy path is easy to test", None)

    got = _set(root)

    assert [e.lens for e in got.lenses] == ["security", "tests"]
    security = got.lenses[0]
    assert [(r.text, r.step) for r in security.reasons] == [
        ("takes a token from the operator", "brainstorm"),
        ("builds a shell command", "implement-phase"),
    ]
    assert security.rule is None and security.file is None


def test_a_rule_requires_a_lens_for_a_changed_file_with_no_agent_addition(
    tmp_path: Path,
) -> None:
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / "src" / "auth").mkdir(parents=True)
    (root / "src" / "auth" / "x.py").write_text("x = 1\n")
    commit_all(root, "feature")

    (entry,) = _set(root).lenses

    assert (entry.lens, entry.rule, entry.file, entry.reasons) == (
        "security", ("src/auth/**",), "src/auth/x.py", (),
    )  # fmt: skip


def test_a_lens_both_added_and_required_appears_once(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / "src" / "auth").mkdir(parents=True)
    (root / "src" / "auth" / "x.py").write_text("x = 1\n")
    commit_all(root, "feature")
    _add(root, "plan", 1, "security", "why", "implement-phase")

    (entry,) = _set(root).lenses

    assert entry.lens == "security" and entry.file == "src/auth/x.py" and len(entry.reasons) == 1


def test_a_branch_that_drops_the_base_rule_still_requires_the_lens(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / ".fr" / "lenses.yaml").write_text("disable: []\n")
    (root / "src" / "auth").mkdir(parents=True)
    (root / "src" / "auth" / "x.py").write_text("x = 1\n")
    commit_all(root, "feature")

    assert [e.lens for e in _set(root).lenses] == ["security"]


def test_frs_own_artifacts_never_match_a_rule(tmp_path: Path) -> None:
    rule = "require:\n  - paths: ['docs/**']\n    lenses: [tests]\n"
    root = lens_repo(tmp_path, base_config=rule)
    for rel in ("docs/superpowers/plans/p/01.yaml", "docs/acceptance/features/x.yaml"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x: 1\n")
    commit_all(root, "artifacts only")

    assert _set(root).lenses == ()


def test_a_journalled_lens_since_disabled_is_dropped_with_a_warning(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _add(root, "plan", 1, "errors", "a retry hides the cause", "implement-phase")
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text("disable: [errors]\n")

    got = _set(root)

    assert got.lenses == ()
    assert len(got.warnings) == 1 and "errors" in got.warnings[0]


def test_lens_set_reads_the_runs_spec_and_plan_journals(tmp_path: Path) -> None:
    from types import SimpleNamespace

    root = lens_repo(tmp_path)
    _add(root, "spec", 1, "simplicity", "two layers for one call", "spec-review")
    _add(root, "plan", 1, "tests", "a mock stands in for the parser", "implement-phase")
    steps = {
        "brainstorm": SimpleNamespace(emitted={"spec": f"docs/superpowers/specs/{SPEC}-design.md"}),
        "plan": SimpleNamespace(emitted={"plan": f"docs/superpowers/plans/{PLAN}"}),
        "implement": SimpleNamespace(emitted=None),
    }
    run = SimpleNamespace(steps=steps)

    assert [e.lens for e in lens_set(root, run).lenses] == ["simplicity", "tests"]  # type: ignore[arg-type]
