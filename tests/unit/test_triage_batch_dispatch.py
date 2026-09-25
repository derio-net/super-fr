"""`fr triage batch dispatch` (spec 2026-09-25-triage-batches §3.C, §3.E, §3.I;
Test Plan 4, 5, 7, 8, 17).

Nothing here reaches a real forge, a real runner or a real clone: the adapter
is `FakeGhClient` (through `triage_batch_cmd.make_client`), the runner is
`FakeRunner` (through `triage_batch_cmd.load_runner`) and the local checkout is
`FakeCheckout` (through `triage_batch_cmd.make_checkout`).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage.batch_dispatch import render_brief
from fr.triage.model import (
    DispatchEvent,
    Facts,
    Issue,
    TriageConfig,
    load_judgements,
)
from fr_dispatch.work_item import WorkItem, run_item_id
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"
ITEM = f"{REPO}/run/batch-lifecycle"
MEMBERS = (577, 575)

JUDGEMENTS = """\
schema: 2
ranked_at: 2026-09-25
tiers:
  - {n: 1, title: Now}
issues:
  super-fr#577: {tier: 1, detail: "rebuild routes through down", note: "seen twice"}
  super-fr#575: {tier: 1, detail: "stop re-uses teardown"}
  super-fr#420: {tier: 1, detail: "executor guard"}
batches:
  - id: lifecycle
    title: Separate container lifecycle
    ids: ["super-fr#577", "super-fr#575"]
    rationale: Rebuild and stop both route through down.
    bump: minor
    launch: {runner: fake, harness: claude, model: claude-opus-5-5}
"""

PYPROJECT = '[project]\nname = "super-fr"\nversion = "4.21.1"\n'
VERSION_CONFIG = {
    "version": {
        "source": {"file": "pyproject.toml", "key": "project.version"},
        "files": ["pyproject.toml", "uv.lock"],
        "set": "python scripts/bump.py {version}",
    }
}


def _issue(number: int, **kw: Any) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=kw.pop("title", f"issue {number}"),
        state=kw.pop("state", "open"),
        url=f"https://github.com/{REPO}/issues/{number}",
        **kw,
    )


def _facts(config: dict[str, Any] | None = None, **kw: Any) -> Facts:
    return Facts(
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at=kw.pop("collected_at", "2026-09-26T12:00:00+00:00"),
        repos=[REPO],
        issues=kw.pop("issues", [_issue(577), _issue(575), _issue(420)]),
        config={REPO: TriageConfig.model_validate(config)} if config is not None else {},
        **kw,
    )


def _state(tmp_path: Path, facts: Facts | None = None, judgements: str = JUDGEMENTS) -> Path:
    (tmp_path / "judgements.yaml").write_text(judgements, encoding="utf-8")
    (tmp_path / "facts.json").write_text(json.dumps((facts or _facts()).to_json()), "utf-8")
    return tmp_path


class FakeRunner:
    """A run-unit runner that records every protocol call, in order."""

    name = "fake"
    capabilities = frozenset({"git"})

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.dispatched: list[WorkItem] = []
        self.accepts = True
        self.refusal: str | None = None
        self.live: set[str] = set()
        self.fail: Exception | None = None
        self.handle: str | None = "w2:p1K"

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        self.calls.append("preflight")
        return self.refusal

    def refresh(self) -> None:
        self.calls.append("refresh")

    def slot_budget(self) -> int:
        return 1

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        self.calls.append("existing_dispatches")
        return {i.id for i in items} & self.live

    def can_dispatch(self, item: WorkItem) -> bool:
        self.calls.append("can_dispatch")
        return self.accepts

    def dispatch(self, item: WorkItem) -> str | None:
        self.calls.append("dispatch")
        if self.fail is not None:
            raise self.fail
        self.dispatched.append(item)
        return self.handle


class FakeCheckout:
    """The local clone, as `fr.triage.gitseam.Checkout` presents it."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.origin = REPO
        self.default = "main"
        self.files: dict[tuple[str, str], str] = {("origin/main", "pyproject.toml"): PYPROJECT}
        self.config_changed_at: datetime | None = None
        self.remote_branches: set[str] = set()
        self.fetched = 0

    def origin_repo(self) -> str | None:
        return self.origin

    def default_branch(self) -> str:
        return self.default

    def fetch(self) -> None:
        self.fetched += 1

    def show(self, ref: str, file: str) -> str | None:
        return self.files.get((ref, file))

    def last_change(self, ref: str, file: str) -> datetime | None:
        return self.config_changed_at

    def remote_branch_exists(self, branch: str) -> bool:
        return branch in self.remote_branches


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGhClient:
    client = FakeGhClient()
    for n in (*MEMBERS, 420):
        client.add_issue(REPO, n)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    return client


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> FakeRunner:
    fake = FakeRunner()
    loaded: list[str] = []

    def _load(name: str) -> FakeRunner:
        loaded.append(name)
        return fake

    monkeypatch.setattr(triage_batch_cmd, "load_runner", _load)
    fake.loaded = loaded  # type: ignore[attr-defined]
    return fake


@pytest.fixture
def checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeCheckout:
    fake = FakeCheckout(tmp_path / "clone")
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    return fake


def _dispatch(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app,
        ["triage", "batch", "dispatch", *args, "--repo", REPO, "--dir", str(tmp_path)],
    )
    return result.exit_code, result.output


def _mutations(client: FakeGhClient) -> list[str]:
    return [name for name, _ in client.calls if name != "list_issue_comments"]


# ------------------------------------------------------------ checkout (§3.I)


def test_a_checkout_of_another_repo_is_refused_naming_both(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    checkout.origin = "someone/else"
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 2
    assert "someone/else" in out and REPO in out
    assert runner.dispatched == []


def test_launch_defaults_resolve_from_the_collected_config_at_dispatch(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    judgements = JUDGEMENTS.replace(
        "    launch: {runner: fake, harness: claude, model: claude-opus-5-5}\n", ""
    )
    config = {"defaults": {"launch": {"runner": "fake", "harness": "claude", "model": "m-9"}}}
    _state(tmp_path, _facts(config=config), judgements)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 0, out
    assert "runner: fake" in out and "harness: claude" in out and "model: m-9" in out
    assert runner.loaded == ["fake"]  # type: ignore[attr-defined]


def test_to_overrides_the_launch_runner(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle", "--to", "other")
    assert code == 0, out
    assert runner.loaded == ["other"]  # type: ignore[attr-defined]


def test_no_launch_anywhere_is_refused(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    judgements = JUDGEMENTS.replace(
        "    launch: {runner: fake, harness: claude, model: claude-opus-5-5}\n", ""
    )
    _state(tmp_path, judgements=judgements)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 2
    assert "defaults.launch" in out


def test_a_config_older_than_the_checkouts_last_change_is_refused(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(collected_at="2026-09-26T12:00:00+00:00"))
    checkout.config_changed_at = datetime(2026, 9, 26, 13, 0, tzinfo=UTC)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 2
    assert "re-collect" in out or "collect" in out
    assert runner.dispatched == []


def test_a_config_collected_after_the_last_change_is_used(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(collected_at="2026-09-26T12:00:00+00:00"))
    checkout.config_changed_at = datetime(2026, 9, 26, 11, 0, tzinfo=UTC)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 0, out


def test_the_missing_dispatch_package_is_named_like_apply(
    tmp_path: Path, gh: FakeGhClient, checkout: FakeCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a: None if name == "fr_dispatch" else real(name, *a),
    )
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 2
    assert "uv tool install --with fr-dispatch fr" in out


def test_a_runner_without_from_env_is_refused(
    tmp_path: Path, gh: FakeGhClient, checkout: FakeCheckout
) -> None:
    """The real loader: `vk` is registered but cannot be built outside its bridge."""
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle", "--to", "vk")
    assert code == 2
    assert "cannot be constructed outside its own bridge" in out


# ------------------------------------------------------------- brief (§3.C.3)


def _brief(reserved: str | None = "4.22.0", judgements: str = JUDGEMENTS) -> str:
    import yaml
    from fr.triage.model import Judgements

    j = Judgements.model_validate(yaml.safe_load(judgements))
    return render_brief(
        j.batches[0],
        j,
        _facts(),
        repo=REPO,
        closing_refs=[f"Closes {REPO}#{n}" for n in MEMBERS],
        reserved_version=reserved,
        model="claude-opus-5-5",
    )


def test_identical_judgements_render_byte_identical_briefs() -> None:
    assert _brief() == _brief()


def test_the_brief_carries_every_rule_the_run_depends_on() -> None:
    brief = _brief()
    assert brief.startswith("/fr-goal Separate container lifecycle\n")
    for n in MEMBERS:
        assert f"Closes {REPO}#{n}" in brief
        assert f"issue {n}" in brief  # the member's title from facts
    assert "rebuild routes through down" in brief and "seen twice" in brief
    assert "Rebuild and stop both route through down." in brief
    assert "feat/batch-lifecycle" in brief
    assert "Bump the version to `4.22.0`" in brief
    assert "Use `claude-opus-5-5` for every subagent and every model tier" in brief
    assert "Do not name any member issue as a phase `tracking_issue`" in brief
    assert "draft PR" in brief


def test_the_brief_omits_the_bump_line_without_a_reservation() -> None:
    assert "Bump the version" not in _brief(reserved=None)


def test_the_brief_is_printed_with_the_reserved_version(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(config=VERSION_CONFIG))
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 0, out
    assert "Bump the version to `4.22.0`" in out
    assert "reserved version: 4.22.0" in out
    assert f"Closes {REPO}#577" in out


# ------------------------------------------------------------ WorkItem (§3.C.4)


def test_the_work_item_is_a_run_of_fr_goal_with_the_issues_in_its_payload(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(config=VERSION_CONFIG))
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    (item,) = runner.dispatched
    assert item.id == run_item_id(REPO, "batch-lifecycle") == ITEM
    assert item.unit == "run"
    assert item.repo == REPO
    assert item.workflow == "fr-goal"
    assert item.parent is None
    assert item.inputs == ()
    assert item.tracking is None
    payload = dict(item.payload)
    assert payload["issues"] == ["super-fr#577", "super-fr#575"]
    assert payload["harness"] == "claude"
    assert payload["model"] == "claude-opus-5-5"
    assert payload["branch"] == "feat/batch-lifecycle"
    assert payload["reserved_version"] == "4.22.0"
    assert payload["checkout"] == str(checkout.path)
    assert payload["brief"].startswith("/fr-goal ")


# ---------------------------------------------------- without --yes (§3.C.5)


def test_dispatch_without_yes_writes_nothing(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(config=VERSION_CONFIG))
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 0, out
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert _mutations(gh) == []
    assert "dispatch" not in runner.calls
    assert runner.dispatched == []
    assert "re-run with --yes" in out
    for word in ("runner: fake", "harness: claude", "model: claude-opus-5-5"):
        assert word in out
    assert "branch: feat/batch-lifecycle" in out
    assert load_judgements(tmp_path / "judgements.yaml").batches[0].events == []


def test_dispatch_event_records_the_handle(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    (event,) = load_judgements(tmp_path / "judgements.yaml").batches[0].events
    assert isinstance(event, DispatchEvent)
    assert event.handle == "w2:p1K"
    assert event.runner == "fake"
    assert event.branch == "feat/batch-lifecycle"
    assert event.reserved_version is None  # no version block declared


# ------------------------------------------------ gates (§3.C step 6, Test Plan 8)

DISPATCHED = (
    JUDGEMENTS
    + """\
    events:
      - {kind: dispatch, at: 2026-09-25T10:00:00Z, runner: fake, handle: "w1:p0",
         branch: feat/batch-lifecycle, reserved_version: 4.22.0}
"""
)
CANCELLED = (
    DISPATCHED
    + """\
      - {kind: cancel, at: 2026-09-25T11:00:00Z, reason: split}
"""
)


def _pr(state: str = "OPEN", **kw: Any) -> Any:
    from fr.triage.model import PullRequest

    return PullRequest(
        repo=REPO,
        number=kw.pop("number", 700),
        title="batch PR",
        state=state,
        is_draft=kw.pop("is_draft", True),
        url=f"https://github.com/{REPO}/pull/700",
        head_ref="feat/batch-lifecycle",
        created_at="2026-09-25T10:30:00+00:00",
        **kw,
    )


@pytest.mark.parametrize("live", [False, True], ids=["runner-idle", "runner-live"])
@pytest.mark.parametrize("stage", ["dispatched", "pr-open"])
def test_the_stage_gate_refuses_a_dispatched_or_pr_open_batch(
    tmp_path: Path,
    gh: FakeGhClient,
    runner: FakeRunner,
    checkout: FakeCheckout,
    stage: str,
    live: bool,
) -> None:
    facts = _facts(prs=[_pr()]) if stage == "pr-open" else _facts()
    _state(tmp_path, facts, DISPATCHED)
    if live:
        runner.live = {ITEM}
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 2
    assert stage in out and "--repair" in out
    assert runner.dispatched == [] and _mutations(gh) == []
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_a_cancelled_batch_may_be_dispatched_again_on_its_existing_branch(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, judgements=CANCELLED)
    checkout.remote_branches = {"feat/batch-lifecycle"}  # left by the first run
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    assert len(runner.dispatched) == 1


def test_the_branch_gate_refuses_a_proposed_batch_already_on_origin(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    checkout.remote_branches = {"feat/batch-lifecycle"}
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 2
    assert "already dispatched from another scope" in out
    assert runner.calls == [] and _mutations(gh) == []


def test_can_dispatch_is_consulted_before_preflight(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    """Spec §3.C step 6.3 (review r2p-f12b): the cheap routing gate runs first,
    and a refusal there reaches no backend call at all."""
    _state(tmp_path)
    runner.accepts = False
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 2
    assert "runner `fake` does not take run-unit work" in out
    assert runner.calls == ["can_dispatch"]


def test_the_protocol_calls_run_in_the_spec_order(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    assert runner.calls == ["can_dispatch", "preflight", "existing_dispatches", "dispatch"]


def test_a_preflight_refusal_writes_nothing(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    runner.refusal = "herdr is not on PATH"
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 2
    assert "herdr is not on PATH" in out
    assert "dispatch" not in runner.calls and _mutations(gh) == []


def test_a_live_item_is_refused_by_name(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    runner.live = {ITEM}
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 2
    assert ITEM in out
    assert "dispatch" not in runner.calls and _mutations(gh) == []


# ------------------------------------------------------ forge writes (§3.E)


def test_label_and_marker_reach_every_member_only_after_the_runner_dispatched(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    order: list[str] = []
    real_dispatch = runner.dispatch

    def _dispatch_first(item: WorkItem) -> str | None:
        order.append(f"runner:{len(_mutations(gh))}")
        return real_dispatch(item)

    runner.dispatch = _dispatch_first  # type: ignore[method-assign]
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    assert order == ["runner:0"]  # no forge write before the runner accepted
    for n in MEMBERS:
        assert "fr:in-progress" in gh.issues[(REPO, n)].labels
        (comment,) = gh.issue_comments[(REPO, n)]
        assert comment["body"].startswith(f"<!-- fr-batch:{ITEM} -->")
        assert "feat/batch-lifecycle" in comment["body"]
        assert "w2:p1K" not in comment["body"]  # the handle never reaches the forge
    assert "fr:in-progress" not in gh.issues[(REPO, 420)].labels


def test_a_failed_dispatch_writes_nothing(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    runner.fail = RuntimeError("tab create failed")
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 1
    assert "tab create failed" in out
    assert _mutations(gh) == []
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_a_runner_without_a_handle_records_the_item_id(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    """Review r2p-handle: `Runner.dispatch` may return None; the event's handle
    is a required str, so None maps to the item id, the runner's own identity
    for the dispatch (`existing_dispatches` matches by it)."""
    _state(tmp_path)
    runner.handle = None
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    (event,) = load_judgements(tmp_path / "judgements.yaml").batches[0].events
    assert isinstance(event, DispatchEvent)
    assert event.handle == ITEM


def test_a_forge_failure_after_dispatch_keeps_the_event_and_names_repair(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path)
    gh.fail_on_mutation = 3  # ensure_labels, 577 label + comment, then 575 label fails
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 1
    assert "super-fr#575" in out and "--repair" in out
    (event,) = load_judgements(tmp_path / "judgements.yaml").batches[0].events
    assert isinstance(event, DispatchEvent)


def test_a_redispatch_after_cancel_posts_a_new_marker(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, judgements=CANCELLED)
    for n in MEMBERS:
        gh.issue_comments[(REPO, n)] = [
            {"body": f"<!-- fr-batch:{ITEM} -->\nDispatched", "created_at": "2026-09-25T10:00Z"},
            {"body": f"<!-- fr-batch-withdrawn:{ITEM} -->\nbatch withdrawn", "created_at": "x"},
        ]
    code, out = _dispatch(tmp_path, "lifecycle", "--yes")
    assert code == 0, out
    for n in MEMBERS:
        assert len(gh.issue_comments[(REPO, n)]) == 3


# ------------------------------------------------------------ --repair (§3.C)


def test_repair_calls_no_runner_keeps_the_reservation_and_posts_no_duplicate(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, _facts(config=VERSION_CONFIG), DISPATCHED)
    gh.issue_comments[(REPO, 577)] = [
        {"body": f"<!-- fr-batch:{ITEM} -->\nDispatched", "created_at": "2026-09-25T10:00Z"}
    ]
    checkout.files[("origin/main", "pyproject.toml")] = PYPROJECT.replace("4.21.1", "4.30.0")
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _dispatch(tmp_path, "lifecycle", "--repair", "--yes")
    assert code == 0, out
    assert runner.calls == [] and runner.loaded == []  # type: ignore[attr-defined]
    assert (tmp_path / "judgements.yaml").read_bytes() == before  # no new event
    assert len(gh.issue_comments[(REPO, 577)]) == 1  # the marker was already there
    assert len(gh.issue_comments[(REPO, 575)]) == 1  # the missing one was posted
    for n in MEMBERS:
        assert "fr:in-progress" in gh.issues[(REPO, n)].labels
    assert "4.22.0" in out  # the stored reservation, not a new one


def test_repair_without_yes_writes_nothing(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, judgements=DISPATCHED)
    code, out = _dispatch(tmp_path, "lifecycle", "--repair")
    assert code == 0, out
    assert _mutations(gh) == [] and runner.calls == []


def test_repair_refuses_a_batch_whose_last_event_is_not_a_dispatch(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    _state(tmp_path, judgements=CANCELLED)
    code, out = _dispatch(tmp_path, "lifecycle", "--repair", "--yes")
    assert code == 2
    assert "--repair" in out
    assert _mutations(gh) == []


def test_an_unsupported_backend_is_refused_with_its_message(
    tmp_path: Path, runner: FakeRunner, checkout: FakeCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.real_glabclient import RealGlabClient

    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: RealGlabClient())
    _state(tmp_path)
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 2
    assert "gh#611" in out


# ----------------------------------------------------- reservation (§3.D)


def test_successive_dispatches_reserve_successive_versions(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    second = JUDGEMENTS.replace(
        "issues:\n",
        "issues:\n  super-fr#1: {tier: 1}\n",
    ) + (
        '  - id: second\n    title: Second\n    ids: ["super-fr#1"]\n'
        "    launch: {runner: fake, harness: claude, model: m}\n"
    )
    facts = _facts(config=VERSION_CONFIG, issues=[_issue(577), _issue(575), _issue(420), _issue(1)])
    gh.add_issue(REPO, 1)
    _state(tmp_path, facts, second)
    assert _dispatch(tmp_path, "lifecycle", "--yes")[0] == 0  # minor: 4.21.1 -> 4.22.0
    code, out = _dispatch(tmp_path, "second", "--yes")  # patch, after the live 4.22.0
    assert code == 0, out
    events = {b.id: b.events[-1] for b in load_judgements(tmp_path / "judgements.yaml").batches}
    assert events["lifecycle"].reserved_version == "4.22.0"  # type: ignore[union-attr]
    assert events["second"].reserved_version == "4.22.1"  # type: ignore[union-attr]


def test_the_source_version_is_read_from_the_default_branch_on_origin(
    tmp_path: Path, gh: FakeGhClient, runner: FakeRunner, checkout: FakeCheckout
) -> None:
    checkout.default = "trunk"
    checkout.files = {
        ("origin/trunk", "pyproject.toml"): PYPROJECT.replace("4.21.1", "5.0.0"),
        ("HEAD", "pyproject.toml"): PYPROJECT.replace("4.21.1", "9.9.9"),
    }
    _state(tmp_path, _facts(config=VERSION_CONFIG))
    code, out = _dispatch(tmp_path, "lifecycle")
    assert code == 0, out
    assert "reserved version: 5.1.0" in out
    assert checkout.fetched == 1
