"""Tracker protocol + per-instance mapping config — §4.G of the 2026-08-14
workflow-shapes-and-workitem-dispatch spec. No Jira adapter is built here;
`GithubTracker` (built from today's label behavior) is the one concrete
implementation, and it exists to prove the Protocol is satisfiable and that
the config loader/resolver round-trips real data, not to ship a second
tracker.

Fixture discipline note: `_SCRAMBLED_MAPPING` below (a `jira`/`ACME`
instance) declares its state keys in an order that does NOT sort into
lifecycle order (`in_review`, `blocked`, `queued`, `done`, `in_progress` —
alphabetical would be `blocked, done, in_progress, in_review, queued`), so a
precedence-style regression in the loader/resolver path would be caught
rather than masked by an accidental sort (see the phase-3 finding
`p3-label-precedence-alphabetical`, the reason this instruction exists).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.item_state import ITEM_STATES, ItemState

from tests.unit.fakes import FakeGhClient
from tests.unit.test_tick_workitem import (
    REPO,
    FakeRunner,
    RecordingMetrics,
    _one_phase_plan,
    _ready,
)

# ── (a) load_trackers — the config parser ───────────────────────────────

# Deliberately scrambled key order (see module docstring) — a dict literal
# in Python preserves insertion order, so this also pins that nothing
# downstream silently re-sorts it into lifecycle order and calls that a
# feature.
_SCRAMBLED_MAPPING = """
jira:
  ACME:
    in_review: null
    blocked: {transition: "Block"}
    queued: {status: "To Do"}
    done: {transition: "Resolve"}
    in_progress: {transition: "Start Progress"}
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "trackers.yaml"
    p.write_text(text)
    return p


def test_load_trackers_parses_tracker_instance_state_mapping(tmp_path: Path):
    from fr.tracker.model import load_trackers

    cfg = load_trackers(_write(tmp_path, _SCRAMBLED_MAPPING))

    assert cfg["jira"]["ACME"]["queued"] == {"status": "To Do"}
    assert cfg["jira"]["ACME"]["in_review"] is None


def test_load_trackers_missing_file_yields_empty_config(tmp_path: Path):
    from fr.tracker.model import load_trackers

    assert load_trackers(tmp_path / "nope.yaml") == {}


def test_load_trackers_fails_loud_on_an_unknown_state_key(tmp_path: Path):
    from fr.tracker.model import TrackerConfigError, load_trackers

    bad = _write(
        tmp_path,
        """
        jira:
          ACME:
            in_progresss: {transition: "Start Progress"}
        """,
    )
    with pytest.raises(TrackerConfigError, match="in_progresss"):
        load_trackers(bad)


def test_load_trackers_rejects_a_non_mapping_top_level(tmp_path: Path):
    from fr.tracker.model import TrackerConfigError, load_trackers

    with pytest.raises(TrackerConfigError):
        load_trackers(_write(tmp_path, "- just\n- a\n- list\n"))


def test_load_trackers_rejects_a_non_mapping_instance(tmp_path: Path):
    from fr.tracker.model import TrackerConfigError, load_trackers

    bad = _write(tmp_path, "jira:\n  ACME: not-a-mapping\n")
    with pytest.raises(TrackerConfigError):
        load_trackers(bad)


# ── (b) resolve_instance_mapping — repo over user, mirrors fr.models ────


def test_resolution_prefers_repo_over_user():
    from fr.tracker.model import resolve_instance_mapping

    repo_cfg = {"jira": {"ACME": {"queued": {"status": "Backlog"}}}}
    user_cfg = {"jira": {"ACME": {"queued": {"status": "To Do"}}}}

    mapping = resolve_instance_mapping("jira", "ACME", repo_cfg=repo_cfg, user_cfg=user_cfg)

    assert mapping == {"queued": {"status": "Backlog"}}


def test_resolution_falls_back_to_user_when_repo_has_no_entry():
    from fr.tracker.model import resolve_instance_mapping

    repo_cfg: dict = {}
    user_cfg = {"jira": {"ACME": {"queued": {"status": "To Do"}}}}

    mapping = resolve_instance_mapping("jira", "ACME", repo_cfg=repo_cfg, user_cfg=user_cfg)

    assert mapping == {"queued": {"status": "To Do"}}


def test_resolution_is_none_when_neither_config_has_the_instance():
    from fr.tracker.model import resolve_instance_mapping

    mapping = resolve_instance_mapping("jira", "ACME", repo_cfg={}, user_cfg={})

    assert mapping is None


def test_resolution_does_not_inject_the_shipped_root_or_any_other_default():
    """Regression fixture for the class of bug the branch's own review
    caught elsewhere (resolution tests that always injected the shipped
    root): resolution here must answer purely from the two dicts it is
    given, never from a real config file on this machine."""
    from fr.tracker.model import resolve_instance_mapping

    # A tracker/instance pair that is vanishingly unlikely to exist in any
    # real ~/.config/fr/trackers.yaml or docs/superpowers/trackers.yaml —
    # if resolution silently consulted disk, this would still (correctly)
    # return None, but a *positive* hit below is what actually proves it.
    repo_cfg = {"jira": {"NOT-A-REAL-PROJECT-KEY-9f3": {"queued": {"status": "Backlog"}}}}
    assert resolve_instance_mapping(
        "jira", "NOT-A-REAL-PROJECT-KEY-9f3", repo_cfg=repo_cfg, user_cfg={}
    ) == {"queued": {"status": "Backlog"}}
    assert (
        resolve_instance_mapping("jira", "SOME-OTHER-KEY", repo_cfg=repo_cfg, user_cfg={}) is None
    )


# ── (c) state_supported — null vs. present, the partial-mapping rule ────


def test_state_supported_is_false_for_a_null_mapping():
    from fr.tracker.model import state_supported

    mapping = {"in_review": None, "queued": {"status": "To Do"}}

    assert state_supported(mapping, "in_review") is False


def test_state_supported_is_true_for_a_present_mapping():
    from fr.tracker.model import state_supported

    mapping = {"queued": {"status": "To Do"}}

    assert state_supported(mapping, "queued") is True


def test_state_supported_is_false_when_the_state_key_is_absent_entirely():
    """A partial mapping (spec §4.G) may simply omit a state rather than
    spell it out as `null` — both mean 'this instance cannot express it'."""
    from fr.tracker.model import state_supported

    assert state_supported({"queued": {"status": "To Do"}}, "done") is False


def test_state_supported_is_false_for_no_mapping_at_all():
    from fr.tracker.model import state_supported

    assert state_supported(None, "queued") is False


def test_every_item_state_round_trips_through_a_full_mapping():
    """Not a tautology: iterates the REAL `ITEM_STATES` tuple rather than a
    hand-typed list, so a future sixth state is covered automatically."""
    from fr.tracker.model import state_supported

    full = {state: {"marker": state} for state in ITEM_STATES}
    for state in ITEM_STATES:
        assert state_supported(full, state) is True


# ── (d) GithubTracker — satisfies the Protocol, delegates to fr.item_state ─


def _github_tracker(gh: FakeGhClient, *, mapping=None):
    from fr.tracker.github import GithubTracker

    return GithubTracker(instance=REPO, gh=gh, mapping=mapping)


def test_github_tracker_satisfies_the_tracker_protocol():
    from fr.tracker.model import Tracker

    gh = FakeGhClient()
    tracker: Tracker = _github_tracker(gh)
    assert tracker.name == "github"


def test_github_tracker_supports_all_five_states_by_default():
    """'Built from the existing label behavior': with no per-instance
    override, GithubTracker supports every ItemState — the same claim
    `fr.item_state._GITHUB_PROJECTION` already makes about today's labels."""
    gh = FakeGhClient()
    tracker = _github_tracker(gh)

    for state in ITEM_STATES:
        assert tracker.supports(state) is True


def test_github_tracker_honours_a_partial_instance_override():
    gh = FakeGhClient()
    mapping = {
        "queued": {"label": "fr:ready"},
        "blocked": {"label": "fr:blocked"},
        "in_progress": {"label": "fr:in-progress"},
        "in_review": None,  # this GitHub instance's board has no review column
        "done": {"close": True},
    }
    tracker = _github_tracker(gh, mapping=mapping)

    assert tracker.supports("in_review") is False
    assert tracker.supports("queued") is True


def test_github_tracker_observe_reads_state_off_the_issue_labels(tmp_path: Path):
    from fr.render import phase_item_decision

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    items = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)
    tracker = _github_tracker(gh)

    observed = tracker.observe(items)

    assert observed[items[0].id] == "queued"
    # Cross-checked against the neutral seam itself, not re-derived here.
    from fr.observe import observe as gh_observe

    decision = phase_item_decision(plan, gh_observe(plan, gh), 1)
    assert observed[items[0].id] == decision.state


def test_github_tracker_observe_reports_done_for_a_closed_issue():
    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    gh.issues[(repo, n)].state = "CLOSED"
    gh.issues[(repo, n)].labels = set()

    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    items = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)
    tracker = _github_tracker(gh)

    assert tracker.observe(items)[items[0].id] == "done"


def test_github_tracker_create_item_refuses_bypassing_the_operator_only_invariant():
    """Issue creation stays operator-only (`fr apply --yes`; the 2026-05-18
    incident) — the tracker seam does not grow a second creation path."""
    gh = FakeGhClient()
    tracker = _github_tracker(gh)
    plan, repo, n = _one_phase_plan()
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    item = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)[0]

    with pytest.raises(NotImplementedError, match="operator-only"):
        tracker.create_item(item)


def test_github_tracker_link_parent_is_honestly_unimplemented():
    """GitHub has no native parent/epic link — hierarchy synthesis (task
    lists, cross-references) is real future work this phase does not
    build; `NotImplementedError` says so rather than silently no-op'ing."""
    gh = FakeGhClient()
    tracker = _github_tracker(gh)
    plan, repo, n = _one_phase_plan()
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    item = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)[0]

    with pytest.raises(NotImplementedError):
        tracker.link_parent(item, item)


def test_github_tracker_transition_edits_labels_via_the_shared_projection():
    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    gh.ensure_labels(repo, ["fr:ready", "fr:in-progress", "fr:blocked", "fr:pr-ready"])

    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    item = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)[0]
    tracker = _github_tracker(gh)

    tracker.transition(item, "in_progress")

    assert "fr:in-progress" in gh.issues[(repo, n)].labels
    assert "fr:ready" not in gh.issues[(repo, n)].labels


def test_github_tracker_transition_to_done_closes_the_issue():
    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    gh.ensure_labels(repo, ["fr:ready"])

    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    item = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)[0]
    tracker = _github_tracker(gh)

    tracker.transition(item, "done")

    assert gh.issues[(repo, n)].state == "closed"


def test_github_tracker_transition_refuses_an_unsupported_state():
    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))

    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch.item_graph import build_items

    item = build_items(FR_GOAL_PHASE_DISPATCH, plan, repo=repo)[0]
    mapping = {s: ({"label": s} if s != "in_review" else None) for s in ITEM_STATES}
    tracker = _github_tracker(gh, mapping=mapping)

    with pytest.raises(ValueError, match="in_review"):
        tracker.transition(item, "in_review")


# ── (e) check_tracker_mapping_shape — honestly-named, config-only ───────


def test_check_tracker_mapping_shape_reports_an_unresolvable_instance():
    from fr.tracker.model import check_tracker_mapping_shape

    problems = check_tracker_mapping_shape("jira", "GHOST", repo_cfg={}, user_cfg={})

    assert problems and "GHOST" in problems[0]


def test_check_tracker_mapping_shape_is_clean_for_a_resolvable_instance():
    from fr.tracker.model import check_tracker_mapping_shape

    repo_cfg = {"jira": {"ACME": {"queued": {"status": "To Do"}}}}

    assert check_tracker_mapping_shape("jira", "ACME", repo_cfg=repo_cfg, user_cfg={}) == []


def test_check_tracker_mapping_shape_docstring_disclaims_live_validation():
    """§4.G's 'validate against the live server's actual transitions' half
    is NOT implemented — the docstring must say so honestly rather than
    read as though this function reaches a real Jira/GitHub instance."""
    from fr.tracker.model import check_tracker_mapping_shape

    doc = check_tracker_mapping_shape.__doc__ or ""
    assert "live" in doc.lower()
    assert "not" in doc.lower()


# ── (f) the refusal path — reuses the Phase-5 capability short-circuit ──


class _FakeTracker:
    """A non-GitHub tracker double whose vocabulary/name deliberately does
    not sort into lifecycle order — see the module docstring."""

    name = "jira"

    def __init__(self, unsupported: frozenset[ItemState] = frozenset()) -> None:
        self._unsupported = unsupported

    def supports(self, state: ItemState) -> bool:
        return state not in self._unsupported

    def observe(self, items):  # pragma: no cover - not exercised here
        return {}

    def create_item(self, item):  # pragma: no cover
        raise NotImplementedError

    def transition(self, item, to):  # pragma: no cover
        raise NotImplementedError

    def link_parent(self, child, parent):  # pragma: no cover
        raise NotImplementedError


def test_tick_refuses_when_the_tracker_cannot_express_a_required_state():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner()
    tracker = _FakeTracker(unsupported=frozenset({"in_review"}))

    result = tick(
        plan,
        gh,
        runner,
        tracker=tracker,
        tracker_instance="ACME",
        required_tracker_states=frozenset({"in_review"}),
        metrics=m,
    )

    assert result.synced == 0
    assert result.errors == 1
    assert "in_review" in result.failures[0]
    assert "ACME" in result.failures[0]
    assert "jira" in result.failures[0]
    assert runner.preflight_items is None  # never reached — same short-circuit as §4.F
    assert runner.dispatched == []
    assert m.reasons == ["preflight"]


def test_tracker_refusal_is_checked_after_capability_refusal_not_instead_of_it():
    """One chain, ordered: capability -> tracker -> runner.preflight. A
    capability shortfall must win even when the tracker ALSO can't express
    the required state, so the failure message always names the FIRST
    thing wrong, never a coin flip between two refusal mechanisms."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()  # capabilities = {"git", "scm"} — no "browser"
    tracker = _FakeTracker(unsupported=frozenset({"in_review"}))

    result = tick(
        plan,
        gh,
        runner,
        required_capabilities=frozenset({"browser"}),
        tracker=tracker,
        tracker_instance="ACME",
        required_tracker_states=frozenset({"in_review"}),
    )

    assert "browser" in result.failures[0]
    assert "in_review" not in result.failures[0]


def test_tick_dispatches_normally_when_the_tracker_supports_every_required_state():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()
    tracker = _FakeTracker(unsupported=frozenset())

    result = tick(
        plan,
        gh,
        runner,
        tracker=tracker,
        tracker_instance="ACME",
        required_tracker_states=frozenset({"in_review", "queued"}),
    )

    assert result.synced == 1
    assert runner.preflight_items is not None  # preflight DID run — no blocker


def test_tick_default_required_tracker_states_is_empty_and_never_refuses():
    """No caller passing `required_tracker_states` (every pre-Phase-10
    caller, including the live bridge) sees any behavior change."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()
    tracker = _FakeTracker(unsupported=frozenset(ITEM_STATES))  # would refuse EVERYTHING if checked

    result = tick(plan, gh, runner, tracker=tracker, tracker_instance="ACME")

    assert result.synced == 1


def test_tick_with_no_tracker_configured_never_refuses_on_tracker_state():
    """`required_tracker_states` with `tracker=None` (the still-legal
    default) must not blow up or refuse — a tracker that cannot express a
    state must still be usable when nobody has wired one in yet."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    result = tick(plan, gh, runner, required_tracker_states=frozenset({"in_review"}))

    assert result.synced == 1
