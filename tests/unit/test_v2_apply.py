import subprocess
from dataclasses import replace as dc_replace
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan_with_extra_label():
    """Helper: parse FIXTURE, attach tracking_issue, return (plan, repo, issue_number)."""
    from vk import parse

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    n = 142
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{n}"}
            )
        }
    )
    return dc_replace(plan, phases=(phase,)), repo, n


def test_apply_dry_run_calls_no_mutation_methods():
    """dry_run=True returns mutations without touching gh."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh, dry_run=True)

    assert result.dry_run is True
    assert len(result.applied) == len(d.mutations)  # all mutations "applied" in dry run
    assert gh.calls == []  # but no real calls
    assert result.failures == ()


def test_apply_creates_issue_and_returns_url():
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh)

    assert result.dry_run is False
    assert result.failures == ()
    assert 1 in result.created_issues
    assert result.created_issues[1].startswith("https://github.com/")


def test_apply_ensures_labels_with_registry_colors():
    """E2E: LabelDef objects with registry colors survive the trip through
    render → diff → apply → gh.ensure_labels. Diff-layer coverage is in
    test_v2_diff.test_repo_label_ensure_carries_registry_colors; this test
    catches a future regression where apply() or its sort/projection
    strips the colors off before handing them to the GhClient.
    """
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.labels import (
        PHASE_LABEL_COLOR,
        PLAN_LABEL_COLOR,
        SPEC_LABEL_COLOR,
        VK_READY,
        LabelDef,
    )
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    apply(d, gh)

    ensure_calls = [c for c in gh.calls if c[0] == "ensure_labels"]
    assert len(ensure_calls) == 1
    [(_, kwargs)] = ensure_calls
    passed = kwargs["labels"]

    assert passed, "apply() called ensure_labels with an empty label list"
    non_defs = [ld for ld in passed if not isinstance(ld, LabelDef)]
    assert not non_defs, f"non-LabelDef in ensure_labels call: {non_defs}"

    by_name = {ld.name: ld for ld in passed}
    assert by_name["vk-ready"].color == VK_READY.color
    assert by_name["phase:1"].color == PHASE_LABEL_COLOR
    assert by_name["plan:2026-05-09-fixture-minimal"].color == PLAN_LABEL_COLOR
    assert by_name["spec:vk-rebuild-state-machine-design"].color == SPEC_LABEL_COLOR

    # Sort key invariant: apply() sorts by name (LabelDef has no natural order).
    passed_names = [ld.name for ld in passed]
    assert passed_names == sorted(passed_names)


def test_apply_managed_labels_only_does_not_touch_operator_labels():
    """Pre-existing operator label like 'good-first-issue' must survive apply."""
    from tests.unit.fakes import FakeGhClient
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan, repo, issue_n = _dispatched_plan_with_extra_label()

    # Pre-load an Issue with operator-added "good-first-issue" + a stale managed label
    gh = FakeGhClient()
    gh.add_issue(
        repo,
        issue_n,
        state="OPEN",
        labels={"good-first-issue", "vk-ready", "phase:1"},
        # missing spec:* and plan:* taxonomy labels — apply should add them
    )

    obs = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"good-first-issue", "vk-ready", "phase:1"}),
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )
    rendered = render(plan, obs)
    d = diff(rendered, obs, plan=plan)
    apply(d, gh)

    final_labels = gh.issues[(repo, issue_n)].labels
    # The unmanaged label survives
    assert "good-first-issue" in final_labels
    # Managed labels were added (positive case)
    assert "spec:vk-rebuild-state-machine-design" in final_labels
    assert "plan:2026-05-09-fixture-minimal" in final_labels


def test_apply_idempotent_after_url_fillin_cycle():
    """Three cycles: create → fill-in URL body → no-op."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueBodyChange, RepoLabelEnsure, diff
    from vk.observe import observe
    from vk.render import render

    plan = parse(FIXTURE)
    gh = FakeGhClient()

    # Cycle 1 — observed empty, render+diff+apply creates the Issue
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    result = apply(d, gh)
    assert result.failures == ()
    new_url = result.created_issues[1]

    # Inject the now-known tracking_issue back into the plan model
    # (in production this is a write to the phase yaml; for test, mutate in memory)
    phase = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": new_url})}
    )
    plan2 = dc_replace(plan, phases=(phase,))

    # Cycle 2 — body now contains the real URL (was placeholder); diff
    # emits IssueBodyChange to bring observed up to date. This is the
    # URL-fill-in case from the diff.py docstring.
    observed2 = observe(plan2, gh)
    rendered2 = render(plan2, observed2)
    d2 = diff(rendered2, observed2, plan=plan2)
    body_changes = [m for m in d2.mutations if isinstance(m, IssueBodyChange)]
    assert len(body_changes) == 1, "Cycle 2 should fill in the URL via IssueBodyChange"
    apply(d2, gh)

    # Cycle 3 — true idempotent no-op. Only RepoLabelEnsure remains
    # (always emitted; no Issue mutations).
    observed3 = observe(plan2, gh)
    rendered3 = render(plan2, observed3)
    d3 = diff(rendered3, observed3, plan=plan2)
    non_label = [m for m in d3.mutations if not isinstance(m, RepoLabelEnsure)]
    assert non_label == [], f"Cycle 3 should be a no-op; got: {non_label}"


def test_apply_propagates_unhandled_mutation_type():
    """Programmer-error sentinel must NOT be swallowed as a failure."""
    import pytest

    from tests.unit.fakes import FakeGhClient
    from vk.apply import _UnhandledMutationError, apply
    from vk.diff import Diff

    class NovelMutation:
        """A mutation type apply() doesn't know about."""

        repo = "x/y"

    gh = FakeGhClient()
    d = Diff(mutations=(NovelMutation(),))  # type: ignore[arg-type]
    with pytest.raises(_UnhandledMutationError, match="NovelMutation"):
        apply(d, gh)


def test_fakegh_failed_mutation_not_recorded_in_calls():
    """When fail_on_mutation fires, the call is NOT recorded in .calls."""
    from tests.unit.fakes import FakeGhClient

    gh = FakeGhClient()
    gh.add_issue("o/r", 1)
    gh.fail_on_mutation = 0  # fail the first attempted mutation

    try:
        gh.edit_issue_labels("o/r", 1, add=frozenset({"x"}), remove=frozenset())
    except Exception:
        pass

    # Failed mutation NOT in .calls; attempted_mutations counts it
    assert gh.calls == []
    assert gh.attempted_mutations == 1


def test_apply_in_flight_dep_body_uses_predecessor_issue_number():
    """Two phases both being created in the same apply() run. After Phase 1's
    IssueCreate succeeds and returns URL .../issues/N, the IssueCreate that
    creates Phase 2 must use a body containing `- Blocked by #N` — the real
    Issue number, not the phase-number fallback.

    diff() ran when neither Phase had a tracking_issue, so the diff's
    initial Phase 2 IssueCreate body says `- Blocked by #1` (phase-number
    fallback). apply() must re-render that body after Phase 1's create
    lands and before Phase 2's create runs.
    """
    from pathlib import Path

    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueCreate, diff
    from vk.render import render
    from vk.states import GhState

    # Use the multi-phase fixture: Phase 2 depends on Phase 1.
    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)

    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    # Sanity: diff currently emits Phase 2 IssueCreate with the broken
    # phase-number fallback body, because no tracking_issue is set yet.
    creates_pre = [m for m in d.mutations if isinstance(m, IssueCreate)]
    phase2_pre = next(m for m in creates_pre if m.phase_number == 2)
    assert "- Blocked by #1" in phase2_pre.body, "fixture precondition"

    gh = FakeGhClient()
    # Make Phase 1's issue number ≠ 1 so the assertion isn't ambiguous with
    # the phase-number fallback `#1`.
    gh._next_issue_number[plan.meta.target_repo] = 50
    result = apply(d, gh, plan=plan)

    assert result.failures == ()
    phase1_url = result.created_issues[1]
    phase1_issue_n = int(phase1_url.rsplit("/", 1)[-1])
    assert phase1_issue_n == 50

    # The body Phase 2 was actually CREATED with (look at the create_issue
    # call recorded by the fake) must reference Phase 1's real Issue number.
    create_calls = [c for c in gh.calls if c[0] == "create_issue"]
    # Phase 1 is created first, Phase 2 second (mutations preserve order).
    phase2_create_call = next(c for c in create_calls if "Phase 2" in c[1]["title"])
    body_used = phase2_create_call[1]["body"]
    assert "- Blocked by #50" in body_used
    assert "- Blocked by #1" not in body_used


## ---------------------------------------------------------------------------
## tracking_issue writeback (CLI integration)
## ---------------------------------------------------------------------------


def _writeback_repo(tmp_path: Path, fixture_name: str = "v2_plan_minimal") -> Path:
    """Copy a fixture into a fresh git repo with a bare origin so the reachability
    gate (origin/HEAD) has a remote to resolve against.

    Also seeds a stub spec file matching the one referenced by v2_plan_minimal so
    the gate's spec-reachability check passes.
    """
    import shutil

    import yaml

    # Create bare origin so origin/HEAD resolves.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "Test"], check=True)

    plan_dir = work / "docs" / "superpowers" / "plans" / fixture_name
    plan_dir.parent.mkdir(parents=True)
    src = Path(__file__).parent / "fixtures" / fixture_name
    shutil.copytree(src, plan_dir)

    # Seed any spec file referenced by the fixture so the reachability gate passes.
    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    if meta.get("spec"):
        spec_path = work / meta["spec"]
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text("# stub spec\n")

    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "set-head", "origin", "--auto"],
        check=True,
        capture_output=True,
    )
    return plan_dir


def test_apply_command_writes_tracking_issue_back(tmp_path):
    import yaml

    from tests.unit.fakes import FakeGhClient
    from vk.commands import apply_cmd

    plan_dir = _writeback_repo(tmp_path)
    fake = FakeGhClient()

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        apply_cmd.apply_command(plan_dir=plan_dir, all_plans=False, yes=True, output_format="text")

    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"], "tracking_issue should be written"
    assert raw["phase"]["tracking_issue"].startswith("https://github.com/")


def test_apply_command_second_run_emits_no_issue_create(tmp_path, capsys):
    """Second `apply_command --yes` must NOT emit another IssueCreate."""
    import json

    from tests.unit.fakes import FakeGhClient
    from vk.commands import apply_cmd
    from vk.diff import IssueCreate

    plan_dir = _writeback_repo(tmp_path)
    fake = FakeGhClient()

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        # First run — creates the Issue and writes back the URL.
        apply_cmd.apply_command(plan_dir=plan_dir, all_plans=False, yes=True, output_format="json")
        capsys.readouterr()  # discard first-run output
        # Second run — must be a no-op for IssueCreate.
        apply_cmd.apply_command(plan_dir=plan_dir, all_plans=False, yes=True, output_format="json")
        out = capsys.readouterr().out

    parsed = json.loads(out)
    [plan_result] = parsed["plans"]
    issue_creates = [m for m in plan_result["mutations"] if m["kind"] == IssueCreate.__name__]
    assert issue_creates == [], f"second run should emit zero IssueCreate; got: {issue_creates}"


def test_apply_command_dry_run_does_not_write_back(tmp_path):
    import yaml

    from tests.unit.fakes import FakeGhClient
    from vk.commands import apply_cmd

    plan_dir = _writeback_repo(tmp_path)
    fake = FakeGhClient()

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        apply_cmd.apply_command(plan_dir=plan_dir, all_plans=False, yes=False, output_format="text")

    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"] is None


def test_apply_command_partial_failure_isolates_writeback(tmp_path):
    """Phase 1 IssueCreate succeeds, Phase 2's fails — Phase 1 writeback lands."""
    import yaml

    from tests.unit.fakes import FakeGhClient, FakeGhError
    from vk.commands import apply_cmd

    plan_dir = _writeback_repo(tmp_path, fixture_name="v2_plan_multi_phase")
    fake = FakeGhClient()

    orig_create = fake.create_issue

    def selective_create_issue(repo, *, title, body, labels):
        if "Phase 2" in title or "Second" in title:
            fake.attempted_mutations += 1
            raise FakeGhError("simulated phase-2 failure")
        return orig_create(repo, title=title, body=body, labels=labels)

    fake.create_issue = selective_create_issue  # type: ignore[method-assign]

    import pytest as _pytest
    import typer

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        with _pytest.raises(typer.Exit):
            apply_cmd.apply_command(
                plan_dir=plan_dir, all_plans=False, yes=True, output_format="text"
            )

    p1 = yaml.safe_load((plan_dir / "01.yaml").read_text())
    p2 = yaml.safe_load((plan_dir / "02.yaml").read_text())
    assert p1["phase"]["tracking_issue"], "phase 1 must have its writeback"
    assert p1["phase"]["tracking_issue"].startswith("https://github.com/")
    assert p2["phase"]["tracking_issue"] is None, "phase 2 must NOT have a writeback"


def test_apply_command_writeback_failure_surfaced_in_json_and_text(tmp_path, capsys):
    """If set_tracking_issue raises, both JSON and text output must surface it."""
    import json

    import pytest as _pytest
    import typer

    from tests.unit.fakes import FakeGhClient
    from vk import plan_ops
    from vk.commands import apply_cmd

    plan_dir = _writeback_repo(tmp_path)
    fake = FakeGhClient()

    def boom(*a, **kw):
        raise plan_ops.PlanEditError("disk full")

    # JSON run
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        mp.setattr(apply_cmd.plan_ops, "set_tracking_issue", boom)
        with _pytest.raises(typer.Exit) as ei:
            apply_cmd.apply_command(
                plan_dir=plan_dir, all_plans=False, yes=True, output_format="json"
            )
        assert ei.value.exit_code == 4
        json_out = capsys.readouterr().out

    parsed = json.loads(json_out)
    [plan_result] = parsed["plans"]
    wf = plan_result["tracking_issue_writeback_failures"]
    assert wf, "writeback failure must appear in JSON output"
    assert wf[0]["error"].startswith("disk full") or "disk full" in wf[0]["error"]
    assert "url" in wf[0]
    assert "phase_number" in wf[0]

    # Text run — fresh state (re-init fixture + fake)
    plan_dir2 = _writeback_repo(tmp_path / "second")
    fake2 = FakeGhClient()
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake2)
        mp.setattr(apply_cmd.plan_ops, "set_tracking_issue", boom)
        with _pytest.raises(typer.Exit):
            apply_cmd.apply_command(
                plan_dir=plan_dir2, all_plans=False, yes=True, output_format="text"
            )
        text_out = capsys.readouterr().out

    assert "writeback" in text_out
    assert "disk full" in text_out


def test_apply_command_all_isolates_writeback_per_plan(tmp_path, monkeypatch):
    """`--all`: one plan's writeback failure must not nullify another's success."""
    import shutil

    import pytest as _pytest
    import typer
    import yaml

    from tests.unit.fakes import FakeGhClient
    from vk import plan_ops
    from vk.commands import apply_cmd

    # Build a repo with TWO plans + a bare origin so origin/HEAD resolves.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "Test"], check=True)
    plans_dir = work / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True)
    src = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_a = plans_dir / "plan-a-first"
    plan_b = plans_dir / "plan-b-second"
    shutil.copytree(src, plan_a)
    shutil.copytree(src, plan_b)
    # Distinct plan slugs in _meta — to keep the labels distinct on gh.
    for plan_dir, slug in ((plan_a, "plan-a-first"), (plan_b, "plan-b-second")):
        raw = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
        raw["plan"] = slug
        (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    # Seed the spec so the reachability gate passes for both plans.
    sample_meta = yaml.safe_load((plan_a / "_meta.yaml").read_text())
    if sample_meta.get("spec"):
        spec_path = work / sample_meta["spec"]
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text("# stub spec\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "set-head", "origin", "--auto"],
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(work)
    fake = FakeGhClient()

    real_set = plan_ops.set_tracking_issue

    def conditional_set(plan_dir, phase_n, url):
        if "plan-b-second" in str(plan_dir):
            raise plan_ops.PlanEditError("simulated B-only writeback failure")
        return real_set(plan_dir, phase_n, url)

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(apply_cmd, "_make_gh_client", lambda: fake)
        mp.setattr(apply_cmd.plan_ops, "set_tracking_issue", conditional_set)
        with _pytest.raises(typer.Exit) as ei:
            apply_cmd.apply_command(plan_dir=None, all_plans=True, yes=True, output_format="text")
        assert ei.value.exit_code == 4

    raw_a = yaml.safe_load((plan_a / "01.yaml").read_text())
    raw_b = yaml.safe_load((plan_b / "01.yaml").read_text())
    assert raw_a["phase"]["tracking_issue"], "plan A writeback should have landed"
    assert raw_b["phase"]["tracking_issue"] is None, "plan B writeback must NOT have landed"


def test_apply_accumulates_failures_continues_past_one_bad_mutation():
    """Mutation N fails — mutation N+1 still runs; failure is recorded."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)
    assert len(d.mutations) >= 2  # need at least 2 to test "continue past failure"

    gh = FakeGhClient()
    gh.fail_on_mutation = 1  # second mutation fails

    result = apply(d, gh)

    assert len(result.failures) == 1
    # Other mutations still applied
    assert len(result.applied) == len(d.mutations) - 1


# ---------------------------------------------------------------------------
# Reachability gate tests
# ---------------------------------------------------------------------------


def _make_repo_with_origin(tmp_path):
    """Create a working tree + bare 'origin' remote, return (work, origin) paths.

    Test fixture for gate tests. Initial commit + push so origin/HEAD
    is set automatically.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    for k, v in (("user.email", "t@x"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(work), "config", k, v], check=True)
    # Initial commit so we have a HEAD to push.
    (work / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "seed"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "set-head", "origin", "--auto"],
        check=True,
        capture_output=True,
    )
    return work, origin


def test_gate_passes_when_plan_and_spec_on_origin_head(tmp_path):
    """All files committed and pushed → empty missing-paths list."""
    import shutil

    from vk.commands.apply_cmd import _check_plan_reachable_on_origin_head
    from vk.parser import parse

    work, _ = _make_repo_with_origin(tmp_path)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest_plan = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    dest_plan.parent.mkdir(parents=True)
    shutil.copytree(src_fixture, dest_plan)
    spec_dir = work / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "2026-05-06-vk-rebuild-state-machine-design.md"
    spec_path.write_text("# stub spec\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "land plan"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )

    plan = parse(dest_plan)
    missing = _check_plan_reachable_on_origin_head(plan, work)
    assert missing == [], f"expected empty, got {missing}"


def test_gate_reports_missing_plan_files(tmp_path):
    """Plan files committed locally but NOT pushed → returned in missing list."""
    import shutil

    from vk.commands.apply_cmd import _check_plan_reachable_on_origin_head
    from vk.parser import parse

    work, _ = _make_repo_with_origin(tmp_path)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest_plan = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    dest_plan.parent.mkdir(parents=True)
    shutil.copytree(src_fixture, dest_plan)
    spec_dir = work / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-05-06-vk-rebuild-state-machine-design.md").write_text("# stub\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "local only"], check=True)
    # NOTE: no push — files are local-only.

    plan = parse(dest_plan)
    missing = _check_plan_reachable_on_origin_head(plan, work)
    assert len(missing) >= 3, f"expected plan files in missing list, got {missing}"
    assert any("_meta.yaml" in str(p) for p in missing)
    assert any("_prose.md" in str(p) for p in missing)
    assert any("01.yaml" in str(p) for p in missing)


def test_gate_reports_missing_spec(tmp_path):
    """Plan committed and pushed, but spec NOT pushed → spec in missing list."""
    import shutil

    from vk.commands.apply_cmd import _check_plan_reachable_on_origin_head
    from vk.parser import parse

    work, _ = _make_repo_with_origin(tmp_path)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest_plan = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    dest_plan.parent.mkdir(parents=True)
    shutil.copytree(src_fixture, dest_plan)
    # Push the plan first.
    subprocess.run(["git", "-C", str(work), "add", "docs/superpowers/plans/"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "land plan only"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    # Create the spec locally; do NOT commit it.
    spec_dir = work / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-05-06-vk-rebuild-state-machine-design.md").write_text("# stub\n")

    plan = parse(dest_plan)
    missing = _check_plan_reachable_on_origin_head(plan, work)
    assert any("2026-05-06-vk-rebuild-state-machine-design.md" in str(p) for p in missing), (
        f"expected spec in missing list, got {missing}"
    )


def test_gate_skips_spec_check_when_meta_spec_is_none(tmp_path):
    """Plan with no spec field → gate doesn't fail on missing spec."""
    import shutil

    import yaml

    from vk.commands.apply_cmd import _check_plan_reachable_on_origin_head
    from vk.parser import parse

    work, _ = _make_repo_with_origin(tmp_path)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest_plan = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    dest_plan.parent.mkdir(parents=True)
    shutil.copytree(src_fixture, dest_plan)
    # Strip the spec field from _meta.yaml.
    meta_path = dest_plan / "_meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta.pop("spec", None)
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "plan no spec"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )

    plan = parse(dest_plan)
    missing = _check_plan_reachable_on_origin_head(plan, work)
    assert missing == [], f"expected empty (no spec to check), got {missing}"


# ---------------------------------------------------------------------------
# Gate wiring integration tests (_apply_one)
# ---------------------------------------------------------------------------


def test_apply_one_rejects_when_gate_returns_missing(tmp_path, monkeypatch):
    """vk apply --yes refuses dispatch when the gate reports missing files."""
    import shutil

    from vk.commands import apply_cmd

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = tmp_path / "v2_plan_minimal"
    shutil.copytree(src_fixture, plan_dir)

    stubbed_missing = [
        Path("docs/superpowers/plans/v2_plan_minimal/_meta.yaml"),
        Path("docs/superpowers/plans/v2_plan_minimal/01.yaml"),
    ]
    monkeypatch.setattr(
        apply_cmd,
        "_check_plan_reachable_on_origin_head",
        lambda plan, repo_root: stubbed_missing,
    )

    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: fake)

    rc, text, json_out = apply_cmd._apply_one(plan_dir, fake, yes=True)
    assert rc == 2, f"expected exit 2, got {rc}"
    assert "refuse to dispatch" in text
    assert "_meta.yaml" in text
    assert "01.yaml" in text
    assert json_out.get("unreachable_paths") == [str(p) for p in stubbed_missing]
    assert fake.calls == [], f"unexpected gh calls: {fake.calls}"


def test_apply_one_refuses_when_plan_not_in_git_checkout(tmp_path, monkeypatch):
    """No `.git/` anywhere above the plan dir → refuse early with a clear message."""
    import shutil

    from vk.commands import apply_cmd

    # NO `git init` — tmp_path is not a git checkout.
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = tmp_path / "v2_plan_minimal"
    shutil.copytree(src_fixture, plan_dir)

    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: fake)

    called = {"count": 0}

    def _spy(plan, repo_root):
        called["count"] += 1
        return []

    monkeypatch.setattr(apply_cmd, "_check_plan_reachable_on_origin_head", _spy)

    rc, text, _ = apply_cmd._apply_one(plan_dir, fake, yes=True)
    assert rc == 2, f"expected exit 2, got {rc}\noutput:\n{text}"
    assert "not in a git checkout" in text
    assert called["count"] == 0, "gate should NOT run when plan.repo_root is None"
    assert fake.calls == [], f"unexpected gh calls: {fake.calls}"


def test_apply_one_passes_through_when_gate_returns_empty(tmp_path, monkeypatch):
    """Gate passes → normal apply flow runs."""
    import shutil

    from vk.commands import apply_cmd

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = tmp_path / "v2_plan_minimal"
    shutil.copytree(src_fixture, plan_dir)

    monkeypatch.setattr(
        apply_cmd,
        "_check_plan_reachable_on_origin_head",
        lambda plan, repo_root: [],
    )

    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: fake)

    rc, text, json_out = apply_cmd._apply_one(plan_dir, fake, yes=True)
    assert rc == 0, f"expected exit 0, got {rc}\noutput:\n{text}"
    assert any(c[0] == "create_issue" for c in fake.calls), (
        f"expected an IssueCreate, got calls={fake.calls}"
    )


def test_apply_one_dry_run_skips_gate(tmp_path, monkeypatch):
    """vk apply <plan-dir> (no --yes) doesn't invoke the gate — preview unaffected."""
    import shutil

    from vk.commands import apply_cmd

    src_fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = tmp_path / "v2_plan_minimal"
    shutil.copytree(src_fixture, plan_dir)

    called = {"count": 0}

    def _spy(plan, repo_root):
        called["count"] += 1
        return []

    monkeypatch.setattr(apply_cmd, "_check_plan_reachable_on_origin_head", _spy)

    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: fake)

    rc, text, json_out = apply_cmd._apply_one(plan_dir, fake, yes=False)
    assert rc == 0
    assert called["count"] == 0, "gate should NOT be invoked on dry-run"
