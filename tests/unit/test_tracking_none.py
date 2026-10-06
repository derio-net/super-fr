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
    assert "fr archive --issues" in brief
    assert "--issues spec/" in brief


def test_closeout_tracking_none_prints_no_issue_filing(tmp_path: Path) -> None:
    _closeout_repo(tmp_path, NONE)
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "fr archive --issues" not in brief
    assert "--issues spec/" not in brief
    assert "stay recorded in the journal and PR body; no tracker is configured" in brief
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


def test_a_cross_repo_plan_is_gated_by_the_plan_repos_tracking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh#804 (operator decision, 2026-10-02): for a plan whose `target_repo`
    is another repo, the PLAN repo's `tracking` governs `fr apply --yes`. fr
    has no checkout of the target to read a declaration from, and the plan
    repo is the one that declared where its work is tracked."""
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    meta = (plan_dir / "_meta.yaml").read_text()
    assert "target_repo: derio-net/superpowers-for-vk" in meta  # not this repo
    _profiles(tmp_path, NONE)
    seen: list[Path] = []
    real = apply_cmd.require_tracker

    def _spy(root: Path) -> None:
        seen.append(root)
        real(root)

    monkeypatch.setattr(apply_cmd, "require_tracker", _spy)
    gh = FakeGhClient()
    rc, text, _ = apply_cmd._apply_one(plan_dir, gh, yes=True, force=True)
    assert seen == [tmp_path.resolve()]
    assert rc == 2
    assert "tracking: {type: none}" in text
    assert gh.calls == []


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


def test_triage_collect_is_unaffected_by_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_triage_cli as cli_fixtures

    repo = tmp_path / "repo"
    _git_repo(repo)
    _profiles(repo, NONE)
    monkeypatch.chdir(repo)
    state = tmp_path / "state"
    result = cli_fixtures._run(
        monkeypatch, cli_fixtures._Forge(), "--repo", "derio-net/super-fr", "--dir", str(state)
    )
    assert result.exit_code == 0, result.output
    assert (state / "facts.json").exists()


# --- the other tracker writers: batch cancel, fr undispatch (gh#803) ------
#
# R6 named only apply and dispatch; every verb that writes a label, comment or
# state to the tracker is gated the same way. `batch merge` is not here: it
# merges PRs (the forge) and writes nothing to an issue.


def _cancel_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profiles: str | None):
    from tests.unit import test_triage_batch_verbs as verbs

    gh = FakeGhClient()
    gh.add_issue(verbs.REPO, 577, labels={"fr:in-progress"})
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: gh)
    clone = tmp_path / "clone"
    _git_repo(clone)
    if profiles is not None:
        _profiles(clone, profiles)
    monkeypatch.setattr(
        triage_batch_cmd, "make_checkout", lambda path: dispatch_fixtures.FakeCheckout(clone)
    )
    state = tmp_path / "state"
    state.mkdir()
    verbs._with(
        state,
        {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [verbs._DISPATCH]},
    )
    return gh, state


def test_cancel_yes_refuses_under_tracking_none_before_any_forge_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_triage_batch_verbs as verbs

    gh, state = _cancel_env(tmp_path, monkeypatch, NONE)
    before = (state / "judgements.yaml").read_text("utf-8")
    code, out = verbs._run(state, "cancel", "lifecycle", "--yes")
    assert code == 2, out
    assert "tracking: {type: none}" in out
    assert gh.calls == []
    assert (state / "judgements.yaml").read_text("utf-8") == before


def test_cancel_dry_run_warns_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_triage_batch_verbs as verbs

    gh, state = _cancel_env(tmp_path, monkeypatch, NONE)
    code, out = verbs._run(state, "cancel", "lifecycle")
    assert code == 0, out
    assert "tracking: {type: none}" in out


def test_cancel_yes_still_acts_under_the_default_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_triage_batch_verbs as verbs

    gh, state = _cancel_env(tmp_path, monkeypatch, None)
    code, out = verbs._run(state, "cancel", "lifecycle", "--yes")
    assert code == 0, out
    assert "fr:in-progress" not in gh.issues[(verbs.REPO, 577)].labels


def _undispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str):
    from tests.unit import test_undispatch_cmd as undispatch_fixtures

    plan_dir = undispatch_fixtures._dispatched_plan_repo(tmp_path)
    _profiles(tmp_path, NONE)
    gh = FakeGhClient()
    gh.add_issue(undispatch_fixtures.REPO, 7, state="OPEN")
    result = undispatch_fixtures._invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), *extra],
    )
    return result, gh, plan_dir


def test_undispatch_yes_refuses_under_tracking_none_before_any_forge_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, gh, plan_dir = _undispatch(tmp_path, monkeypatch, "--yes")
    assert result.exit_code == 2, result.output
    assert "tracking: {type: none}" in result.output
    assert gh.calls == []
    assert "tracking_issue: https" in (plan_dir / "01.yaml").read_text()


def test_undispatch_dry_run_warns_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, gh, _ = _undispatch(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "tracking: {type: none}" in result.output
    assert gh.attempted_mutations == 0


# --- review fixes ---------------------------------------------------------


def _dispatch_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profiles: str | None):
    gh = FakeGhClient()
    for n in (*dispatch_fixtures.MEMBERS, 420):
        gh.add_issue(dispatch_fixtures.REPO, n)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: gh)
    monkeypatch.setattr(
        triage_batch_cmd, "load_runner", lambda name: dispatch_fixtures.FakeRunner()
    )
    clone = tmp_path / "clone"
    _git_repo(clone)
    if profiles is not None:
        _profiles(clone, profiles)
    fake = dispatch_fixtures.FakeCheckout(clone)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    dispatch_fixtures._state(tmp_path)
    return gh, fake


def test_f1_repair_yes_under_tracking_none_refuses_with_no_forge_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh, _ = _dispatch_env(tmp_path, monkeypatch, NONE)
    code, out = dispatch_fixtures._dispatch(tmp_path, "lifecycle", "--repair", "--yes")
    assert code == 2, out
    assert "tracking: {type: none}" in out
    assert gh.calls == []


def test_f1_repair_yes_with_no_clone_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.model import TriageError

    gh, _ = _dispatch_env(tmp_path, monkeypatch, None)

    def _no_clone(path):  # noqa: ANN001, ANN202
        raise TriageError("no clone here")

    monkeypatch.setattr(triage_batch_cmd, "make_checkout", _no_clone)
    code, out = dispatch_fixtures._dispatch(tmp_path, "lifecycle", "--repair", "--yes")
    assert code == 2, out
    assert "no clone here" in out
    assert gh.calls == []


def test_f1_repair_yes_in_a_clone_of_another_repo_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh, fake = _dispatch_env(tmp_path, monkeypatch, None)
    fake.origin = "someone/else"
    code, out = dispatch_fixtures._dispatch(tmp_path, "lifecycle", "--repair", "--yes")
    assert code == 2, out
    assert "someone/else" in out
    assert gh.calls == []


def test_no_plan_under_tracking_none_files_nothing_but_still_closes_out(tmp_path: Path) -> None:
    """With no plan, tracking none removes only the issue-filing lines. The
    housekeeping block stays: close-out is an always condition keyed on the
    branch (#733/#790), which superseded this phase's earlier "no block when
    there is nothing to commit" rule."""
    closeout_fixtures._spec_file(tmp_path, with_test_plan=False)
    closeout_fixtures._spec_out_of_scope_finding(tmp_path)
    _profiles(tmp_path, NONE)
    state = closeout_fixtures._state()
    del state.steps["plan"]
    brief = closeout_brief(tmp_path, state)
    assert "stay recorded in the journal and PR body; no tracker is configured" in brief
    assert "fr archive --issues" not in brief
    assert "--issues spec/" not in brief
    assert f"fr isolation up --branch chore/closeout-{state.run}" in brief


def test_f3_a_deferred_ci_does_not_refuse_apply_when_tracking_is_valid(tmp_path: Path) -> None:
    plan_dir = apply_fixtures._ticked_plan_repo(tmp_path)
    _profiles(tmp_path, "schema_version: 2\nci:\n  type: jenkins\n  host: ci.example.com\n")
    require_tracker(tmp_path)
    rc, text, _ = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=True)
    assert "jenkins" not in text


def test_f3_a_deferred_ci_does_not_make_closeout_blame_tracking(tmp_path: Path) -> None:
    _closeout_repo(tmp_path, "schema_version: 2\nci:\n  type: jenkins\n  host: ci.example.com\n")
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "WARNING" not in brief
    assert "fr archive --issues" in brief


def test_f5_malformed_warning_only_when_out_of_scope_findings_exist(tmp_path: Path) -> None:
    closeout_fixtures._spec_file(tmp_path, with_test_plan=False)
    closeout_fixtures._plan_dir(tmp_path)
    _profiles(tmp_path, MALFORMED)
    brief = closeout_brief(tmp_path, closeout_fixtures._state())
    assert "WARNING" not in brief


def test_the_app_still_loads() -> None:
    assert CliRunner().invoke(app, ["--help"]).exit_code == 0
