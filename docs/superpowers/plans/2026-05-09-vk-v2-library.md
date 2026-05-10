# Vk V2 Library Implementation Plan

**Spec:** `docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md`
**Status:** Not Started

**Goal:** Ship the v2 library, CLI, migration tool, and GHA workflow in `superpowers-for-vk`; retire v1 code; release `v2.0.0`; self-migrate this repo's plans. Inline execution via `superpowers:executing-plans`. No dispatch.

**Out of scope (deferred to other plans):**
- Bridge migration in willikins (Plan 2)
- Per-consumer-repo migration sweep (Plan 3)

**Reading order for the executing agent:** open the spec referenced above first, then this plan. The spec is canonical for *design*; this plan is canonical for *sequence*. Where the plan says "per spec §X," consult the spec section rather than re-litigating the design.

---

## Phase 1: Schema + parser foundation [agentic]
**Depends on:** —

**Phase goal:** `vk.v2.parse(plan_dir) -> Plan` returns frozen pydantic-validated dataclasses for v2 plan folders. Lives alongside v1 (no collisions). Round-trips a fixture v2 plan.

**Done when:**
- `pytest tests/unit/test_v2_parse.py -q` green
- `from vk.v2 import parse, Plan, Phase, PlanMeta` works
- v1 tests still all pass (no regression)

### Task 1: Pydantic schemas

- [x] **Step 1: Create v2 package skeleton**
  Create empty package files. Run:
  ```
  mkdir -p src/vk/v2 tests/unit/fixtures/v2_plan_minimal
  touch src/vk/v2/__init__.py src/vk/v2/types.py
  ```
  Verify: `python -c "import vk.v2"` exits 0.

- [x] **Step 2: Write fixture v2 plan folder (minimal valid)**
  Create `tests/unit/fixtures/v2_plan_minimal/_meta.yaml`:
  BEGIN: tests/unit/fixtures/v2_plan_minimal/_meta.yaml
  ```
  schema_version: 2
  plan: 2026-05-09-fixture-minimal
  spec: docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md
  target_repo: derio-net/superpowers-for-vk
  vk_version: ">=2.0.0,<3.0.0"
  created: 2026-05-09
  ```
  END: tests/unit/fixtures/v2_plan_minimal/_meta.yaml
  Create `tests/unit/fixtures/v2_plan_minimal/_prose.md`:
  BEGIN: tests/unit/fixtures/v2_plan_minimal/_prose.md
  ```
  # Fixture: minimal v2 plan
  Plan-level prose. Not read by tooling.
  ```
  END: tests/unit/fixtures/v2_plan_minimal/_prose.md
  Create `tests/unit/fixtures/v2_plan_minimal/01.yaml`:
  BEGIN: tests/unit/fixtures/v2_plan_minimal/01.yaml
  ```
  schema_version: 2
  phase:
    number: 1
    title: Fixture phase
    tag: agentic
    depends_on: []
    tracking_issue: null
  tasks:
    - number: 1
      title: Fixture task
      steps:
        - id: P1.T1.S1
          text: Fixture step
  state:
    steps:
      P1.T1.S1:
        state: " "
        ticked_at: null
        note: null
    completion:
      at: null
      note: null
      observed_prs: []
  ```
  END: tests/unit/fixtures/v2_plan_minimal/01.yaml

- [x] **Step 3: Write test asserting pydantic loads `_meta.yaml`**
  Create `tests/unit/test_v2_parse.py`:
  ```python
  import pytest
  from pathlib import Path

  FIXTURE_DIR = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

  def test_planmeta_loads_minimal_fixture():
      from vk.v2.types import PlanMeta
      import yaml
      meta = PlanMeta.model_validate(yaml.safe_load((FIXTURE_DIR / "_meta.yaml").read_text()))
      assert meta.plan == "2026-05-09-fixture-minimal"
      assert meta.target_repo == "derio-net/superpowers-for-vk"
      assert meta.vk_version == ">=2.0.0,<3.0.0"
      assert meta.parent_plan is None
      assert meta.origin_items == []
  ```
  Run: `uv run pytest tests/unit/test_v2_parse.py::test_planmeta_loads_minimal_fixture -q` — expect ImportError (PlanMeta doesn't exist).

- [x] **Step 4: Implement `PlanMeta` pydantic model**
  Edit `src/vk/v2/types.py`:
  BEGIN: src/vk/v2/types.py
  ```python
  from __future__ import annotations
  from typing import Literal
  from pydantic import BaseModel, ConfigDict, Field


  class OriginItem(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      id: int
      item: str
      source: str
      track: Literal["development", "operations", "decision"]


  class PlanMeta(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      schema_version: Literal[2]
      plan: str
      spec: str | None = None
      target_repo: str
      vk_version: str
      created: str  # YYYY-MM-DD; not parsed to date for round-trip stability
      parent_plan: str | None = None
      prior_rework: str | None = None
      origin_items: list[OriginItem] = Field(default_factory=list)
  ```
  END: src/vk/v2/types.py
  Re-run Step 3's test: green.

- [x] **Step 5: Test PlanMeta rejects bad input**
  Append to `test_v2_parse.py`:
  ```python
  def test_planmeta_rejects_missing_required():
      from vk.v2.types import PlanMeta
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          PlanMeta.model_validate({"schema_version": 2, "plan": "x"})

  def test_planmeta_rejects_extra_field():
      from vk.v2.types import PlanMeta
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          PlanMeta.model_validate({
              "schema_version": 2, "plan": "x", "target_repo": "o/r",
              "vk_version": ">=2", "created": "2026-05-09",
              "extra_field": "boom",
          })
  ```
  Run: green.

- [x] **Step 6: Test PhaseDoc loads minimal fixture**
  Append:
  ```python
  def test_phasedoc_loads_minimal_fixture():
      from vk.v2.types import PhaseDoc
      import yaml
      doc = PhaseDoc.model_validate(yaml.safe_load((FIXTURE_DIR / "01.yaml").read_text()))
      assert doc.phase.number == 1
      assert doc.phase.tag == "agentic"
      assert doc.phase.depends_on == ()
      assert doc.tasks[0].steps[0].id == "P1.T1.S1"
      assert doc.state.steps["P1.T1.S1"].state == " "
  ```
  Run: ImportError.

- [x] **Step 7: Implement `PhaseDoc`, `Task`, `Step`, `PhaseStateBlock`, `StepState`, `Completion`**
  Append to `src/vk/v2/types.py`:
  ```python
  class Step(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      id: str = Field(pattern=r"^P\d+\.T\d+\.S\d+$")
      text: str


  class Task(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      number: int
      title: str
      steps: tuple[Step, ...]


  class PhaseHeader(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      number: int
      title: str
      tag: Literal["agentic", "manual"]
      depends_on: tuple[int, ...] = ()
      tracking_issue: str | None = None


  class StepState(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      state: Literal[" ", "x", "-"]
      ticked_at: str | None = None
      note: str | None = None


  class Completion(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      at: str | None = None
      note: str | None = None
      observed_prs: tuple[str, ...] = ()


  class PhaseStateBlock(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      steps: dict[str, StepState]
      completion: Completion


  class PhaseDoc(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid")
      schema_version: Literal[2]
      phase: PhaseHeader
      tasks: tuple[Task, ...]
      state: PhaseStateBlock
  ```
  Run Step 6's test: green.

- [x] **Step 8: Test cross-validation — state.steps keys match step ids**
  Append:
  ```python
  def test_phasedoc_rejects_state_key_mismatch():
      from vk.v2.types import PhaseDoc
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          PhaseDoc.model_validate({
              "schema_version": 2,
              "phase": {"number": 1, "title": "x", "tag": "agentic"},
              "tasks": [{"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]}],
              "state": {
                  "steps": {"P1.T1.S99": {"state": " "}},
                  "completion": {"observed_prs": []}
              }
          })
  ```
  Run: red — pydantic doesn't enforce this yet.

- [x] **Step 9: Add cross-validator to PhaseDoc**
  Add `from pydantic import model_validator` to imports. Add to `PhaseDoc`:
  ```python
      @model_validator(mode="after")
      def _state_keys_match_steps(self) -> "PhaseDoc":
          step_ids = {s.id for t in self.tasks for s in t.steps}
          state_keys = set(self.state.steps.keys())
          if step_ids != state_keys:
              missing = step_ids - state_keys
              extra = state_keys - step_ids
              raise ValueError(
                  f"state.steps keys must match task step ids exactly. "
                  f"missing={sorted(missing)} extra={sorted(extra)}"
              )
          return self
  ```
  Run Step 8's test: green.

### Task 2: `vk.v2.parse`

- [x] **Step 1: Test parse() round-trips minimal fixture**
  Append to `test_v2_parse.py`:
  ```python
  def test_parse_minimal_fixture():
      from vk.v2 import parse
      plan = parse(FIXTURE_DIR)
      assert plan.meta.plan == "2026-05-09-fixture-minimal"
      assert len(plan.phases) == 1
      assert plan.phases[0].phase.number == 1
      assert plan.dir == FIXTURE_DIR
  ```
  Run: ImportError.

- [x] **Step 2: Implement `vk.v2.parse`**
  Create `src/vk/v2/parse.py`:
  BEGIN: src/vk/v2/parse.py
  ```python
  from __future__ import annotations
  import re
  from dataclasses import dataclass
  from pathlib import Path
  import yaml
  from vk.v2.types import PlanMeta, PhaseDoc


  class PlanSchemaError(Exception):
      pass


  @dataclass(frozen=True)
  class Plan:
      dir: Path
      meta: PlanMeta
      phases: tuple[PhaseDoc, ...]

      @property
      def prose_path(self) -> Path:
          return self.dir / "_prose.md"


  _PHASE_FILE_RE = re.compile(r"^(\d{2,})\.yaml$")


  def parse(plan_dir: Path) -> Plan:
      plan_dir = Path(plan_dir).resolve()
      if not plan_dir.is_dir():
          raise PlanSchemaError(f"not a directory: {plan_dir}")
      meta_path = plan_dir / "_meta.yaml"
      if not meta_path.exists():
          raise PlanSchemaError(
              f"{plan_dir} is not a v2 plan (no _meta.yaml). "
              f"Run `vk migrate v1-to-v2` first if migrating from v1."
          )
      try:
          meta = PlanMeta.model_validate(yaml.safe_load(meta_path.read_text()))
      except Exception as e:
          raise PlanSchemaError(f"_meta.yaml: {e}") from e

      phase_files = sorted(
          (p for p in plan_dir.iterdir() if _PHASE_FILE_RE.match(p.name)),
          key=lambda p: int(_PHASE_FILE_RE.match(p.name).group(1)),
      )
      phases: list[PhaseDoc] = []
      for f in phase_files:
          try:
              phases.append(PhaseDoc.model_validate(yaml.safe_load(f.read_text())))
          except Exception as e:
              raise PlanSchemaError(f"{f.name}: {e}") from e

      return Plan(dir=plan_dir, meta=meta, phases=tuple(phases))
  ```
  END: src/vk/v2/parse.py

- [x] **Step 3: Wire parse() into `vk.v2.__init__`**
  Edit `src/vk/v2/__init__.py`:
  ```python
  from vk.v2.parse import parse, Plan, PlanSchemaError
  from vk.v2.types import (
      PlanMeta, PhaseDoc, Task, Step, PhaseHeader,
      PhaseStateBlock, StepState, Completion, OriginItem,
  )

  __all__ = [
      "parse", "Plan", "PlanSchemaError",
      "PlanMeta", "PhaseDoc", "Task", "Step", "PhaseHeader",
      "PhaseStateBlock", "StepState", "Completion", "OriginItem",
  ]
  ```
  Run Task 2 Step 1's test: green.

- [x] **Step 4: Test parse() rejects v1 plan**
  Append:
  ```python
  def test_parse_rejects_v1_plan(tmp_path):
      from vk.v2 import parse, PlanSchemaError
      v1 = tmp_path / "v1-plan"
      v1.mkdir()
      (v1 / "looks-like-a-plan.md").write_text("# old")
      with pytest.raises(PlanSchemaError, match="not a v2 plan"):
          parse(v1)
  ```
  Run: green.

- [x] **Step 5: Test parse() enforces vk_version constraint**
  Add fixture `tests/unit/fixtures/v2_plan_future/_meta.yaml` with `vk_version: ">=99.0.0"`, plus `_prose.md` and `01.yaml`. Append:
  ```python
  def test_parse_enforces_vk_version(monkeypatch):
      from vk.v2 import parse, PlanSchemaError
      from vk.v2 import parse as parse_module
      monkeypatch.setattr(parse_module, "INSTALLED_VK_VERSION", "1.4.5")
      future = Path(__file__).parent / "fixtures" / "v2_plan_future"
      with pytest.raises(PlanSchemaError, match="vk_version"):
          parse(future)
  ```
  Run: red.

- [x] **Step 6: Add version-constraint enforcement in parse()**
  Edit `src/vk/v2/parse.py`:
  - Add `import importlib.metadata`
  - Add `from packaging.specifiers import SpecifierSet`
  - Add `from packaging.version import Version`
  - Add module-level `INSTALLED_VK_VERSION = importlib.metadata.version("vk")`
  - Inside `parse()`, after meta validation:
    ```python
    spec = SpecifierSet(meta.vk_version)
    if Version(INSTALLED_VK_VERSION) not in spec:
        raise PlanSchemaError(
            f"plan {plan_dir} requires vk_version {meta.vk_version} "
            f"but installed is {INSTALLED_VK_VERSION}. "
            f"To upgrade: pip install --user --upgrade "
            f'"vk @ git+https://github.com/derio-net/superpowers-for-vk@v<version>"'
        )
    ```
  - Add `packaging>=24` to `pyproject.toml` dependencies.
  Run: `uv sync && uv run pytest tests/unit/test_v2_parse.py -q` — green.

### Task 3: Round-trip and regression check

- [x] **Step 1: Test round-trip — parse, serialize back, parse again equals original**
  Append:
  ```python
  def test_parse_roundtrip(tmp_path):
      from vk.v2 import parse
      import yaml, shutil
      shutil.copytree(FIXTURE_DIR, tmp_path / "copy")
      plan = parse(tmp_path / "copy")
      (tmp_path / "copy" / "_meta.yaml").write_text(yaml.safe_dump(plan.meta.model_dump()))
      (tmp_path / "copy" / "01.yaml").write_text(yaml.safe_dump(plan.phases[0].model_dump()))
      reparsed = parse(tmp_path / "copy")
      assert reparsed.meta == plan.meta
      assert reparsed.phases == plan.phases
  ```
  Run: green.

- [x] **Step 2: Verify v1 tests still pass**
  Run `uv run pytest -q --no-cov` — every existing v1 test still green.

- [x] **Step 3: Verify ruff and mypy clean on new code**
  Run `uv run ruff check src/vk/v2/ tests/unit/test_v2_parse.py` — clean.
  Run `uv run mypy src/vk/v2/` — clean.

- [x] **Step 4: Commit Phase 1**
  Stage: `src/vk/v2/`, `tests/unit/test_v2_parse.py`, `tests/unit/fixtures/v2_plan_minimal/`, `tests/unit/fixtures/v2_plan_future/`, `pyproject.toml`, `uv.lock`.
  Message:
  ```
  feat(v2): pydantic schemas + parse() — Phase 1 of v2 library

  Lives under src/vk/v2/. v1 code untouched. Loads plan-as-folder
  format defined in 2026-05-06 spec; refuses v1 plans with actionable
  error; enforces vk_version constraint at parse time.
  ```

---

## Phase 2: Library projection chain [agentic]
**Depends on:** Phase 1

**Phase goal:** `render(plan, observed) -> RenderedState` is a pure function; `observe(plan, gh) -> GhState` queries gh; `diff(rendered, observed) -> Diff` is pure; `apply(diff, gh, *, dry_run, yes) -> ApplyResult` mutates gh idempotently. Every projection rule from spec §"Rendering" implemented and table-tested.

**Done when:**
- `pytest tests/unit/test_v2_render.py tests/unit/test_v2_observe.py tests/unit/test_v2_diff.py tests/unit/test_v2_apply.py -q` green
- `apply(diff, gh, dry_run=True)` returns mutations; with `dry_run=False` and a fake `GhClient`, recorded calls match expectations
- v1 tests still pass

### Task 1: Renderer (pure)

- [x] **Step 1: Define `RenderedState`, `RenderedIssue`, `GhState`, `PhaseObservation`, `PrObservation`**
  Create `src/vk/v2/states.py` with frozen dataclasses per spec §"Rendering" and §"Observing". No methods. All fields typed.

- [x] **Step 2: Test `render()` for the simplest case (one undispatched agentic phase, no observation)**
  Create `tests/unit/test_v2_render.py`:
  ```python
  from vk.v2 import parse
  from vk.v2.render import render
  from vk.v2.states import GhState
  from pathlib import Path

  FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

  def test_render_undispatched_phase_yields_create_intent():
      plan = parse(FIXTURE)
      observed = GhState(phases={})
      rendered = render(plan, observed)
      assert 1 in rendered.issue_per_phase
      issue = rendered.issue_per_phase[1]
      assert issue.state == "OPEN"
      assert "spec:vk-rebuild-state-machine-design" in issue.labels
      assert "plan:2026-05-09-fixture-minimal" in issue.labels
      assert "phase:1" in issue.labels
      assert "vk-ready" in issue.labels
      assert rendered.archive_decision is False
  ```
  Run: ImportError.

- [x] **Step 3: Implement `render()` skeleton + body template**
  Create `src/vk/v2/render.py`:
  - `_render_body(phase, plan) -> str` — static template per spec §"Rendering" (tracking block + Instruction/Workspace/Dependencies sections)
  - `_lifecycle_label(phase, observation) -> str | None` — implements the table from spec
  - `_render_one_phase(phase, plan, observation) -> RenderedIssue`
  - `render(plan, observed) -> RenderedState`
  Run Step 2: green.

- [x] **Step 4: Test lifecycle label projection — table-driven**
  Append:
  ```python
  import pytest
  from vk.v2.states import PhaseObservation, PrObservation

  @pytest.mark.parametrize("obs,expected_label", [
      (PhaseObservation(issue_state="OPEN", issue_labels=frozenset(), issue_assignees=(), linked_prs=()), "vk-ready"),
      (PhaseObservation(issue_state="OPEN", issue_labels=frozenset(), issue_assignees=("claude-bot",), linked_prs=()), "in-progress"),
      (PhaseObservation(issue_state="OPEN", issue_labels=frozenset(), issue_assignees=(),
                        linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=True, ci="PASS"),)), "in-progress"),
      (PhaseObservation(issue_state="OPEN", issue_labels=frozenset(), issue_assignees=(),
                        linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),)), "pr-ready"),
  ])
  def test_lifecycle_label_projection(obs, expected_label):
      from vk.v2.render import _lifecycle_label
      from vk.v2 import parse
      plan = parse(FIXTURE)
      assert _lifecycle_label(plan.phases[0], obs) == expected_label
  ```
  Run: red (some cases).

- [x] **Step 5: Implement lifecycle-label projection table**
  Per spec §"Rendering". Cover: vk-ready / manual / in-progress / pr-ready / None.
  Run Step 4: green.

- [x] **Step 6: Test phase-completion projection — agentic**
  Append:
  ```python
  def test_agentic_phase_complete_when_all_steps_ticked_and_pr_merged():
      from vk.v2.render import _phase_complete
      from vk.v2 import parse
      plan = parse(FIXTURE)
      observed_open_pr = PhaseObservation(
          issue_state="OPEN", issue_labels=frozenset(), issue_assignees=(),
          linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),)
      )
      assert _phase_complete(plan.phases[0], observed_open_pr) is False
      ticked_phase = plan.phases[0].model_copy(update={
          "state": plan.phases[0].state.model_copy(update={
              "steps": {"P1.T1.S1": plan.phases[0].state.steps["P1.T1.S1"].model_copy(update={"state": "x"})}
          })
      })
      observed_merged = PhaseObservation(
          issue_state="OPEN", issue_labels=frozenset(), issue_assignees=(),
          linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),)
      )
      assert _phase_complete(ticked_phase, observed_merged) is True
  ```
  Run: red.

- [x] **Step 7: Implement `_phase_complete()` per spec rules**
  Agentic: completion.at OR (all steps ticked AND merged PR observed AND no open PR). Manual: completion.at AND completion.note required; steps optional.
  Run Step 6: green.

- [x] **Step 8: Test archive_decision = all phases complete**
  Add `tests/unit/fixtures/v2_plan_two_phase/` with two phases. Both complete → archive=True; one incomplete → archive=False.

- [x] **Step 9: Implement and verify**
  Run: green.

- [x] **Step 10: Test render() drift warnings (3 cases per spec)**
  - Steps all ticked, PR not merged → warning
  - PR merged, steps unticked → warning
  - Issue closed, plan says incomplete → warning

- [x] **Step 11: Implement drift warnings in render()**
  Add `Warnings` field (tuple of strings) to `RenderedState`. Populate in `render()`. Run: green.

### Task 2: Observer (gh-API-backed)

- [x] **Step 1: Define `GhClient` Protocol**
  Create `src/vk/v2/ghclient.py`:
  ```python
  from typing import Protocol

  class GhClient(Protocol):
      def view_issue(self, repo: str, number: int) -> dict: ...
      def list_linked_prs(self, repo: str, issue_number: int) -> list[dict]: ...
      def view_pr(self, repo: str, number: int) -> dict: ...
      def edit_issue_labels(self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]) -> None: ...
      def edit_issue_state(self, repo: str, number: int, *, state: str, reason: str | None = None) -> None: ...
      def edit_issue_body(self, repo: str, number: int, body: str) -> None: ...
      def create_issue(self, repo: str, *, title: str, body: str, labels: frozenset[str]) -> str: ...
      def ensure_labels(self, repo: str, labels: list) -> None: ...
  ```

- [x] **Step 2: Implement `FakeGhClient` for tests**
  Create `tests/unit/fakes.py` with `FakeGhClient`: in-memory state, records calls, supports preconditions.

- [x] **Step 3: Test `observe()` for one-phase plan with no tracking_issue**
  Create `tests/unit/test_v2_observe.py`:
  ```python
  from vk.v2 import parse
  from vk.v2.observe import observe
  from tests.unit.fakes import FakeGhClient

  def test_observe_undispatched_phase_returns_no_observation():
      plan = parse(FIXTURE)
      gh = FakeGhClient()
      observed = observe(plan, gh)
      assert observed.phases == {}
  ```
  Run: red.

- [x] **Step 4: Implement `observe()` skeleton**
  Create `src/vk/v2/observe.py`. For each phase with `tracking_issue`: parse repo + number, query gh, build PhaseObservation. Phases without: skip. Run: green.

- [x] **Step 5: Test `observe()` for dispatched phase with merged PR**
  Use a fixture phase yaml with `tracking_issue` set; FakeGhClient pre-loaded with corresponding Issue + PR data. Assert `observed.phases[1].linked_prs[0].merged is True`.

- [x] **Step 6: Implement linked-PR discovery**
  GraphQL `closingIssuesReferences` first; title-pattern fallback. Run: green.

### Task 3: Differ + Applier

- [x] **Step 1: Define `Diff`, `IssueLabelChange`, `IssueStateChange`, `IssueBodyChange`, `IssueCreate`, `RepoLabelEnsure`**
  In `src/vk/v2/diff.py`. All frozen.

- [x] **Step 2: Test `diff()` — undispatched phase yields IssueCreate**
  Create `tests/unit/test_v2_diff.py`:
  ```python
  def test_diff_undispatched_yields_create():
      plan = parse(FIXTURE)
      observed = GhState(phases={})
      rendered = render(plan, observed)
      d = diff(rendered, observed, plan=plan)
      creates = [m for m in d.mutations if isinstance(m, IssueCreate)]
      assert len(creates) == 1
      assert creates[0].phase_number == 1
      assert creates[0].labels >= frozenset({"vk-ready", "phase:1"})
  ```
  Run: red.

- [x] **Step 3: Implement `diff()`**
  For each phase: if no tracking_issue and no observation → IssueCreate; if tracking_issue and observation → compare labels, body, open/closed, emit changes. Always emit RepoLabelEnsure for the target_repo. Run: green.

- [x] **Step 4: Test diff is idempotent — re-diff after apply yields no mutations**
  Append a placeholder test that runs after the applier exists.

- [x] **Step 5: Test `apply()` honors managed-labels-only rule**
  - Pre-load FakeGhClient Issue with operator-added label `good-first-issue`
  - render → diff → apply
  - Assert `good-first-issue` was NOT removed; only managed labels (vk-*/spec:/plan:/phase:) touched

- [x] **Step 6: Implement `apply()`**
  Create `src/vk/v2/apply.py`. Iterate mutations; for label changes, intersect with `MANAGED_LABEL_PREFIXES = {"vk-", "spec:", "plan:", "phase:"}` plus the lifecycle names. `dry_run=True`: return mutations without executing. `yes=False` and a destructive op: prompt via `typer.confirm` if invoked from CLI. Run: green.

- [x] **Step 7: Test `apply()` dry-run returns mutations without calling gh**
  Append: `apply(diff, fake_gh, dry_run=True, yes=True)` → fake_gh has zero recorded calls.

- [x] **Step 8: Test `apply()` is atomic-per-mutation, accumulates failures**
  - Configure FakeGhClient to fail on the second mutation
  - Apply 3 mutations
  - Assert: m1 succeeded, m2 failed (recorded in result), m3 succeeded

- [x] **Step 9: Implement failure accumulation**
  Run: green.

- [x] **Step 10: Run idempotency end-to-end**
  Re-run Step 4's test. Apply → re-observe → re-diff → assert empty mutations. Green.

- [x] **Step 11: Verify ruff, mypy, full test suite**
  ```
  uv run ruff check src/vk/v2/ tests/unit/test_v2_*.py
  uv run mypy src/vk/v2/
  uv run pytest -q --no-cov
  ```
  All green.

- [x] **Step 12: Commit Phase 2**
  ```
  feat(v2): renderer + observer + differ + applier — Phase 2

  Pure render() and diff(); observe() reads gh; apply() mutates gh
  idempotently with managed-labels-only rule and per-mutation
  failure accumulation. FakeGhClient added for tests.
  ```

---

## Phase 3: CLI surface + migration tool + GHA workflow [agentic]
**Depends on:** Phase 2

**Phase goal:** All v2 commands operational. Migration tool round-trips v1 plans to v2 folders for the test fixtures. GHA workflow file lints clean. Coexists with v1 commands.

**Done when:**
- `vk apply --help`, `vk plan create --help`, `vk plan edit --help`, `vk plan rework --help`, `vk plan rework-add --help`, `vk plan rework-list --help`, `vk pickup --help`, `vk spec status --help`, `vk migrate v1-to-v2 --help` all return clean help text
- `pytest tests/unit/test_v2_cli.py tests/unit/test_v2_migrate.py tests/unit/test_v2_spec.py tests/integration/test_v2_apply_e2e.py -q` green
- `actionlint .github/workflows/vk-spec-status.yml` clean (or document if actionlint unavailable)
- v1 tests still all pass

### Task 1: `vk apply` command + e2e

- [x] **Step 1: Test e2e — fixture plan → vk apply --dry-run → assert mutations**
  Create `tests/integration/test_v2_apply_e2e.py`. Use a tmp git repo with the minimal v2 fixture plan. Invoke `vk apply <plan-dir> --dry-run` via CliRunner. Assert stdout shows the IssueCreate mutation.
  Run: red (no apply command yet).

- [x] **Step 2: Implement `vk apply` typer command**
  Create `src/vk/v2/commands/apply_cmd.py`. Wire into `src/vk/cli.py`:
  ```python
  from vk.v2.commands.apply_cmd import apply_app
  app.add_typer(apply_app, name="apply")
  ```
  Run Step 1: green.

- [x] **Step 3: Test `vk apply --all` walks plans/**
  Run: red.

- [x] **Step 4: Implement `--all`** — find plan folders under `docs/superpowers/plans/`, apply each. Run: green.

### Task 2: `vk plan create / edit / rework / rework-add / rework-list`

- [x] **Step 1: Test `vk plan create` scaffolds a folder + appends spec row**
  Use a tmp repo with a stub spec containing `## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|---|---|---|---|`. Invoke `vk plan create --from-spec <spec> --slug test-plan --target-repo derio-net/x`. Assert: folder created with _meta + _prose; spec table has new row.

- [x] **Step 2: Implement `vk.plan.create()` library function**
  Per spec §"Plan editing — vk.plan.*". Atomically: write _meta.yaml, write _prose.md, write empty 01.yaml stub, append row to spec's Implementation Plans table.

- [x] **Step 3: Implement `vk plan create` CLI command**
  Run Step 1: green.

- [x] **Step 4: Test `vk plan edit --tick P1.T1.S1`**
  Tick a step in a fixture plan. Assert state YAML changed; ticked_at populated; idempotent on re-tick.

- [x] **Step 5: Implement `vk plan edit --tick`**
  Library function `vk.plan.tick()`; CLI wrapper. Stages via `git add` after write. Run: green.

- [x] **Step 6: Test `vk plan edit --complete-phase`**
  - Manual phase requires `--note`
  - Agentic phase refuses if any step state == " "

- [x] **Step 7: Implement `vk.plan.complete_phase()` and CLI**
  Run: green.

- [x] **Step 8: Test `vk plan rework` scaffolds sibling folder + spec row + parent_plan field**
  Fixture: a "completed" v2 plan; invoke `vk plan rework <parent>`; assert sibling folder exists with `_meta.parent_plan` set and Implementation Plans table has the rework row.

- [x] **Step 9: Implement `vk.plan.rework_create()` and CLI**
  Per spec §"Rework plans". Includes the cross-directory N-collision check from v1. Run: green.

- [x] **Step 10: Test `vk plan rework-add`**
  Append an origin item; assert `_meta.origin_items` has the new entry with auto-incremented id; track validation rejects bad values.

- [x] **Step 11: Implement `vk.plan.rework_add_origin()` and CLI**
  Run: green.

- [x] **Step 12: Test `vk plan rework-list`**
  Glob plan folders; filter by `_meta.parent_plan`; aggregate status from phase yamls. Assert columns match spec.

- [x] **Step 13: Implement `vk.plan.rework_list()` and CLI**
  Run: green.

- [x] **Step 14: Test `vk plan self-review` lints**
  - Cyclic depends_on → flagged
  - Missing tracking_issue on a phase with state changes → flagged
  - Manual phase with all steps ticked but no completion.note → flagged

- [x] **Step 15: Implement `vk.plan.self_review()` and CLI**
  Run: green.

### Task 3: `vk pickup`

- [x] **Step 1: Test `vk pickup` outputs full step text + PR title template + dependency reminder**
  Run: red.

- [x] **Step 2: Implement `vk pickup`**
  Per spec — output structured markdown for the agent. Includes the PR title template `[<repo>] <plan-slug> · Phase N/M · <subject>`. Run: green.

### Task 4: `vk spec status` + `--all`

- [x] **Step 1: Test `vk.spec.parse()` extracts Implementation Plans table without Status column**
  Use a fixture spec file; assert `SpecMeta.plans` has the right PlanRefs.

- [x] **Step 2: Implement `vk.spec.parse()`**
  Create `src/vk/v2/spec.py`. Run: green.

- [x] **Step 3: Test `vk.spec.compute_status()` aggregates across plans**
  Fixture: two plan folders, one Complete, one half-done. Assert SpecStatus shows `1/2 plans complete` and percent calculation.

- [x] **Step 4: Implement `vk.spec.compute_status()`**
  Walk PlanRefs; for each, read plan dir (local fs path-based for now; cross-repo gh API is documented for Plan 3). Aggregate. Run: green.

- [x] **Step 5: Test `vk.spec.render_status_md()`**
  Snapshot test: known input → expected markdown comment body (matches the GHA comment example in the spec).

- [x] **Step 6: Implement `render_status_md()`**
  Run: green.

- [x] **Step 7: Implement `vk spec status` CLI**
  Print rendered markdown.

- [x] **Step 8: Implement `vk spec status --all`**
  Walk `docs/superpowers/specs/`; print one block per spec.

### Task 5: `vk migrate v1-to-v2`

- [x] **Step 1: Test migrate converts a sample v1 plan to v2 folder**
  - Tmp v1 plan markdown with phases, tasks, steps, tracking comments
  - Invoke `vk migrate v1-to-v2 --dry-run` from the tmp repo
  - Assert stdout shows expected file moves
  - Invoke `vk migrate v1-to-v2 --yes`
  - Assert: folder created with _meta, _prose, 01.yaml; original .md moved to .v1-archive; new folder parses cleanly via `vk.v2.parse`

- [x] **Step 2: Implement migrate skeleton**
  Create `src/vk/v2/migrate.py`. For each .md in plans/ + archived-plans/:
  - Parse via v1 parser
  - Extract per-spec migration mapping
  - Write v2 folder
  - Move .md to .v1-archive
  Run Step 1: green.

- [x] **Step 3: Test migrate fails loud on per-phase target_repo override**
  v1 plan with phases declaring different `**Target repo:**` values → migration fails with clear error.

- [x] **Step 4: Implement the cross-target-repo loud failure**
  Per spec §"Migration" step 2. Run: green.

- [x] **Step 5: Test migrate --skip-in-progress (default)**
  - Tmp repo has two plans: one Status=Complete, one Status=In Progress
  - `vk migrate v1-to-v2 --yes`
  - Assert: Complete migrated; In Progress untouched; warning printed about the skipped plan

- [x] **Step 6: Implement `--skip-in-progress` (default true)**
  Add `--include-in-progress` opt-in flag. Run: green.

- [x] **Step 7: Test migrate handles v1 rework plans**
  Tmp repo with a `*-rework-N.md` v1 file (with Origin table, parent_plan reference). Migrate. Assert: v2 rework folder has `_meta.parent_plan`, `_meta.origin_items` populated from Origin table.

- [x] **Step 8: Implement v1-rework parsing in migrate**
  Reuse existing `src/vk/plan/rework.py:parse_origin_table()`. Run: green.

- [x] **Step 9: Test migrate updates spec files (drops Status column, points File at folders)**
  Tmp spec with Implementation Plans table including Status column. Migrate. Assert: spec table has no Status column; File cells point to folder paths.

- [x] **Step 10: Implement spec-file rewrite**
  Run: green.

### Task 6: GitHub Action workflow file

- [x] **Step 1: Write `.github/workflows/vk-spec-status.yml`**
  Reusable workflow using bash/gh CLI (no inline JS), to keep the file simple and reviewable.
  BEGIN: .github/workflows/vk-spec-status.yml
  ```
  name: vk-spec-status
  on:
    workflow_call:
  jobs:
    status:
      if: github.event.pull_request.merged == true
      runs-on: ubuntu-latest
      permissions:
        pull-requests: write
        contents: read
      steps:
        - uses: actions/checkout@v4
          with:
            fetch-depth: 0
        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"
        - name: Install vk
          run: pip install --user "vk @ git+https://github.com/derio-net/superpowers-for-vk@v2.0.0"
        - name: Find specs touched by plan changes
          id: affected
          shell: bash
          env:
            BASE_SHA: ${{ github.event.pull_request.base.sha }}
            HEAD_SHA: ${{ github.event.pull_request.merge_commit_sha }}
          run: |
            set -euo pipefail
            mapfile -t plan_dirs < <(
              git diff --name-only "$BASE_SHA...$HEAD_SHA" \
              | grep -E '^docs/superpowers/(plans|archived-plans)/[^/]+/' \
              | sed -E 's|^(docs/superpowers/(plans\|archived-plans)/[^/]+)/.*|\1|' \
              | sort -u
            )
            specs=()
            for spec in docs/superpowers/specs/*.md; do
              [ -f "$spec" ] || continue
              for d in "${plan_dirs[@]:-}"; do
                [ -z "$d" ] && continue
                if grep -q -F "$d" "$spec"; then
                  specs+=("$spec")
                  break
                fi
              done
            done
            printf 'specs=%s\n' "${specs[*]:-}" >> "$GITHUB_OUTPUT"
        - name: Build status comment
          if: steps.affected.outputs.specs != ''
          shell: bash
          run: |
            set -euo pipefail
            : > /tmp/status.md
            for spec in ${{ steps.affected.outputs.specs }}; do
              vk spec status "$spec" >> /tmp/status.md
              printf '\n\n---\n\n' >> /tmp/status.md
            done
        - name: Post comment
          if: steps.affected.outputs.specs != ''
          shell: bash
          env:
            GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          run: |
            gh pr comment "${{ github.event.pull_request.number }}" --body-file /tmp/status.md
  ```
  END: .github/workflows/vk-spec-status.yml

- [x] **Step 2: Add a thin wrapper workflow at `.github/workflows/_pr_spec_status.yml` for this repo's own use**
  ```
  name: PR spec status (self)
  on:
    pull_request:
      types: [closed]
  jobs:
    status:
      uses: ./.github/workflows/vk-spec-status.yml
  ```

- [x] **Step 3: Lint the workflow files**
  ```
  command -v actionlint >/dev/null && actionlint .github/workflows/vk-spec-status.yml .github/workflows/_pr_spec_status.yml
  ```
  If actionlint not installed, document and skip.

### Task 7: Final integration

- [x] **Step 1: Full e2e test — fixture plan, dispatch via apply, simulated state changes, complete**
  Add `tests/integration/test_v2_full_lifecycle.py`. Use FakeGhClient + tmp git repo.

- [x] **Step 2: Run full test suite + linters**
  ```
  uv run ruff format src/ tests/
  uv run ruff check src/ tests/
  uv run mypy src/vk/v2/
  uv run pytest -q --no-cov
  ```
  All green.

- [x] **Step 3: Commit Phase 3**
  ```
  feat(v2): CLI surface, migration tool, GHA workflow — Phase 3

  All v2 commands operational alongside v1. Migration tool round-trips
  v1 plans to v2 folders (including rework Origin tables and per-phase
  target_repo loud-failure). GHA workflow file lints clean.
  ```

---

## Phase 4: Retire v1 + skill updates [agentic]
**Depends on:** Phase 3

**Phase goal:** Delete every v1 module and v1 test listed in spec §"v1 code retirement"; update the four `vk-*` skill files to call only v2 commands. After this phase, `vk --help` shows v2 commands only; `pytest -q` passes.

**Done when:**
- All files in spec's "v1 code retirement" table either deleted or replaced
- `grep -rn "vk progress\|vk dispatch\|vk admin\|vk issue " skills/ src/` returns nothing
- `vk --help` shows v2 commands only
- `pytest -q --no-cov` passes
- `ruff check && mypy src/` clean

### Task 1: Delete v1 source modules + tests

- [x] **Step 1: Move v1 modules out of `src/vk/`** — `git rm` per spec retirement table
  ```
  git rm src/vk/plan/parser.py src/vk/plan/models.py src/vk/plan/format.py \
         src/vk/plan/writer.py src/vk/plan/convert.py src/vk/plan/validate.py \
         src/vk/plan/rework.py src/vk/plan/filename.py \
         src/vk/spec_index.py \
         src/vk/commands/progress_cmd.py src/vk/commands/dispatch_cmd.py \
         src/vk/commands/admin_cmd.py src/vk/commands/execute_cmd.py \
         src/vk/commands/issue_cmd.py \
         src/vk/commands/dispatch_body_validator.py
  ```
  (`src/vk/labels.py` stays — registry preserved; `src/vk/gh.py` stays.)

- [x] **Step 2: Delete v1 tests** — `git rm`
  ```
  git rm tests/unit/test_plan_parser.py tests/unit/test_plan_writer.py \
         tests/unit/test_plan_validate.py tests/unit/test_plan_loose_format.py \
         tests/unit/test_plan_convert.py tests/unit/test_rework.py \
         tests/unit/test_spec_index.py tests/unit/test_admin_*.py \
         tests/unit/test_execute_*.py tests/unit/test_issue_cmd.py \
         tests/unit/test_dispatch_body.py tests/unit/test_dispatch_body_validator.py \
         tests/unit/test_progress_reconcile.py tests/unit/test_audit.py \
         tests/unit/test_self_review_multi_repo.py tests/unit/test_filename.py \
         tests/unit/test_format.py tests/unit/test_models.py \
         tests/integration/test_dispatch.py tests/integration/test_plan_execute.py \
         tests/integration/test_plan_rework.py
  ```

- [x] **Step 3: Update `src/vk/cli.py`** — remove imports/registrations of deleted command modules
  Open `src/vk/cli.py`. Remove every `add_typer` and `from vk.commands.X` line for the deleted commands. Keep `apply_app`, `plan_app` (v2 version), `pickup_app`, `spec_app`, `migrate_app`.

- [x] **Step 4: Move v2 commands from `vk.v2.commands` to `vk.commands`** (the v2 namespace was a coexistence scaffold; collapse it now)
  ```
  git mv src/vk/v2/commands/* src/vk/commands/
  for f in src/vk/v2/*.py; do
    [ "$(basename "$f")" = "__init__.py" ] && continue
    git mv "$f" "src/vk/$(basename "$f")"
  done
  rmdir src/vk/v2/commands src/vk/v2
  ```
  Update all imports (`from vk.v2.X` → `from vk.X`). Update tests similarly.

- [x] **Step 5: Run pytest — verify only v2 tests remain and all pass**
  ```
  uv run pytest -q --no-cov
  ```
  Green.

- [x] **Step 6: Run ruff + mypy**
  ```
  uv run ruff format src/ tests/
  uv run ruff check src/ tests/
  uv run mypy src/
  ```
  Clean.

### Task 2: Update skill files

- [x] **Step 1: Update `skills/vk-plan/SKILL.md`**
  - `vk plan new` → `vk plan create`
  - `vk plan self-review` → unchanged name; lints differ
  - `vk plan spec-index` → DELETED; spec rows are auto-written by `vk plan create` and `vk plan rework`. Remove reference.
  - Migration section reference (vk-execute) → remove.
  - Add note about v2 plan-as-folder format.

- [x] **Step 2: Update `skills/vk-dispatch/SKILL.md`**
  - `vk dispatch create` → `vk apply <plan-dir>`
  - `vk dispatch migrate` → DELETED; `vk apply` is idempotent
  - Update entire flow narrative.

- [x] **Step 3: Update `skills/vk-execute/SKILL.md`**
  - `vk execute scope` / `check-deps` → `vk pickup <plan-dir> --phase N`
  - `vk execute claim` → DELETED (no claim verb in v2)
  - `vk execute pr-opened` → DELETED (observed by next apply tick)
  - `vk execute pr-body` → `vk pickup` outputs PR title template
  - `vk execute check-step` → `vk plan edit --tick`

- [x] **Step 4: Update `skills/vk-progress/SKILL.md`**
  - `vk progress sync` / `audit` / `transition` / `board` / `create` → ALL DELETED
  - Replace with `vk apply --dry-run` (audit), `vk plan edit --complete-phase` (transition), `vk spec status --all` (board)

- [x] **Step 5: Verify skills are coherent** — read each SKILL.md after edits, ensure no dangling references

### Task 3: Confirm final state

- [x] **Step 1: `grep -rn "vk progress\|vk dispatch\|vk admin\|vk issue \|vk execute" skills/ src/`**
  Expected: zero matches.

- [x] **Step 2: `vk --help`** — confirm only v2 commands shown.

- [x] **Step 3: Commit Phase 4**
  ```
  feat(v2)!: retire v1 code and update skills — Phase 4

  Deletes all v1 modules and tests per spec retirement table.
  Updates vk-plan, vk-dispatch, vk-execute, vk-progress skill files
  to call v2 commands only. After this commit the package exposes
  only the v2 surface.

  BREAKING CHANGE: every v1 CLI command is removed. Plans must be
  in v2 folder format; v1 .md plans must be migrated via
  `vk migrate v1-to-v2` (in this same release).
  ```

---

## Phase 5: v2.0.0 release [manual]
**Depends on:** Phase 4

**Phase goal:** Tag and publish `v2.0.0`. Three version files moved in lockstep; `uv run vk --version` reports `2.0.0`; CHANGELOG entry; git tag pushed.

**Done when:**
- `uv run vk --version` outputs `2.0.0`
- `git tag` shows `v2.0.0`
- `git push --tags` succeeded
- `CHANGELOG.md` has v2.0.0 entry

### Task 1: Bump version triplet

- [ ] **Step 1: Update `pyproject.toml`** — set `[project].version = "2.0.0"`
- [ ] **Step 2: Update `.claude-plugin/plugin.json`** — set `.version = "2.0.0"`
- [ ] **Step 3: Update `.claude-plugin/marketplace.json`** — set `.plugins[0].version = "2.0.0"`
- [ ] **Step 4: Run `uv sync`** — uv.lock picks up `vk==2.0.0`
- [ ] **Step 5: Verify `uv run vk --version`** — outputs `2.0.0`

### Task 2: CHANGELOG

- [ ] **Step 1: Add v2.0.0 section to `CHANGELOG.md`**
  Brief but explicit: "BREAKING — full rewrite per 2026-05-06 spec. Plan format is now folder-based (v2.0); use `vk migrate v1-to-v2` to convert existing v1 plans. CLI surface collapses to `vk apply`, `vk plan create/edit/rework`, `vk pickup`, `vk spec status`, `vk migrate`. The bridge in willikins requires Plan 2 to migrate to v2 vk; until then it operates on consumer repos that haven't migrated."

### Task 3: Tag and push

- [ ] **Step 1: Commit Phase 5**
  ```
  release: v2.0.0 — single state machine rebuild

  Per docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md.
  ```

- [ ] **Step 2: Tag**
  ```
  git tag -a v2.0.0 -m "v2.0.0 — single state machine rebuild"
  git push --tags
  ```

- [ ] **Step 3: Verify tag visible** — `gh release view v2.0.0` (or check github.com)

---

## Phase 6: Self-migrate this repo's plans [manual]
**Depends on:** Phase 5

**Phase goal:** This repo's `docs/superpowers/plans/` and `docs/superpowers/archived-plans/` are migrated to v2 folder format using the just-released v2 plugin. Specs have Status column dropped and File cells point to folders. One PR opened, reviewed, merged.

**Done when:**
- All `*.md` plans (except this in-progress plan) converted to `<slug>/` folders
- All `.md` originals moved to `.v1-archive` siblings
- All specs in `docs/superpowers/specs/` have Status column removed and File cells updated
- `vk apply --dry-run docs/superpowers/archived-plans/<a-migrated-folder>` works
- PR merged

### Task 1: Dry-run

- [ ] **Step 1: From repo root, run dry-run**
  ```
  uv run vk migrate v1-to-v2 --dry-run
  ```
  Expected output: list of every .md plan that will be converted (excluding this in-progress plan); list of spec files that will have Status column dropped; nothing applied.

- [ ] **Step 2: Sanity-check the output**
  Verify: this plan's own file is in the SKIPPED list (because Status: In Progress). All Complete plans listed for conversion.

### Task 2: Apply

- [ ] **Step 1: Apply migration**
  ```
  uv run vk migrate v1-to-v2 --yes
  ```
  Expected output: per-plan conversion log; per-spec table-rewrite log; summary of files added/moved.

- [ ] **Step 2: Verify a sample migrated plan**
  ```
  uv run vk apply --dry-run docs/superpowers/archived-plans/<a-migrated-folder>
  ```
  Should parse cleanly; mostly "no diff" output for archived plans.

- [ ] **Step 3: Run full test suite** — ensure migration didn't break anything
  ```
  uv run pytest -q --no-cov
  ```
  Green.

### Task 3: PR + review

- [ ] **Step 1: Branch, commit, push**
  ```
  git checkout -b chore/self-migrate-v1-to-v2
  git add -A
  git commit -m "chore(plans): self-migrate v1 plans to v2 folder format"
  git push -u origin chore/self-migrate-v1-to-v2
  ```

- [ ] **Step 2: Open PR**
  ```
  gh pr create --title "chore(plans): self-migrate v1 plans to v2 folder format" \
    --body "Mechanical migration via 'vk migrate v1-to-v2'. Excludes this plan (still in progress). Spec tables updated to drop Status column. See spec 2026-05-06-vk-rebuild-state-machine-design.md."
  ```

- [ ] **Step 3: Review and merge** — operator action; once green, merge.

### Task 4: Post-completion housekeeping (documented; executed AFTER Phase 6)

After this plan reaches Status: Complete (after Phase 6's PR merges), do the final self-housekeeping:

- [ ] **Step 1: Mark this plan Status: Complete** via `vk plan edit ... --complete-phase` for any remaining unchecked steps
- [ ] **Step 2: Run migration on the now-complete plan**
  ```
  uv run vk migrate v1-to-v2 --include-in-progress --yes
  ```
- [ ] **Step 3: Open a tiny follow-up PR archiving this plan**
- [ ] **Step 4: Plan 1 is closed. Plan 2 (bridge migration in willikins) is now unblocked.**
