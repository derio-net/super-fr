"""`scripts/ci_budget.py` — the CI time-budget watcher's core + gh adapter.

Spec 2026-09-26-ci-time-budget-design.md §3.B (state machine), §5 (error
handling), §7.2-§7.7 (Test Plan). Fixtures under tests/fixtures/ci_budget/
are captured `gh api` output (never constructed) — see the README there.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ci_budget.py"
FIXTURES = REPO / "tests" / "fixtures" / "ci_budget"

spec = importlib.util.spec_from_file_location("ci_budget", SCRIPT)
assert spec and spec.loader
ci_budget = importlib.util.module_from_spec(spec)
sys.modules["ci_budget"] = ci_budget
spec.loader.exec_module(ci_budget)


def _jobs(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())["jobs"]


def _run(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ── §7.2 wall_clock ──────────────────────────────────────────────────────


def test_wall_clock_pre_sharding_run_is_about_435s() -> None:
    jobs = _jobs("jobs_pre_sharding.json")
    assert ci_budget.wall_clock(jobs) == pytest.approx(436.0)


def test_wall_clock_sharded_run_excludes_the_skipped_job_by_conclusion() -> None:
    """r1-skipped-jobs-have-timestamps: GitHub stamps skipped jobs (run
    36247922786's `change-fragment` started 14:16:03Z, completed 14:16:02Z —
    *before* its own start), so filtering on missing timestamps would be
    wrong. `wall_clock` must filter by `conclusion == "skipped"` and get
    155s; including the skipped job's earlier `started_at` would pull the
    window back to 157s.
    """
    jobs = _jobs("jobs_sharded.json")

    assert ci_budget.wall_clock(jobs) == pytest.approx(155.0)

    # Prove the 157s figure only arises by NOT excluding the skipped job —
    # pins the exact defect the finding described, not just the fix's output.
    naive = [dict(j) for j in jobs]
    for j in naive:
        j["conclusion"] = "success" if j["conclusion"] == "skipped" else j["conclusion"]
    assert ci_budget.wall_clock(naive) == pytest.approx(157.0)


def test_wall_clock_skipped_job_is_excluded_even_with_no_null_timestamps() -> None:
    change_fragment = next(j for j in _jobs("jobs_sharded.json") if j["name"] == "change-fragment")
    assert change_fragment["conclusion"] == "skipped"
    assert change_fragment["started_at"] is not None
    assert change_fragment["completed_at"] is not None


def test_wall_clock_all_skipped_gives_none() -> None:
    jobs = [
        {
            "name": "a",
            "conclusion": "skipped",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:00:01Z",
        },
        {
            "name": "b",
            "conclusion": "skipped",
            "started_at": "2026-01-01T00:00:02Z",
            "completed_at": "2026-01-01T00:00:03Z",
        },
    ]
    assert ci_budget.wall_clock(jobs) is None


def test_slowest_job_ignores_skipped_jobs() -> None:
    name, seconds = ci_budget.slowest_job(_jobs("jobs_sharded.json"))
    assert name == "coverage" or name.startswith("test")
    assert seconds > 0


def test_measure_reduces_a_captured_run_and_its_jobs_to_a_measurement() -> None:
    run = _run("run_sharded.json")
    jobs = _jobs("jobs_sharded.json")

    measurement = ci_budget.measure("ci.yml", run, jobs, 240.0)

    assert measurement.wall_clock_seconds == pytest.approx(155.0)
    assert measurement.over_budget is False
    assert measurement.sha == run["head_sha"][:7]
    assert measurement.run_url == run["html_url"]


# ── §7.3 watch-list tripwire ─────────────────────────────────────────────


def test_watch_list_tripwire_passes_on_the_real_repo() -> None:
    errors = ci_budget.check_watch_list(
        REPO / ".github" / "workflows",
        REPO / ".github" / "workflows" / "ci-budget.yml",
        ci_budget.load_config(REPO / ".github" / "ci-budget.yaml"),
    )
    assert errors == []


def _write_workflow(path: Path, name: str, on: dict | list) -> None:
    path.write_text(yaml.safe_dump({"name": name, "on": on, "jobs": {}}))


def test_watch_list_tripwire_fails_on_an_unlisted_workflow(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_workflow(
        workflows / "ci-budget.yml",
        "ci-budget",
        {"workflow_run": {"workflows": ["CI"], "types": ["completed"]}},
    )
    _write_workflow(workflows / "ci.yml", "CI", ["push", "pull_request"])
    _write_workflow(workflows / "mystery.yml", "Mystery", ["push"])
    config: dict = {"default_seconds": 240, "workflows": {}}

    errors = ci_budget.check_watch_list(workflows, workflows / "ci-budget.yml", config)

    assert any("mystery.yml" in e for e in errors)
    assert not any("ci.yml" in e for e in errors)


def test_watch_list_tripwire_fails_on_a_stale_config_key(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_workflow(
        workflows / "ci-budget.yml",
        "ci-budget",
        {"workflow_run": {"workflows": ["CI"], "types": ["completed"]}},
    )
    _write_workflow(workflows / "ci.yml", "CI", ["push", "pull_request"])
    config = {"default_seconds": 240, "workflows": {"gone.yml": {"exclude": True}}}

    errors = ci_budget.check_watch_list(workflows, workflows / "ci-budget.yml", config)

    assert any("gone.yml" in e for e in errors)


def test_watch_list_tripwire_excluded_file_need_not_be_watched(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_workflow(
        workflows / "ci-budget.yml",
        "ci-budget",
        {"workflow_run": {"workflows": ["CI"], "types": ["completed"]}},
    )
    _write_workflow(workflows / "ci.yml", "CI", ["push", "pull_request"])
    _write_workflow(workflows / "reusable.yml", "Reusable", {"workflow_call": {}})
    config = {"default_seconds": 240, "workflows": {"reusable.yml": {"exclude": True}}}

    errors = ci_budget.check_watch_list(workflows, workflows / "ci-budget.yml", config)

    assert errors == []


# ── §7.4 counted ─────────────────────────────────────────────────────────


def _on(workflow_path: str) -> object:
    doc = yaml.safe_load((REPO / ".github" / "workflows" / workflow_path).read_text())
    return ci_budget.workflow_on(doc)


def test_counted_ci_yml_only_counts_push_on_main() -> None:
    on_value = _on("ci.yml")
    assert ci_budget.counted(on_value, {"event": "push", "head_branch": "main"}) is True
    assert ci_budget.counted(on_value, {"event": "push", "head_branch": "feat/x"}) is False
    assert ci_budget.counted(on_value, {"event": "pull_request", "head_branch": "feat/x"}) is False


def test_counted_acceptance_report_star_star_filter_only_counts_push_on_main() -> None:
    on_value = _on("acceptance-report.yml")
    assert ci_budget.counted(on_value, {"event": "push", "head_branch": "main"}) is True
    assert ci_budget.counted(on_value, {"event": "push", "head_branch": "feat/x"}) is False
    assert ci_budget.counted(on_value, {"event": "schedule", "head_branch": "main"}) is False


def test_counted_pr_spec_status_counts_every_event() -> None:
    on_value = _on("_pr_spec_status.yml")
    assert ci_budget.counted(on_value, {"event": "pull_request", "head_branch": "feat/x"}) is True


def test_counted_pinned_clis_counts_every_event() -> None:
    on_value = _on("pinned-clis.yml")
    assert ci_budget.counted(on_value, {"event": "schedule", "head_branch": "main"}) is True
    assert (
        ci_budget.counted(on_value, {"event": "workflow_dispatch", "head_branch": "main"}) is True
    )
    assert ci_budget.counted(on_value, {"event": "pull_request", "head_branch": "feat/x"}) is True


def test_counted_release_and_pages_push_branches_main_only_counts_push_on_main() -> None:
    for name in ("release.yml", "pages.yml"):
        on_value = _on(name)
        assert ci_budget.counted(on_value, {"event": "push", "head_branch": "main"}) is True
        assert (
            ci_budget.counted(on_value, {"event": "workflow_dispatch", "head_branch": "main"})
            is False
        )


def test_counted_handles_the_on_key_parsed_as_true() -> None:
    # PyYAML: `on: [push]` parses the KEY as the boolean True, not "on".
    doc = yaml.safe_load("on: [push]\nname: x\n")
    assert True in doc
    on_value = ci_budget.workflow_on(doc)
    assert ci_budget.counted(on_value, {"event": "push", "head_branch": "main"}) is True


# ── §7.5 the state machine ────────────────────────────────────────────────


def _measurement(
    *,
    file: str = "ci.yml",
    wall_clock_seconds: float | None = 300.0,
    budget_seconds: float = 240.0,
    conclusion: str = "success",
    run_id: int = 1,
    slowest: tuple[str, float] = ("test (1)", 150.0),
) -> ci_budget.Measurement:
    return ci_budget.Measurement(
        file=file,
        run_id=run_id,
        run_url=f"https://github.com/derio-net/super-fr/actions/runs/{run_id}",
        sha="abc1234",
        event="push",
        head_branch="main",
        conclusion=conclusion,
        budget_seconds=budget_seconds,
        wall_clock_seconds=wall_clock_seconds,
        slowest_job_name=slowest[0] if wall_clock_seconds is not None else None,
        slowest_job_seconds=slowest[1] if wall_clock_seconds is not None else None,
    )


def test_no_open_issue_under_budget_is_noop() -> None:
    action = ci_budget.decide(None, _measurement(wall_clock_seconds=100.0))
    assert action.kind is ci_budget.ActionKind.NOOP


def test_no_open_issue_over_budget_creates() -> None:
    action = ci_budget.decide(None, _measurement(wall_clock_seconds=300.0))
    assert action.kind is ci_budget.ActionKind.CREATE
    assert "ci.yml" in action.title
    parsed = ci_budget.parse_body(action.body)
    assert parsed.file == "ci.yml"
    assert len(parsed.rows) == 1
    assert parsed.streak == 0


def test_creating_after_a_prior_closure_links_the_previous_issue() -> None:
    action = ci_budget.decide(None, _measurement(wall_clock_seconds=300.0), regression_of=42)
    assert action.kind is ci_budget.ActionKind.CREATE
    assert "previously #42" in action.body


def test_open_issue_over_budget_appends_a_row_and_resets_the_streak() -> None:
    state = ci_budget.ParsedBody(file="ci.yml", budget_seconds=240.0, streak=2)
    action = ci_budget.decide(state, _measurement(wall_clock_seconds=300.0, run_id=5))
    assert action.kind is ci_budget.ActionKind.UPDATE
    parsed = ci_budget.parse_body(action.body)
    assert parsed.streak == 0
    assert len(parsed.rows) == 1
    assert parsed.rows[0].run_id == 5


def test_table_caps_at_ten_rows() -> None:
    rows = tuple(
        ci_budget.Row(
            run_id=i,
            run_url=f"https://x/{i}",
            sha="a" * 7,
            wall_clock_seconds=300.0,
            slowest_job_name="test",
            slowest_job_seconds=100.0,
        )
        for i in range(10)
    )
    state = ci_budget.ParsedBody(file="ci.yml", budget_seconds=240.0, rows=rows)
    action = ci_budget.decide(state, _measurement(wall_clock_seconds=301.0, run_id=999))
    parsed = ci_budget.parse_body(action.body)
    assert len(parsed.rows) == 10
    assert parsed.rows[-1].run_id == 999
    assert parsed.rows[0].run_id == 1  # the oldest (run_id=0) fell off


def test_three_green_successes_close() -> None:
    state = ci_budget.ParsedBody(file="ci.yml", budget_seconds=240.0, streak=2)
    action = ci_budget.decide(
        state, _measurement(wall_clock_seconds=100.0, conclusion="success", run_id=9)
    )
    assert action.kind is ci_budget.ActionKind.CLOSE
    assert action.close_comment
    assert "9" in action.close_comment


def test_a_failure_under_budget_does_not_advance_the_streak() -> None:
    state = ci_budget.ParsedBody(file="ci.yml", budget_seconds=240.0, streak=1)
    action = ci_budget.decide(state, _measurement(wall_clock_seconds=100.0, conclusion="failure"))
    assert action.kind is ci_budget.ActionKind.NOOP


def test_green_streak_increments_without_closing_before_three() -> None:
    state = ci_budget.ParsedBody(file="ci.yml", budget_seconds=240.0, streak=0)
    action = ci_budget.decide(
        state, _measurement(wall_clock_seconds=100.0, conclusion="success", run_id=2)
    )
    assert action.kind is ci_budget.ActionKind.UPDATE
    parsed = ci_budget.parse_body(action.body)
    assert parsed.streak == 1


def test_budget_seconds_override_applies_to_one_invocation_only() -> None:
    """The CLI's --budget-seconds is passed straight into `measure`/`decide`
    for that one call; it is never written back into `.github/ci-budget.yaml`
    or into the issue body's own budget line beyond that one row."""
    over_with_override = _measurement(wall_clock_seconds=50.0, budget_seconds=30.0)
    assert over_with_override.over_budget is True
    under_with_default = _measurement(wall_clock_seconds=50.0, budget_seconds=240.0)
    assert under_with_default.over_budget is False


def test_cancelled_and_timed_out_conclusions_are_never_measured() -> None:
    assert "cancelled" not in ci_budget.COUNTED_CONCLUSIONS
    assert "timed_out" not in ci_budget.COUNTED_CONCLUSIONS
    assert "success" in ci_budget.COUNTED_CONCLUSIONS
    assert "failure" in ci_budget.COUNTED_CONCLUSIONS


def test_per_file_override_changes_which_runs_are_over_budget() -> None:
    config = {"default_seconds": 240, "workflows": {"slow.yml": {"budget_seconds": 360}}}
    assert ci_budget.budget_for(config, "slow.yml") == 360.0
    assert ci_budget.budget_for(config, "ci.yml") == 240.0

    overridden = _measurement(
        file="slow.yml",
        wall_clock_seconds=300.0,
        budget_seconds=ci_budget.budget_for(config, "slow.yml"),
    )
    default = _measurement(
        file="ci.yml",
        wall_clock_seconds=300.0,
        budget_seconds=ci_budget.budget_for(config, "ci.yml"),
    )
    assert overridden.over_budget is False
    assert default.over_budget is True


def test_excluded_file_is_never_decided() -> None:
    config = {"default_seconds": 240, "workflows": {"fr-spec-status.yml": {"exclude": True}}}
    budget = ci_budget.budget_for(config, "fr-spec-status.yml")
    assert isinstance(budget, ci_budget.Excluded)


# ── §7.6 dedup (fake gh) ───────────────────────────────────────────────


class FakeGh:
    """A minimal in-memory GitHub, dispatched on `gh` argv shape.

    Records every argv it is called with; a test can therefore assert
    `gh search` is never invoked, and that `issue list` (never search) is
    the lookup path.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.labels: set[str] = set()
        self._next_number = 100
        self.issues: dict[int, dict] = {}  # number -> {body, state}

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        assert argv[0] != "search", (
            "must use `issue list`, never `gh search` (eventual consistency)"
        )

        if argv[:2] == ["label", "list"]:
            return json.dumps([{"name": n} for n in self.labels])
        if argv[:2] == ["label", "create"]:
            self.labels.add(argv[2])
            return ""
        if argv[:2] == ["issue", "list"]:
            state = argv[argv.index("--state") + 1]
            return json.dumps(
                [
                    {"number": n, "body": i["body"]}
                    for n, i in self.issues.items()
                    if i["state"] == state
                ]
            )
        if argv[:2] == ["issue", "create"]:
            body_path = Path(argv[argv.index("--body-file") + 1])
            number = self._next_number
            self._next_number += 1
            self.issues[number] = {"body": body_path.read_text(), "state": "open"}
            return f"https://github.com/derio-net/super-fr/issues/{number}"
        if argv[:2] == ["issue", "edit"]:
            number = int(argv[2])
            body_path = Path(argv[argv.index("--body-file") + 1])
            self.issues[number]["body"] = body_path.read_text()
            return ""
        if argv[:2] == ["issue", "close"]:
            number = int(argv[2])
            self.issues[number]["state"] = "closed"
            return ""
        raise AssertionError(f"unhandled fake gh call: {argv}")


def _run_once(gh_calls: FakeGh, measurement: ci_budget.Measurement) -> str:
    adapter = ci_budget.GhAdapter("derio-net/super-fr", run=gh_calls)
    found = adapter.find_open_issue(measurement.file)
    state = ci_budget.parse_body(found[1]) if found else None
    regression_of = (
        adapter.find_latest_closed_issue(measurement.file)
        if state is None and measurement.over_budget
        else None
    )
    action = ci_budget.decide(state, measurement, regression_of=regression_of)
    ci_budget.apply_action(adapter, action, found[0] if found else None)
    return action.kind.value


def test_two_sequential_breaches_make_one_create_then_one_edit() -> None:
    gh = FakeGh()

    kind1 = _run_once(gh, _measurement(wall_clock_seconds=300.0, run_id=1))
    assert kind1 == "create"
    creates = [c for c in gh.calls if c[:2] == ["issue", "create"]]
    edits = [c for c in gh.calls if c[:2] == ["issue", "edit"]]
    assert len(creates) == 1
    assert len(edits) == 0

    kind2 = _run_once(gh, _measurement(wall_clock_seconds=310.0, run_id=2))
    assert kind2 == "update"
    creates = [c for c in gh.calls if c[:2] == ["issue", "create"]]
    edits = [c for c in gh.calls if c[:2] == ["issue", "edit"]]
    assert len(creates) == 1
    assert len(edits) == 1

    assert len(gh.issues) == 1


def test_lookup_never_uses_gh_search() -> None:
    gh = FakeGh()
    _run_once(gh, _measurement(wall_clock_seconds=300.0))
    list_calls = [c for c in gh.calls if c[:2] == ["issue", "list"]]
    assert list_calls
    for call in list_calls:
        assert "--label" in call and call[call.index("--label") + 1] == "ci-budget"
        assert "--state" in call and "--json" in call
        assert "number,body" in call


def test_label_is_ensured_created_only_if_absent() -> None:
    gh = FakeGh()
    adapter = ci_budget.GhAdapter("derio-net/super-fr", run=gh)

    adapter.ensure_label()
    creates = [c for c in gh.calls if c[:2] == ["label", "create"]]
    assert len(creates) == 1
    assert "ci-budget" in gh.labels

    adapter.ensure_label()
    creates = [c for c in gh.calls if c[:2] == ["label", "create"]]
    assert len(creates) == 1  # still just the one


def test_hand_edited_body_with_no_streak_marker_still_dedups() -> None:
    gh = FakeGh()
    gh.issues[7] = {
        "body": "<!-- ci-budget:ci.yml -->\nSomeone deleted everything else in this body.\n",
        "state": "open",
    }

    kind = _run_once(gh, _measurement(wall_clock_seconds=100.0, conclusion="success", run_id=8))

    assert kind == "update"
    assert len(gh.issues) == 1
    parsed = ci_budget.parse_body(gh.issues[7]["body"])
    assert parsed.streak == 1  # missing marker parsed as 0, then incremented


# ── §7.7 body idempotence ─────────────────────────────────────────────


def test_render_of_parse_is_byte_identical() -> None:
    original = ci_budget.render_body(
        ci_budget.ParsedBody(
            file="ci.yml",
            budget_seconds=240.0,
            rows=(
                ci_budget.Row(
                    run_id=1,
                    run_url="https://x/1",
                    sha="abc1234",
                    wall_clock_seconds=300.0,
                    slowest_job_name="test (2)",
                    slowest_job_seconds=150.0,
                ),
                ci_budget.Row(
                    run_id=2,
                    run_url="https://x/2",
                    sha="def5678",
                    wall_clock_seconds=310.0,
                    slowest_job_name="test (1)",
                    slowest_job_seconds=160.0,
                ),
            ),
            streak=1,
            green_rows=(
                ci_budget.Row(
                    run_id=3,
                    run_url="https://x/3",
                    sha="ghi9012",
                    wall_clock_seconds=200.0,
                    slowest_job_name="test (3)",
                    slowest_job_seconds=90.0,
                ),
            ),
            regression_of=42,
        )
    )
    roundtripped = ci_budget.render_body(ci_budget.parse_body(original))
    assert roundtripped == original


def test_render_of_parse_is_byte_identical_with_no_rows_no_streak() -> None:
    original = ci_budget.render_body(
        ci_budget.ParsedBody(file="acceptance-report.yml", budget_seconds=240.0)
    )
    roundtripped = ci_budget.render_body(ci_budget.parse_body(original))
    assert roundtripped == original
