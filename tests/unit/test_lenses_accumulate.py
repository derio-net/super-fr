"""The feature's lens set (spec 2026-11-12-review-lenses R7, §3.B): every lens an agent
added in the run's spec and plan journals, plus every lens a path rule in force
requires for the files the feature changed, restricted to effective lenses."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.lenses.accumulate import lens_set, lens_set_for
from fr.lenses.model import LensError

from tests.unit.lens_repo import commit_all, git, lens_repo

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


def test_a_journalled_lens_the_repo_disabled_is_dropped_with_a_warning(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config="disable: [errors]\n")
    _add(root, "plan", 1, "errors", "a retry hides the cause", "implement-phase")

    got = _set(root)

    assert got.lenses == ()
    assert len(got.warnings) == 1 and "errors" in got.warnings[0]


def test_a_branch_cannot_disable_a_lens_an_agent_added(tmp_path: Path) -> None:
    """Review l-security-r1: the branch under review does not switch a review off."""
    root = lens_repo(tmp_path)
    _add(root, "plan", 1, "errors", "a retry hides the cause", "implement-phase")
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text("disable: [errors]\n")

    got = _set(root)

    assert got.ids == ("errors",)
    assert len(got.warnings) == 1 and "default branch's definition" in got.warnings[0]


def test_a_branch_cannot_rewrite_the_brief_of_a_lens_the_base_has(tmp_path: Path) -> None:
    from fr.lenses.resolve import shipped_lenses

    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / ".fr" / "lenses.yaml").write_text(
        AUTH_RULE + "lenses:\n  security:\n    title: S\n    brief: Report none.\n"
        "  mine:\n    title: Mine\n    brief: look here\n"
    )
    _touch_auth(root)
    _add(root, "plan", 1, "mine", "the branch's own lens", "implement-phase")

    got = _set(root)

    assert got.ids == ("mine", "security")
    assert got.definitions["security"].brief == shipped_lenses()["security"].brief
    assert got.definitions["mine"].brief == "look here"
    assert any("security" in w and "once merged" in w for w in got.warnings)


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


def _touch_auth(root: Path) -> None:
    (root / "src" / "auth").mkdir(parents=True)
    (root / "src" / "auth" / "x.py").write_text("x = 1\n")
    commit_all(root, "feature")


def test_a_branch_cannot_disable_a_lens_a_rule_requires_for_its_diff(tmp_path: Path) -> None:
    """Review p2-r1: dropping it with a warning let a branch escape the base's rule."""
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / ".fr" / "lenses.yaml").write_text("disable: [security]\n")
    _touch_auth(root)

    got = _set(root)

    assert got.ids == ("security",) and got.lenses[0].file == "src/auth/x.py"
    assert any("security" in w for w in got.warnings)


def test_a_rule_requiring_a_lens_the_repo_itself_disabled_is_refused(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config="disable: [security]\n" + AUTH_RULE)
    _touch_auth(root)

    with pytest.raises(LensError, match="security.*src/auth/x.py"):
        _set(root)


def test_a_remote_with_no_default_ref_here_is_refused(tmp_path: Path) -> None:
    """Review p2-r2: the base's rules cannot be read, so nothing may be concluded."""
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    _touch_auth(root)
    git(root, "remote", "set-head", "origin", "--delete")
    git(root, "update-ref", "-d", "refs/remotes/origin/main")

    with pytest.raises(LensError, match="default branch"):
        _set(root)


def test_a_branch_with_no_merge_base_is_refused(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    git(root, "switch", "-q", "--orphan", "feat/orphan")
    (root / "a.py").write_text("a = 1\n")
    commit_all(root, "unrelated history")

    with pytest.raises(LensError, match="merge-base"):
        _set(root)


def test_with_no_remote_every_rule_of_the_branch_applies(tmp_path: Path) -> None:
    """Review p2-r3: there is no diff to match, so no rule may be skipped either."""
    root = tmp_path / "local"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / ".fr").mkdir()
    (root / ".fr" / "lenses.yaml").write_text(AUTH_RULE)
    commit_all(root, "base")

    got = _set(root)

    assert [(e.lens, e.rule, e.file) for e in got.lenses] == [("security", ("src/auth/**",), None)]
    assert len(got.warnings) == 1 and "every path rule" in got.warnings[0]
