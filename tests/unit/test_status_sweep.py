"""`fr status` with no PLAN_DIR — the read-only repo-wide sweep (#334, #526).

Spec `2026-09-23-archive-merge-evidence-design.md` §3.B, Test Plan §5 item 4.

The sweep reports four buckets from `fr.archive.merge_evidence` — the one
definition of "merged" (every agentic phase complete on the default branch's
remote-tracking ref) — and never calls a locally complete plan merged. It
stays gh-free and exit-0. Complements test_status_cmd.py (the per-plan report).

Every repo is a real temp git repo whose remote is a FILE PATH, and
`fr.archive._fetch` is monkeypatched, so nothing touches a network.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fr.archive as archive_mod
import pytest
import yaml
from fr.cli import app
from fr.commands import status_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_merge_evidence import (
    PLANS_REL,
    _add_remote,
    _commit,
    _git,
    _init,
    _publish,
    _write_plan,
    stub_fetch,
)

MERGED = "2026-05-01-merged"
MANUAL_OPEN = "2026-05-02-manual-open"
UNMERGED = "2026-05-03-unmerged"
WIP = "2026-05-04-wip"
GROWN = "2026-05-05-grown"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Cut off operator git config and replace the network fetch with a
    recorder (the sweep must fetch: decision d3-evidence)."""
    return stub_fetch(monkeypatch)


def _four_bucket_repo(tmp_path: Path) -> Path:
    """One plan per bucket, plus the f-p2-local-phases case (GROWN)."""
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, MERGED, [("agentic", True), ("manual", True)])
    _write_plan(repo, MANUAL_OPEN, [("agentic", True), ("agentic", True), ("manual", False)])
    _write_plan(repo, WIP, [("agentic", False)])
    _write_plan(repo, GROWN, [("agentic", True)])
    _commit(repo, "merged plans")
    _publish(repo)
    # On the branch only: a finished plan the PR has not delivered yet, and a
    # phase 2 added to GROWN after its phase 1 merged.
    _write_plan(repo, UNMERGED, [("agentic", True)])
    _write_plan(repo, GROWN, [("agentic", True), ("agentic", True)])
    _commit(repo, "branch work")
    return repo


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


def _section(output: str, heading: str) -> list[str]:
    """The lines of the blank-line-delimited block whose first line starts
    with ``heading`` (heading included); [] when there is none."""
    for block in output.split("\n\n"):
        lines = block.strip("\n").splitlines()
        if lines and lines[0].startswith(heading):
            return lines
    return []


def _sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "--short", "origin/main")


# --- text: four buckets ------------------------------------------------------


def test_archivable_heading_names_the_ref_and_sha_with_a_per_plan_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    block = _section(result.output, "merged but not archived")
    assert block, result.output
    assert f"origin/main @ {_sha(repo)}" in block[0]
    assert "(1)" in block[0]
    assert any(line.strip() == MERGED for line in block)
    assert any(line.strip() == f"fr archive {PLANS_REL}/{MERGED}" for line in block)


def test_archive_all_is_never_suggested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    assert "--all" not in result.output


def test_only_archivable_plans_get_an_archive_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    commands = [ln.strip() for ln in result.output.splitlines() if "fr archive" in ln]
    assert commands == [f"fr archive {PLANS_REL}/{MERGED}"]


def test_merged_plan_with_open_manual_phase_names_the_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    block = _section(result.output, "merged, manual phases still open")
    assert block, result.output
    assert "(1)" in block[0]
    assert any(MANUAL_OPEN in ln and "(phase 3)" in ln for ln in block[1:])


def test_locally_complete_unlanded_plans_wait_for_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    block = _section(result.output, "complete locally, not yet on origin/main")
    assert block, result.output
    assert "waiting for merge" in block[0]
    assert sorted(ln.strip() for ln in block[1:]) == [UNMERGED, GROWN]


def test_a_phase_added_locally_after_merge_keeps_the_plan_unmerged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """f-p2-local-phases: GROWN's phase 1 is on the ref (so the ref's copy is
    agentic-landed), but its phase 2 exists only in the working tree."""
    repo = _four_bucket_repo(tmp_path)
    payload = json.loads(_invoke(monkeypatch, repo, ["status", "--format", "json"]).output)
    assert GROWN not in payload["archivable"]
    assert GROWN not in payload["merged_manual_open"]
    assert GROWN in payload["complete_unmerged"]


def test_in_progress_plans_are_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    block = _section(result.output, "in progress")
    assert [ln.strip() for ln in block[1:]] == [WIP]


def test_the_sweep_fetches_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _hermetic: list[str]
) -> None:
    repo = _four_bucket_repo(tmp_path)
    assert _invoke(monkeypatch, repo, ["status"]).exit_code == 0
    assert _hermetic == ["origin"]


# --- degraded evidence -------------------------------------------------------


def test_unknown_ref_lists_complete_plans_as_merge_state_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init(tmp_path / "r")  # no remote at all
    _write_plan(repo, MERGED, [("agentic", True)])
    _write_plan(repo, WIP, [("agentic", False)])
    _commit(repo, "plans on a local main only")
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    block = _section(result.output, "merge state unknown")
    assert block, result.output
    assert "no git remote" in block[0]
    assert "git fetch" in block[0] and "git remote set-head origin -a" in block[0]
    assert [ln.strip() for ln in block[1:]] == [MERGED]
    assert "merged but not archived" not in result.output
    assert "fr archive" not in result.output


def test_unknown_ref_json_has_null_default_ref_and_nothing_archivable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init(tmp_path / "r")
    _write_plan(repo, MERGED, [("agentic", True)])
    _commit(repo, "plan")
    payload = json.loads(_invoke(monkeypatch, repo, ["status", "--format", "json"]).output)
    assert payload["default_ref"] is None
    assert payload["ref_error"]
    assert payload["archivable"] == []
    assert payload["complete_unmerged"] == [MERGED]


def test_a_failed_fetch_is_reported_and_the_local_ref_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _four_bucket_repo(tmp_path)

    def boom(root: Path, remote: str) -> None:
        raise subprocess.CalledProcessError(128, ["git", "fetch"], stderr="fatal: offline")

    monkeypatch.setattr(archive_mod, "_fetch", boom)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    assert "fetch failed:" in result.output
    assert "using the local origin/main ref" in result.output
    # The stale local ref is still evidence.
    assert f"fr archive {PLANS_REL}/{MERGED}" in result.output
    payload = json.loads(_invoke(monkeypatch, repo, ["status", "--format", "json"]).output)
    assert payload["default_ref"]["fetched"] is False
    assert "offline" in payload["default_ref"]["fetch_error"]


def test_a_plan_unparseable_on_the_ref_is_noted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    plan_dir = _write_plan(repo, "2026-05-06-old", [("agentic", True)])
    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["a_key_no_fr_knows"] = 1  # extra="forbid": the current parser rejects it
    (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    _commit(repo, "an older-schema plan")
    _publish(repo)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    block = _section(result.output, "could not parse on origin/main")
    assert block, result.output
    assert [ln.strip() for ln in block[1:]] == ["2026-05-06-old"]
    payload = json.loads(_invoke(monkeypatch, repo, ["status", "--format", "json"]).output)
    assert payload["unparsed_on_ref"] == ["2026-05-06-old"]


# --- JSON ---------------------------------------------------------------------


def test_sweep_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["archivable"] == [MERGED]
    assert payload["merged_manual_open"] == [MANUAL_OPEN]
    assert payload["complete_unmerged"] == [UNMERGED, GROWN]
    assert payload["in_progress"] == [WIP]
    assert payload["default_ref"] == {
        "ref": "origin/main",
        "sha": _sha(repo),
        "fetched": True,
        "fetch_error": None,
    }
    assert payload["ref_error"] is None
    assert payload["unparsed_on_ref"] == []


def test_sweep_clean_repo_no_archivable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, WIP, [("agentic", False)])
    _commit(repo, "wip")
    _publish(repo)
    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["archivable"] == []


# --- invariants ------------------------------------------------------------------


def test_sweep_never_calls_gh_mutations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sweep stays allowlist-safe: gh-free, no mutation attempts — over a
    repo exercising every bucket, so every rendering path runs."""
    repo = _four_bucket_repo(tmp_path)
    gh = FakeGhClient()
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    for argv in (["status"], ["status", "--format", "json"]):
        result = CliRunner().invoke(app, argv)
        assert result.exit_code == 0, result.output
    assert gh.attempted_mutations == 0


def test_single_plan_path_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing a PLAN_DIR still runs the per-plan report (regression guard)."""
    repo = _four_bucket_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status", f"{PLANS_REL}/{MERGED}"])
    assert result.exit_code == 0, result.output
    assert "phase 1" in result.output
