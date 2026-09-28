"""`tracking: {type: none}` switches off every issue path (spec
2026-09-28-fr-profiles-services R6, §3.E): the closeout brief files no issues,
and `fr apply --yes` / `fr triage batch dispatch --yes` refuse (exit 2) before
any forge call. `fr triage collect` reads issues and is unaffected."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import apply_cmd, triage_batch_cmd
from fr.run.closeout import closeout_brief
from fr.services import TrackerRequiredError, require_tracker
from fr.services.model import ServicesError
from typer.testing import CliRunner

from tests.unit import test_apply_cmd as apply_fixtures
from tests.unit import test_run_closeout as closeout_fixtures
from tests.unit import test_triage_batch_dispatch as dispatch_fixtures
from tests.unit.fakes import FakeGhClient

NONE = "schema_version: 2\ntracking:\n  type: none\n"
MALFORMED = "schema_version: 2\ntracking:\n  type: bogus\n"
PROFILES = Path(".devcontainer") / "fr-profiles.yaml"


def _profiles(root: Path, text: str) -> None:
    path = root / PROFILES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


# --- require_tracker -----------------------------------------------------


def test_require_tracker_refuses_none_naming_the_declaration(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    _profiles(tmp_path, NONE)
    with pytest.raises(TrackerRequiredError) as exc:
        require_tracker(tmp_path)
    assert "tracking: {type: none}" in str(exc.value)
    assert ".devcontainer/fr-profiles.yaml" in str(exc.value)


def test_require_tracker_passes_by_default(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    require_tracker(tmp_path)


def test_require_tracker_is_strict_a_malformed_block_refuses(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    _profiles(tmp_path, MALFORMED)
    with pytest.raises(ServicesError) as exc:
        require_tracker(tmp_path)
    assert not isinstance(exc.value, TrackerRequiredError)


# --- closeout ------------------------------------------------------------


def _closeout_repo(root: Path, profiles: str | None) -> None:
    closeout_fixtures._spec_file(root, with_test_plan=False)
    closeout_fixtures._plan_dir(root)
    closeout_fixtures._spec_out_of_scope_finding(root)
    if profiles is not None:
        _profiles(root, profiles)


def test_closeout_default_tracking_still_files_issues(tmp_path: Path) -> None:
    _closeout_repo(tmp_path, None)
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "file an issue" in brief
    assert "--tracked-by" in brief


def test_closeout_tracking_none_prints_no_issue_filing(tmp_path: Path) -> None:
    _closeout_repo(tmp_path, NONE)
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "file an issue" not in brief
    assert "--tracked-by" not in brief
    assert "stay recorded in the journal and PR body" in brief
    assert "fr archive" in brief


def test_closeout_malformed_tracking_is_loud_not_silent(tmp_path: Path) -> None:
    _closeout_repo(tmp_path, MALFORMED)
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "bogus" in brief and "fr-profiles.yaml" in brief


# --- fr apply ------------------------------------------------------------


def test_apply_yes_refuses_under_tracking_none_before_any_forge_call(tmp_path: Path) -> None:
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    _profiles(tmp_path, NONE)
    gh = FakeGhClient()
    rc, text, _ = apply_cmd._apply_one(plan_dir, gh, yes=True, force=True)
    assert rc == 2
    assert "tracking: {type: none}" in text
    assert gh.calls == []


def test_apply_yes_refuses_a_malformed_tracking_block(tmp_path: Path) -> None:
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    _profiles(tmp_path, MALFORMED)
    gh = FakeGhClient()
    rc, text, _ = apply_cmd._apply_one(plan_dir, gh, yes=True, force=True)
    assert rc == 2
    assert "bogus" in text
    assert gh.calls == []


def test_apply_dry_run_warns_under_tracking_none(tmp_path: Path) -> None:
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    _profiles(tmp_path, NONE)
    rc, text, json_out = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert rc == 0
    assert "tracking: {type: none}" in text
    assert any("tracking" in w["message"] for w in json_out["warnings"])


def test_apply_dry_run_default_tracking_has_no_tracking_warning(tmp_path: Path) -> None:
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    _rc, text, _ = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert "tracking: {type: none}" not in text


# --- fr triage batch dispatch --------------------------------------------


def _dispatch_yes(tmp_path: Path, checkout, *extra: str) -> tuple[int, str]:  # noqa: ANN001
    dispatch_fixtures._state(tmp_path)
    return dispatch_fixtures._dispatch(tmp_path, "lifecycle", *extra)


def test_dispatch_yes_refuses_under_tracking_none_before_any_forge_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = FakeGhClient()
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: gh)
    runner = dispatch_fixtures.FakeRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: runner)
    clone = tmp_path / "clone"
    _git_repo(clone)
    _profiles(clone, NONE)
    monkeypatch.setattr(
        triage_batch_cmd, "make_checkout", lambda path: dispatch_fixtures.FakeCheckout(clone)
    )
    code, out = _dispatch_yes(tmp_path, None, "--yes")
    assert code == 2, out
    assert "tracking: {type: none}" in out
    assert gh.calls == []
    assert runner.dispatched == []


def test_dispatch_dry_run_is_not_refused_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = FakeGhClient()
    for n in (*dispatch_fixtures.MEMBERS, 420):
        gh.add_issue(dispatch_fixtures.REPO, n)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: gh)
    monkeypatch.setattr(
        triage_batch_cmd, "load_runner", lambda name: dispatch_fixtures.FakeRunner()
    )
    clone = tmp_path / "clone"
    _git_repo(clone)
    _profiles(clone, NONE)
    monkeypatch.setattr(
        triage_batch_cmd, "make_checkout", lambda path: dispatch_fixtures.FakeCheckout(clone)
    )
    code, out = _dispatch_yes(tmp_path, None)
    assert code == 0, out
    assert "tracking: {type: none}" in out  # warned


def test_triage_collect_is_unaffected_by_tracking_none() -> None:
    import inspect

    from fr.commands import triage_cmd

    assert "require_tracker" not in inspect.getsource(triage_cmd)


def test_the_app_still_loads() -> None:
    assert CliRunner().invoke(app, ["--help"]).exit_code == 0
