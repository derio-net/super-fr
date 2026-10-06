"""`archive_twin` covers journals, not just specs (2026-09-28-closeout-always
spec §F). ``ARCHIVE_TWIN_DIRS`` becomes a tuple of ``(live, done)`` pairs:
specs (today's), plus journals/{specs,plans,debug} against their
``implemented/journals/…`` twins — so a matrix ref to a journal resolves
before and after the archive sweep moves it, exactly as a spec ref already
does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import archive_twin
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def run_check(root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "check"])


# ── archive_twin: every journal scope, both directions ──────────────────────


@pytest.mark.parametrize("scope_dir", ["specs", "plans", "debug"])
def test_archive_twin_journal_live_to_done(scope_dir: str) -> None:
    live = f"docs/superpowers/journals/{scope_dir}/x.md"
    done = f"docs/superpowers/implemented/journals/{scope_dir}/x.md"
    assert archive_twin(live) == done


@pytest.mark.parametrize("scope_dir", ["specs", "plans", "debug"])
def test_archive_twin_journal_done_to_live(scope_dir: str) -> None:
    live = f"docs/superpowers/journals/{scope_dir}/x.md"
    done = f"docs/superpowers/implemented/journals/{scope_dir}/x.md"
    assert archive_twin(done) == live


def test_archive_twin_specs_still_work_alongside_journals() -> None:
    """The existing spec pair is unaffected by adding the journal pairs."""
    assert archive_twin("docs/superpowers/specs/x.md") == "docs/superpowers/implemented/specs/x.md"
    assert archive_twin("docs/superpowers/implemented/specs/x.md") == "docs/superpowers/specs/x.md"


def test_archive_twin_unrelated_path_still_none() -> None:
    assert archive_twin("scripts/x.sh") is None


def test_archive_twin_no_cross_scope_match() -> None:
    """A plans-journal path is never mistaken for a debug or specs one."""
    assert archive_twin("docs/superpowers/journals/plans/x.md") != (
        "docs/superpowers/implemented/journals/debug/x.md"
    )


# ── end-to-end: `fr acceptance check` survives a debug-journal archive ──────


def test_check_survives_debug_journal_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matrix row citing a debug journal resolves both before and after the
    journal moves to implemented/journals/debug/ (mirroring the spec-archive
    guarantee `test_archived_ref_downgrades_to_warning` already pins)."""
    root = make_repo(
        tmp_path,
        row() + row(id="r2", origin='"own:docs/superpowers/journals/debug/x.md"'),
    )
    journal = root / "docs" / "superpowers" / "journals" / "debug" / "x.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("# debug journal\n")

    result = run_check(root, monkeypatch)
    assert result.exit_code == 0, result.output

    dest = root / "docs" / "superpowers" / "implemented" / "journals" / "debug" / "x.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    journal.rename(dest)

    result = run_check(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "names an archived path" in " ".join(result.output.split())


# ── R7: the reworded warning, and plan-dir refs stay errors ─────────────────


def test_twin_warning_says_the_ref_survived_an_archive_fr_did_not_perform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(origin='"own:docs/superpowers/specs/s.md"'))
    (root / "docs/superpowers/specs/s.md").rename(
        root / "docs/superpowers/implemented/specs/s.md"
    )
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "names an archived path" in flat
    assert "docs/superpowers/implemented/specs/s.md" in flat
    assert "survived an archive fr did not perform; retarget it" in flat


def test_a_stale_plan_dir_ref_is_still_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(origin='"own:docs/superpowers/plans/p1/_meta.yaml"'))
    done = root / "docs/superpowers/implemented/plans/p1"
    done.mkdir(parents=True)
    (done / "_meta.yaml").write_text("x: 1\n")
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1, result.output
    assert "ref does not resolve" in result.output
