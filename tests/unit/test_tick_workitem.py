"""`fr_dispatch.tick` against Runner protocol v2 — the WorkItem loop.

Spec 2026-08-14-workflow-shapes-and-workitem-dispatch §4.D. `tick` stops
iterating `(plan, phase, repo, issue_number)` tuples and iterates
`WorkItem`s; `Runner` loses `dedup_key` (identity lives on the item) and
`can_dispatch_repo` becomes `can_dispatch(item)`.

**Every behaviour pinned here is a restatement of the pre-cutover failure
doctrine, not a new one.** The tick is what a cron daemon runs against
live repos, so its contract under partial failure is the load-bearing
part: per-item accumulation, one bad item never aborts the loop, a raising
`dispatch` leaves the synced stamp unwritten so the next tick retries, and
Issue creation stays operator-only (`skip_issue_create=True` — the
2026-05-18 incident, sfv#196-#214 / sfv#216-#234).

These tests use a `FakeRunner` implementing the v2 protocol directly rather
than `VkRunner`, so they pin the *framework's* doctrine independent of any
adapter. The adapters move in Phase 4.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from fr_dispatch.metrics import NullMetrics

from tests.unit.fakes import FakeGhClient

MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
MULTI = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"

REPO = "derio-net/superpowers-for-vk"

# The id `tick` must compute for phase 1 of the minimal fixture:
# <repo>/<spec-slug>/<plan-slug>/phase/<n>, spec slug being the stem of
# `_meta.yaml`'s `spec:` path (the same derivation render.py uses for the
# `spec:` label).
MINIMAL_PHASE_1_ID = f"{REPO}/fixture-spec-design/2026-05-09-fixture-minimal/phase/1"


# ── doubles ────────────────────────────────────────────────────────────


class FakeRunner:
    """Runner protocol v2 — 6 methods, no `dedup_key`."""

    name = "fake"
    capabilities = frozenset({"git", "scm"})

    def __init__(
        self,
        *,
        preflight_error: str | None = None,
        budget: int = 10,
        existing: set[str] | None = None,
        unroutable: set[str] = frozenset(),  # type: ignore[assignment]
        dispatch_fails: set[str] = frozenset(),  # type: ignore[assignment]
        raise_in: set[str] = frozenset(),  # type: ignore[assignment]
    ) -> None:
        self._preflight_error = preflight_error
        self._budget = budget
        self._existing = set(existing or set())
        self._unroutable = set(unroutable)
        self._dispatch_fails = set(dispatch_fails)
        self._raise_in = set(raise_in)
        self.refreshed = 0
        self.preflight_items: Any = None
        self.existing_dispatches_items: Any = None
        self.dispatched: list[Any] = []
        self.can_dispatch_seen: list[Any] = []

    def _maybe_raise(self, where: str) -> None:
        if where in self._raise_in:
            raise RuntimeError(f"{where} boom")

    def preflight(self, items: Any) -> str | None:
        self.preflight_items = list(items)
        self._maybe_raise("preflight")
        return self._preflight_error

    def refresh(self) -> None:
        self.refreshed += 1
        self._maybe_raise("refresh")

    def slot_budget(self) -> int:
        self._maybe_raise("slot_budget")
        return self._budget

    def existing_dispatches(self, items: Any) -> set[str]:
        self.existing_dispatches_items = list(items)
        self._maybe_raise("existing_dispatches")
        return set(self._existing)

    def can_dispatch(self, item: Any) -> bool:
        self.can_dispatch_seen.append(item)
        self._maybe_raise("can_dispatch")
        return item.id not in self._unroutable

    def dispatch(self, item: Any) -> None:
        if item.id in self._dispatch_fails:
            raise RuntimeError("injected backend failure")
        self.dispatched.append(item)


class RecordingMetrics(NullMetrics):
    """NullMetrics that remembers what tick emitted (no network)."""

    def __init__(self) -> None:
        super().__init__()
        self.reasons: list[str] = []
        self.syncs = 0
        self.heartbeats = 0

    def push_sync_total(self) -> None:
        self.syncs += 1

    def push_failure_total(self, *, reason: str) -> None:
        self.reasons.append(reason)

    def push_heartbeat(self) -> None:
        self.heartbeats += 1


# ── fixtures/helpers ───────────────────────────────────────────────────


def _one_phase_plan(repo: str = REPO, issue_number: int = 42):
    """Minimal fixture with phase 1 stamped with a tracking_issue."""
    from fr import parse

    plan = parse(MINIMAL)
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{issue_number}"}
            )
        }
    )
    return (
        dc_replace(plan, phases=(phase,), meta=plan.meta.model_copy(update={"target_repo": repo})),
        repo,
        issue_number,
    )


def _two_phase_plan(repo: str = REPO):
    """Two INDEPENDENT tracked phases, both projecting ready.

    Phase 2 of the multi-phase fixture depends on phase 1; the dependency
    is dropped here so both are eligible in the same tick — the shape the
    slot-budget and one-bad-item tests need.
    """
    from fr import parse

    plan = parse(MULTI)
    phases = []
    for i, n in enumerate((1, 2)):
        src = plan.phases[i]
        phases.append(
            src.model_copy(
                update={
                    "phase": src.phase.model_copy(
                        update={
                            "tracking_issue": f"https://github.com/{repo}/issues/{100 + n}",
                            "depends_on": (),
                        }
                    )
                }
            )
        )
    return dc_replace(
        plan, phases=tuple(phases), meta=plan.meta.model_copy(update={"target_repo": repo})
    )


def _ready(gh: FakeGhClient, plan, repo: str, numbers: tuple[int, ...]) -> None:
    """Preload OPEN, `fr:ready` Issues with in-sync bodies for `numbers`."""
    from fr.observe import observe
    from fr.render import render

    for phase in plan.phases:
        n = phase.phase.number
        number = int(phase.phase.tracking_issue.rsplit("/", 1)[1])
        if number not in numbers:
            continue
        gh.add_issue(repo, number, state="OPEN", labels={"fr:ready", f"phase:{n}"})
    rendered = render(plan, observe(plan, gh))
    for phase in plan.phases:
        n = phase.phase.number
        number = int(phase.phase.tracking_issue.rsplit("/", 1)[1])
        if (repo, number) in gh.issues:
            gh.issues[(repo, number)].body = rendered.issue_per_phase[n].body


def _synced_adds(gh: FakeGhClient) -> list[dict[str, Any]]:
    return [c[1] for c in gh.calls if c[0] == "edit_issue_labels" and "fr:synced" in c[1]["add"]]


# ── item construction ──────────────────────────────────────────────────


def test_tick_builds_a_phase_unit_workitem_with_the_spec_grammar_id():
    """The item handed to `dispatch` carries the §4.D identity, not a title."""
    from fr_dispatch import tick
    from fr_dispatch.work_item import parent_id

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    result = tick(plan, gh, runner)

    assert result.synced == 1
    (item,) = runner.dispatched
    assert item.id == MINIMAL_PHASE_1_ID
    assert item.unit == "phase"
    assert item.repo == repo
    # `parent` is the PLAN level — a parent, never a dispatchable unit.
    assert item.parent == parent_id(item.id)
    assert item.parent == f"{repo}/fixture-spec-design/2026-05-09-fixture-minimal"
    assert item.tracking == f"https://github.com/{repo}/issues/{n}"


def test_workitem_payload_carries_what_an_adapter_needs():
    """§4.D: an adapter derives `(repo, issue_number)` from `tracking` +
    `payload`, and the phase-unit payload additionally carries the plan and
    phase objects the VK/cncd dispatch bodies are built from."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    tick(plan, gh, runner)

    (item,) = runner.dispatched
    assert item.payload["plan"] is plan
    assert item.payload["phase"] is plan.phases[0]
    assert item.payload["issue_number"] == n


def test_workitem_id_falls_back_to_a_sentinel_spec_slug_when_the_plan_has_no_spec():
    """The multi-phase fixture has no `spec:` — identity must still be
    computable (it is pure string composition, no I/O), so the spec segment
    degrades to a reserved sentinel rather than raising."""
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    runner = FakeRunner()

    tick(plan, gh, runner)

    ids = sorted(i.id for i in runner.dispatched)
    assert ids == [
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1",
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2",
    ]


def test_workitem_declares_its_inputs_and_workflow():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    tick(plan, gh, runner)

    (item,) = runner.dispatched
    assert item.workflow == "fr-goal"
    kinds = {ref.kind: ref for ref in item.inputs}
    assert kinds["plan"].path.endswith("v2_plan_minimal")
    assert kinds["spec"].path == "docs/superpowers/specs/fixture-spec-design.md"
    # Same-repo spec: attributed to the plan's own target repo.
    assert kinds["spec"].repo == plan.meta.target_repo


def test_a_cross_repo_spec_input_names_the_other_repo_and_stays_repo_relative(tmp_path: Path):
    """`ArtifactRef.path` is documented repo-relative and normalized.

    `parser` deliberately leaves `plan.spec_path is None` for a cross-repo
    `<owner>/<repo>:<path>` spec (it can't resolve a path in a checkout it
    doesn't have), so falling back to `meta.spec` shipped the raw notation
    as a `path` — and attributed it to `target_repo`, the one repo the file
    is NOT in. `render.spec_url` and `repair` both split the notation for
    exactly this case; the item's `inputs` must too, because Phase 8
    (reachability from inputs) and Phase 9 (multi-repo fan-out) consume
    these refs as coordinates.
    """
    import shutil

    from fr import parse
    from fr_dispatch.item_graph import plan_artifact_refs

    plan_dir = tmp_path / "plan"
    shutil.copytree(MINIMAL, plan_dir)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(
        meta.read_text().replace(
            "spec: docs/superpowers/specs/fixture-spec-design.md",
            "spec: other-org/other-repo:docs/superpowers/specs/elsewhere-design.md",
        )
    )
    plan = parse(plan_dir)
    assert plan.spec_path is None  # the parser's cross-repo behaviour, pinned

    refs = {ref.kind: ref for ref in plan_artifact_refs(plan)}
    assert refs["spec"].repo == "other-org/other-repo"
    assert refs["spec"].path == "docs/superpowers/specs/elsewhere-design.md"
    assert ":" not in refs["spec"].path
    # The plan itself still lives in the plan's own repo.
    assert refs["plan"].repo == plan.meta.target_repo


# ── (a) a raising dispatch fails ONLY that item, stamp unwritten ────────


def test_raising_dispatch_marks_item_failed_and_leaves_the_synced_stamp_unwritten():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(dispatch_fails={MINIMAL_PHASE_1_ID})

    result = tick(plan, gh, runner, metrics=m)

    assert result.synced == 0
    assert result.errors == 1
    assert len(result.failures) == 1
    assert "injected backend failure" in result.failures[0]
    assert MINIMAL_PHASE_1_ID in result.failures[0]
    assert m.reasons == ["backend_error"]
    # The stamp is what makes the next tick skip — it must NOT be written.
    assert _synced_adds(gh) == []
    assert "fr:synced" not in gh.issues[(repo, n)].labels


def test_next_tick_retries_an_item_whose_dispatch_raised():
    """The whole point of leaving the stamp unwritten."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))

    first = tick(plan, gh, FakeRunner(dispatch_fails={MINIMAL_PHASE_1_ID}))
    assert first.synced == 0

    second_runner = FakeRunner()
    second = tick(plan, gh, second_runner)

    assert second.synced == 1
    assert [i.id for i in second_runner.dispatched] == [MINIMAL_PHASE_1_ID]


# ── (b) one bad item never aborts the loop ─────────────────────────────


def test_one_failing_item_does_not_abort_the_loop():
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    bad = f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1"
    good = f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2"
    m = RecordingMetrics()
    runner = FakeRunner(dispatch_fails={bad})

    result = tick(plan, gh, runner, metrics=m)

    assert [i.id for i in runner.dispatched] == [good]
    assert result.synced == 1
    assert result.errors == 1
    assert m.syncs == 1
    assert m.reasons == ["backend_error"]
    # Only the good item got stamped.
    assert [c["number"] for c in _synced_adds(gh)] == [102]


def test_a_phase_whose_item_cannot_be_built_fails_only_itself():
    """The item-construction guard, exercised directly.

    It cannot be reached through `tick`: `observe()` parses every tracking
    URL first and raises on a malformed one, so a bad URL kills the tick
    before the guard sees it (true before this cutover too — the old
    `parse_issue_url` try/except in the eligibility loop was defensive
    only). The guard is still the thing that keeps a future non-URL item
    failure — an un-composable id, say — from aborting the loop, so it is
    pinned at the helper it lives in rather than not at all.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import _eligible_items

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    observed = observe(plan, gh)
    rendered = render(plan, observed)

    broken = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": "not-a-url"})}
    )
    plan = dc_replace(plan, phases=(broken, plan.phases[1]))

    failures: list[str] = []
    items = _eligible_items(plan, observed, rendered, failures)

    assert [i.id for i in items] == [f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2"]
    assert len(failures) == 1
    # Named like every other accumulated failure: the item ref, which also
    # says WHICH plan the phase belongs to. (The id could not be *composed*
    # here — that is what failed — so the ref is built segment-wise.)
    assert failures[0].startswith(f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1: ")
    assert not failures[0].startswith("phase ")


def test_a_writeback_failure_is_named_by_item_ref_like_every_other_failure(monkeypatch):
    """Both failure classes an operator reads must be formatted alike.

    Every accumulator in the loop emits `f"{item.id}: …"` — deliberately,
    because the id also names the plan. The writeback path (and item
    construction, above) kept the old `phase N:` prefix, so of the failure
    strings a bridge running many plans logs, only some identified the plan.
    """
    import fr_dispatch
    from fr.apply import ApplyResult
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    url = f"https://github.com/{repo}/issues/{n}"

    real_apply = fr_dispatch.apply

    def fake_apply(*args, **kwargs):
        result = real_apply(*args, **kwargs)
        return ApplyResult(
            applied=result.applied,
            failures=result.failures,
            created_issues={1: url},
            dry_run=result.dry_run,
        )

    def boom(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(fr_dispatch, "apply", fake_apply)
    monkeypatch.setattr(fr_dispatch.plan_ops, "set_tracking_issue", boom)

    result = tick(plan, gh, FakeRunner())

    writeback = [f for f in result.failures if "writeback failed" in f]
    assert len(writeback) == 1
    assert writeback[0].startswith(f"{MINIMAL_PHASE_1_ID}: writeback failed: ")


# ── (c) preflight fails EVERY eligible item, synced=0 ──────────────────


def test_preflight_error_fails_every_eligible_item_and_syncs_none():
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    m = RecordingMetrics()
    runner = FakeRunner(preflight_error="VK project id unset")

    result = tick(plan, gh, runner, metrics=m)

    assert result.synced == 0
    assert result.errors == 2
    assert all("VK project id unset" in f for f in result.failures)
    assert result.skipped == 2
    assert m.reasons == ["preflight", "preflight"]
    assert runner.dispatched == []
    assert _synced_adds(gh) == []
    assert m.heartbeats == 1


def test_preflight_receives_the_eligible_items():
    """§4.F: capability negotiation happens in preflight, so it must be
    handed the items — the negotiation logic itself is Phase 5."""
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    runner = FakeRunner()

    tick(plan, gh, runner)

    assert [i.id for i in runner.preflight_items] == [
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1",
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2",
    ]


def test_raising_preflight_is_itself_a_blocker_not_a_crash():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(raise_in={"preflight"})

    result = tick(plan, gh, runner, metrics=m)

    assert result.synced == 0
    assert result.errors == 1
    assert "preflight boom" in result.failures[0]
    assert m.reasons == ["preflight"]


# ── (d) slot_budget caps; the remainder are DEFERRED, not failed ───────


def test_slot_budget_caps_dispatch_and_the_remainder_is_deferred_not_failed():
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    m = RecordingMetrics()
    runner = FakeRunner(budget=1)

    result = tick(plan, gh, runner, metrics=m)

    assert len(runner.dispatched) == 1
    assert result.synced == 1
    assert result.skipped == 1  # deferred
    assert result.errors == 0
    assert result.failures == ()
    assert m.reasons == []


def test_slot_budget_raising_defers_everything_rather_than_dispatching_blind():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner(raise_in={"slot_budget"})

    result = tick(plan, gh, runner)

    assert runner.dispatched == []
    assert result.synced == 0
    assert result.skipped == 1
    assert any("slot check failed" in f for f in result.failures)


# ── (e) a dedup hit skips the backend but STILL gets the stamp ─────────


def test_item_already_in_existing_dispatches_skips_the_backend_but_is_still_stamped():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(existing={MINIMAL_PHASE_1_ID})

    result = tick(plan, gh, runner, metrics=m)

    assert runner.dispatched == []  # no duplicate backend call
    assert result.synced == 1  # but the stamp lands
    assert result.errors == 0
    assert [c["number"] for c in _synced_adds(gh)] == [n]
    assert m.syncs == 1


def test_existing_dispatches_is_keyed_on_item_ids_not_card_titles():
    """A dedup snapshot that does NOT contain the item id must not match."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner(existing={f"gh#{n}: [{repo}]"})  # the legacy card title

    result = tick(plan, gh, runner)

    assert [i.id for i in runner.dispatched] == [MINIMAL_PHASE_1_ID]
    assert result.synced == 1


def test_a_dedup_hit_does_not_consume_a_slot():
    from fr_dispatch import tick

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    already = f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1"
    runner = FakeRunner(budget=1, existing={already})

    result = tick(plan, gh, runner)

    # The dedup hit is stamped without a dispatch; the one slot goes to the
    # item that actually needs the backend.
    assert len(runner.dispatched) == 1
    assert result.synced == 2
    assert result.skipped == 0


def test_a_raising_existing_dispatches_degrades_to_an_empty_snapshot():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner(raise_in={"existing_dispatches"})

    result = tick(plan, gh, runner)

    assert len(runner.dispatched) == 1
    assert any("dedup fetch failed" in f for f in result.failures)
    assert result.synced == 1


# ── (f) Issue creation stays operator-only ────────────────────────────


def test_tick_never_creates_issues_and_never_writes_tracking_back(tmp_path):
    """`apply(..., skip_issue_create=True)` — the 2026-05-18 incident
    (sfv#196-#214 wave 1, sfv#216-#234 wave 2). A phase with a null
    `tracking_issue` is exactly the shape that would otherwise be created.
    """
    import shutil

    import yaml
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(MINIMAL, plan_dir)

    plan = parse(plan_dir)  # tracking_issue is null in the fixture
    gh = FakeGhClient()
    runner = FakeRunner()

    tick(plan, gh, runner)

    assert [c for c in gh.calls if c[0] == "create_issue"] == []
    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"] is None
    assert runner.dispatched == []


# ── eligibility: ItemState, not raw label strings ─────────────────────


def test_an_in_progress_item_is_not_eligible():
    """An assignee projects `in_progress`, so `state_from_labels` no longer
    reads `queued` — the item is skipped even though the stale `fr:ready`
    label is still on the Issue."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"}, assignees=("some-agent",))
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body
    runner = FakeRunner()

    result = tick(plan, gh, runner)

    assert runner.dispatched == []
    assert result.synced == 0
    assert result.skipped == 1
    assert result.errors == 0


def test_an_item_carrying_the_dispatch_stamp_is_not_eligible():
    """`fr:synced` is dispatch bookkeeping, not an ItemState — it is
    checked separately (DISPATCH_STAMP), and it suppresses eligibility."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "fr:synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body
    runner = FakeRunner()

    result = tick(plan, gh, runner)

    assert runner.dispatched == []
    assert result.synced == 0
    assert result.skipped == 1
    assert "fr:synced" in gh.issues[(repo, n)].labels  # apply must not strip it


# ── routing gate: can_dispatch(item) ──────────────────────────────────


def test_can_dispatch_false_fails_the_item_with_the_unknown_repo_reason():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(unroutable={MINIMAL_PHASE_1_ID})

    result = tick(plan, gh, runner, metrics=m)

    assert runner.dispatched == []
    assert result.synced == 0
    assert result.errors == 1
    assert m.reasons == ["unknown_repo"]
    assert _synced_adds(gh) == []


def test_can_dispatch_raising_fails_the_item_with_the_repo_gate_reason():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(raise_in={"can_dispatch"})

    result = tick(plan, gh, runner, metrics=m)

    assert runner.dispatched == []
    assert result.errors == 1
    assert m.reasons == ["repo_gate"]


def test_can_dispatch_is_handed_the_item_not_a_repo_string():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    tick(plan, gh, runner)

    (seen,) = runner.can_dispatch_seen
    assert seen.id == MINIMAL_PHASE_1_ID
    assert seen.repo == repo


# ── GH stamp failures are attributed to GH, not the backend ───────────


def test_gh_stamp_failure_is_reported_as_gh_error_after_a_successful_dispatch():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    # GH mutation order: 0 apply's ensure_labels, 1 apply's label diff,
    # 2 tick's ensure_labels, 3 tick's fr:synced add. Fail the last.
    gh.fail_on_mutation = 3
    m = RecordingMetrics()
    runner = FakeRunner()

    result = tick(plan, gh, runner, metrics=m)

    assert len(runner.dispatched) == 1  # the backend call DID happen
    assert result.synced == 0
    assert "gh_error" in m.reasons
    assert "backend_error" not in m.reasons


def test_apply_side_failures_accumulate_without_short_circuiting_dispatch():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    gh.fail_on_mutation = 0  # apply's leading RepoLabelEnsure
    runner = FakeRunner()

    result = tick(plan, gh, runner)

    assert result.synced == 1
    assert result.errors >= 1
    assert any("configured failure" in f for f in result.failures)


# ── TickResult shape + idle-plan counting ─────────────────────────────


def test_tickresult_fields_and_idle_plan_skipped_convention():
    from fr_dispatch import TickResult, tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "fr:synced", "phase:1"})
    m = RecordingMetrics()

    result = tick(plan, gh, FakeRunner(), metrics=m)

    assert isinstance(result, TickResult)
    assert (result.synced, result.errors, result.skipped) == (0, 0, 1)
    assert result.failures == ()
    assert m.heartbeats == 1  # heartbeat fires even on an idle plan


def test_refresh_is_called_once_and_a_raising_refresh_does_not_kill_the_tick():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner(raise_in={"refresh"})

    result = tick(plan, gh, runner)

    assert runner.refreshed == 1
    assert result.synced == 1
    assert result.errors == 0


# ── protocol shape ────────────────────────────────────────────────────


def test_runner_protocol_v2_has_six_methods_and_no_dedup_key():
    from fr_dispatch.protocols import Runner

    assert not hasattr(Runner, "dedup_key")
    assert not hasattr(Runner, "can_dispatch_repo")
    for method in (
        "preflight",
        "refresh",
        "slot_budget",
        "existing_dispatches",
        "can_dispatch",
        "dispatch",
    ):
        assert hasattr(Runner, method), method


def test_existing_dispatches_receives_this_tick_s_items():
    """The dedup snapshot takes the items it is answering about.

    Adapters have to map board state back to `WorkItem.id`s, and the only
    honest source for that mapping is the item list itself. Passing it
    removes the alternative — an adapter caching the items from an earlier
    `preflight(items)` call and silently returning an empty snapshot if the
    two are ever reordered (VkRunner did exactly that: duplicate cards and
    workspaces on a re-ordered tick).
    """
    import inspect

    from fr_dispatch import tick
    from fr_dispatch.protocols import Runner

    assert "items" in inspect.signature(Runner.existing_dispatches).parameters

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    tick(plan, gh, runner)

    assert [i.id for i in runner.existing_dispatches_items] == [MINIMAL_PHASE_1_ID]
    # …the same list preflight saw, without either call depending on the other.
    assert runner.existing_dispatches_items == runner.preflight_items


def test_fake_runner_satisfies_the_runner_protocol():
    from fr_dispatch.protocols import Runner

    runner: Runner = FakeRunner()
    assert runner.name == "fake"
    assert "git" in runner.capabilities


def test_tick_does_not_reach_for_discover_plans():
    """Phase 10 ships a tripwire on this; assert it here so the coupling
    never appears in the first place. `tick` operates on the plan it is
    given — discovery is the caller's (and later the Source's) job."""
    import inspect

    import fr_dispatch

    assert "discover_plans" not in inspect.getsource(fr_dispatch.tick)
