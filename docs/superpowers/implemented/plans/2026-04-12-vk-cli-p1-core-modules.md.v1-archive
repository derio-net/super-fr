# VK CLI Core Modules Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Complete

**Goal:** Implement all shared library modules (`src/vk/` except `commands/`) with full unit test coverage and fixture files. No CLI commands -- just the core brain that every command will depend on.
**Architecture:** Frozen dataclass AST for plans, regex-driven parser, YAML-backed config with fail-closed dispatch gate, subprocess wrappers for git/gh. All modules are pure library code tested via pytest.
**Tech Stack:** Python 3.11+, uv, pyyaml, pytest, ruff, mypy

---

## Phase 1: Config, models, format, and filename [agentic]

### Task 1: Test fixtures — configs

**Files:**
- Create: `tests/fixtures/configs/dispatch-enabled.yaml`
- Create: `tests/fixtures/configs/dispatch-false.yaml`
- Create: `tests/fixtures/configs/no-dispatch-key.yaml`
- Create: `tests/fixtures/configs/empty.yaml`
- Create: `tests/fixtures/configs/dispatch-minimal.yaml`

- [x] **Step 1: Create all five config fixture files**

Create `tests/fixtures/configs/dispatch-enabled.yaml`:

```yaml
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete

dispatch:
  target: github-issues
  owner: derio-net
  project_board: "Derio Ops"
  default_repo: derio-net/some-repo
  labels:
    agentic: vk-ready
    manual: manual
```

Create `tests/fixtures/configs/dispatch-false.yaml`:

```yaml
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete

dispatch: false
```

Create `tests/fixtures/configs/no-dispatch-key.yaml`:

```yaml
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete
```

Create `tests/fixtures/configs/empty.yaml`:

```yaml
# Intentionally empty config file
```

Create `tests/fixtures/configs/dispatch-minimal.yaml`:

```yaml
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete

dispatch: {}
```

- [x] **Step 2: Commit fixture files**

```bash
git add tests/fixtures/configs/
git commit -m "test: add config fixture files for dispatch gate truth table"
```

### Task 2: Config module — Profile, PlanConfig, HeaderConfig, DispatchConfig

**Files:**
- Create: `src/vk/config.py`
- Create: `tests/unit/test_config.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_config.py`:

```python
"""Tests for vk.config — dispatch gate truth table and profile loading."""

from pathlib import Path

import pytest

from vk.config import (
    DispatchConfig,
    HeaderConfig,
    PlanConfig,
    Profile,
    load_profile,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


# --- Dispatch gate truth table (7 cases) ---


def test_gate_file_missing(tmp_path: Path) -> None:
    """File missing -> dispatch disabled."""
    profile = load_profile(tmp_path / "nonexistent.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_no_dispatch_key() -> None:
    """File exists, no `dispatch` key -> dispatch disabled."""
    profile = load_profile(FIXTURES / "no-dispatch-key.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_false() -> None:
    """`dispatch: false` -> dispatch disabled."""
    profile = load_profile(FIXTURES / "dispatch-false.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_null(tmp_path: Path) -> None:
    """`dispatch: null` -> dispatch disabled."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("dispatch: null\n")
    profile = load_profile(cfg)
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_true_scalar(tmp_path: Path) -> None:
    """`dispatch: true` (scalar, not map) -> dispatch disabled + warning."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("dispatch: true\n")
    with pytest.warns(UserWarning, match="dispatch.*must be a map"):
        profile = load_profile(cfg)
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_empty_map() -> None:
    """`dispatch: {}` -> dispatch enabled with defaults."""
    profile = load_profile(FIXTURES / "dispatch-minimal.yaml")
    assert profile.dispatch_enabled is True
    assert profile.dispatch is not None
    assert profile.dispatch.owner == "derio-net"
    assert profile.dispatch.project_board == "Derio Ops"
    assert profile.dispatch.target == "github-issues"
    assert profile.dispatch.labels == {"agentic": "vk-ready", "manual": "manual"}


def test_gate_dispatch_full_map() -> None:
    """`dispatch: {owner: foo, ...}` -> dispatch enabled with explicit values."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.dispatch_enabled is True
    assert profile.dispatch is not None
    assert profile.dispatch.owner == "derio-net"
    assert profile.dispatch.project_board == "Derio Ops"
    assert profile.dispatch.default_repo == "derio-net/some-repo"
    assert profile.dispatch.target == "github-issues"
    assert profile.dispatch.labels == {"agentic": "vk-ready", "manual": "manual"}


# --- Format derived from dispatch ---


def test_format_flat_when_no_dispatch() -> None:
    """No dispatch -> flat format."""
    from vk.plan.format import PlanFormat

    profile = load_profile(FIXTURES / "no-dispatch-key.yaml")
    assert profile.format is PlanFormat.FLAT


def test_format_phased_when_dispatch_enabled() -> None:
    """Dispatch enabled -> phased format."""
    from vk.plan.format import PlanFormat

    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.format is PlanFormat.PHASED


# --- PlanConfig and HeaderConfig ---


def test_plan_config_defaults(tmp_path: Path) -> None:
    """Missing plan/header sections get sensible defaults."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("# minimal\n")
    profile = load_profile(cfg)
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
    assert profile.plan.save_to == "docs/superpowers/plans/"
    assert "Spec" in profile.header.required
    assert "Status" in profile.header.required


def test_plan_config_loaded() -> None:
    """Explicit plan config is loaded correctly."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
    assert profile.plan.save_to == "docs/superpowers/plans/"
    assert profile.header.required == ("Spec", "Status")
    assert "Not Started" in profile.header.status_values
    assert "In Progress" in profile.header.status_values
    assert "Complete" in profile.header.status_values


# --- Dataclass immutability ---


def test_profile_is_frozen() -> None:
    """Profile and sub-configs are immutable."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    with pytest.raises(AttributeError):
        profile.plan = PlanConfig(filename="x", save_to="y")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        profile.dispatch = None  # type: ignore[misc]


def test_empty_file_gives_defaults() -> None:
    """Empty YAML file gives all-default profile."""
    profile = load_profile(FIXTURES / "empty.yaml")
    assert profile.dispatch_enabled is False
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.config'`

- [x] **Step 3: Implement src/vk/config.py**

```python
"""Configuration loader — reads plan-config.yaml and builds a Profile.

The dispatch gate is fail-closed: missing file, missing key, `false`, `null`,
or a non-map scalar all mean dispatch is disabled.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from vk.plan.format import PlanFormat


@dataclass(frozen=True)
class PlanConfig:
    """Plan file naming and storage settings."""

    filename: str = "YYYY-MM-DD-{name}.md"
    save_to: str = "docs/superpowers/plans/"


@dataclass(frozen=True)
class HeaderConfig:
    """Required header fields and allowed status values."""

    required: tuple[str, ...] = ("Spec", "Status")
    status_values: tuple[str, ...] = ("Not Started", "In Progress", "Complete")


@dataclass(frozen=True)
class DispatchConfig:
    """GitHub Issues dispatch settings.  Present = dispatch enabled."""

    owner: str = "derio-net"
    project_board: str = "Derio Ops"
    default_repo: str = ""
    target: str = "github-issues"
    labels: dict[str, str] = field(
        default_factory=lambda: {"agentic": "vk-ready", "manual": "manual"}
    )


@dataclass(frozen=True)
class Profile:
    """Loaded plan-config profile.  Single source of truth for repo behaviour."""

    plan: PlanConfig = field(default_factory=PlanConfig)
    header: HeaderConfig = field(default_factory=HeaderConfig)
    dispatch: DispatchConfig | None = None

    @property
    def dispatch_enabled(self) -> bool:
        """Fail-closed: only True when an explicit dispatch map was loaded."""
        return self.dispatch is not None

    @property
    def format(self) -> PlanFormat:
        """Format is derived from dispatch presence (Decision D3)."""
        from vk.plan.format import PlanFormat

        return PlanFormat.PHASED if self.dispatch_enabled else PlanFormat.FLAT


def _parse_dispatch(raw: object) -> DispatchConfig | None:
    """Parse the raw dispatch value from YAML.  Returns None for disabled."""
    if raw is None:
        return None
    if raw is False:
        return None
    if raw is True:
        warnings.warn(
            "`dispatch: true` is invalid — dispatch must be a map, not a scalar. "
            "Treating as disabled.",
            UserWarning,
            stacklevel=3,
        )
        return None
    if not isinstance(raw, dict):
        return None
    # It's a map — dispatch is enabled
    return DispatchConfig(
        owner=raw.get("owner", "derio-net"),
        project_board=raw.get("project_board", "Derio Ops"),
        default_repo=raw.get("default_repo", ""),
        target=raw.get("target", "github-issues"),
        labels=raw.get("labels", {"agentic": "vk-ready", "manual": "manual"}),
    )


def _parse_plan(raw: dict[str, object] | None) -> PlanConfig:
    """Parse plan section with defaults."""
    if not raw or not isinstance(raw, dict):
        return PlanConfig()
    return PlanConfig(
        filename=str(raw.get("filename", PlanConfig.filename)),
        save_to=str(raw.get("save_to", PlanConfig.save_to)),
    )


def _parse_header(raw: dict[str, object] | None) -> HeaderConfig:
    """Parse header section with defaults."""
    if not raw or not isinstance(raw, dict):
        return HeaderConfig()
    required = raw.get("required", list(HeaderConfig.required))
    status_values = raw.get("status_values", list(HeaderConfig.status_values))
    return HeaderConfig(
        required=tuple(required) if isinstance(required, list) else HeaderConfig.required,
        status_values=tuple(status_values)
        if isinstance(status_values, list)
        else HeaderConfig.status_values,
    )


def load_profile(config_path: Path) -> Profile:
    """Load a Profile from a plan-config.yaml file.

    Returns an all-defaults Profile if the file is missing or empty.
    """
    if not config_path.exists():
        return Profile()

    text = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return Profile()

    return Profile(
        plan=_parse_plan(data.get("plan")),
        header=_parse_header(data.get("header")),
        dispatch=_parse_dispatch(data.get("dispatch")),
    )
```

- [x] **Step 4: Create src/vk/plan/__init__.py**

```python
"""Plan parsing, writing, and conversion."""
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS — all 13 tests pass (format tests will fail until format.py exists; continue to next task)

- [x] **Step 6: Commit**

```bash
git add src/vk/config.py src/vk/plan/__init__.py tests/unit/test_config.py
git commit -m "feat: add config module with dispatch gate truth table"
```

### Task 3: PlanFormat enum and detection

**Files:**
- Create: `src/vk/plan/format.py`
- Create: `tests/unit/test_format.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_format.py`:

```python
"""Tests for vk.plan.format — format enum and detection from markdown."""

import pytest

from vk.plan.format import PlanFormat, detect


# --- Enum properties ---


def test_phased_can_dispatch() -> None:
    assert PlanFormat.PHASED.can_dispatch is True


def test_flat_cannot_dispatch() -> None:
    assert PlanFormat.FLAT.can_dispatch is False


# --- Detection from markdown ---


PHASED_MARKDOWN = """\
# My Plan

**Spec:** `some/spec.md`
**Status:** Not Started

---

## Phase 1: Setup [agentic]

### Task 1: Create files

- [x] **Step 1: Do something**
"""

FLAT_MARKDOWN = """\
# My Plan

**Spec:** `some/spec.md`
**Status:** Not Started

---

### Task 1: Create files [agentic]

- [x] **Step 1: Do something**
"""

NO_PLAN_MARKDOWN = """\
# Just a document

Some text without any task headers.
"""

MIXED_MARKDOWN = """\
# My Plan

## Phase 1: Setup [agentic]

### Task 1: First thing

## Phase 2: Build [agentic]

### Task 2: Second thing
"""


def test_detect_phased() -> None:
    assert detect(PHASED_MARKDOWN) is PlanFormat.PHASED


def test_detect_flat() -> None:
    assert detect(FLAT_MARKDOWN) is PlanFormat.FLAT


def test_detect_not_a_plan() -> None:
    with pytest.raises(ValueError, match="not a vk plan"):
        detect(NO_PLAN_MARKDOWN)


def test_detect_phased_with_multiple_phases() -> None:
    assert detect(MIXED_MARKDOWN) is PlanFormat.PHASED


def test_detect_phase_header_variations() -> None:
    """Phase header with different tags and numbers."""
    md = "## Phase 3: Deploy [manual]\n\n### Task 1: Upload\n"
    assert detect(md) is PlanFormat.PHASED


def test_detect_flat_task_only() -> None:
    """Flat format with only task headers, no phase headers."""
    md = "### Task 1: First [agentic]\n\n### Task 2: Second [manual]\n"
    assert detect(md) is PlanFormat.FLAT
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.format'`

- [x] **Step 3: Implement src/vk/plan/format.py**

```python
"""Plan format enum and structural detection from markdown content."""

from __future__ import annotations

import enum
import re


class PlanFormat(enum.Enum):
    """Plan structure format, derived from dispatch presence (Decision D3)."""

    FLAT = "flat"
    PHASED = "phased"

    @property
    def can_dispatch(self) -> bool:
        """Only phased plans can be dispatched to GitHub Issues."""
        return self is PlanFormat.PHASED


_RE_PHASE_HEADER = re.compile(r"^## Phase \d+:", re.MULTILINE)
_RE_TASK_HEADER = re.compile(r"^### Task \d+:", re.MULTILINE)


def detect(markdown: str) -> PlanFormat:
    """Detect plan format from markdown content.

    Detection is structural, not config-driven:
    - At least one ``## Phase N:`` header -> PHASED
    - No phase headers but has ``### Task N:`` headers -> FLAT
    - Neither -> raises ValueError (not a vk plan)
    """
    if _RE_PHASE_HEADER.search(markdown):
        return PlanFormat.PHASED
    if _RE_TASK_HEADER.search(markdown):
        return PlanFormat.FLAT
    msg = "Cannot detect plan format — not a vk plan (no Phase or Task headers found)"
    raise ValueError(msg)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_format.py -v`
Expected: PASS — all 7 tests pass

- [x] **Step 5: Re-run config tests to verify format integration**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_format.py -v`
Expected: PASS — all tests pass including format-derived-from-dispatch tests

- [x] **Step 6: Commit**

```bash
git add src/vk/plan/format.py tests/unit/test_format.py
git commit -m "feat: add PlanFormat enum with structural detection from markdown"
```

### Task 4: Plan models — Plan, Phase, Task, Step, CheckboxState

**Files:**
- Create: `src/vk/plan/models.py`
- Create: `tests/unit/test_models.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_models.py`:

```python
"""Tests for vk.plan.models — frozen dataclass AST for plans."""

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import CheckboxState, Phase, Plan, Step, Task


# --- Step ---


def test_step_unchecked() -> None:
    step = Step(number=1, title="Write the test", body="Some body.", state=" ")
    assert step.state == " "
    assert step.number == 1
    assert step.title == "Write the test"
    assert step.body == "Some body."


def test_step_done() -> None:
    step = Step(number=2, title="Implement", body="", state="x")
    assert step.state == "x"


def test_step_skipped() -> None:
    step = Step(number=3, title="Optional", body="", state="-")
    assert step.state == "-"


def test_step_is_frozen() -> None:
    step = Step(number=1, title="Test", body="", state=" ")
    with pytest.raises(AttributeError):
        step.state = "x"  # type: ignore[misc]


# --- Task ---


def test_task_with_steps() -> None:
    s1 = Step(number=1, title="First", body="", state=" ")
    s2 = Step(number=2, title="Second", body="", state="x")
    task = Task(number=1, title="Setup", tag="agentic", steps=(s1, s2), files_mentioned=("a.py",))
    assert len(task.steps) == 2
    assert task.tag == "agentic"
    assert task.files_mentioned == ("a.py",)


def test_task_no_tag() -> None:
    task = Task(number=1, title="Setup", tag=None, steps=(), files_mentioned=())
    assert task.tag is None


def test_task_is_frozen() -> None:
    task = Task(number=1, title="Test", tag=None, steps=(), files_mentioned=())
    with pytest.raises(AttributeError):
        task.title = "Changed"  # type: ignore[misc]


# --- Phase ---


def test_phase_with_tasks() -> None:
    s = Step(number=1, title="Do it", body="", state=" ")
    t = Task(number=1, title="Build", tag=None, steps=(s,), files_mentioned=())
    phase = Phase(number=1, title="Setup", tag="agentic", tasks=(t,), tracking_url=None)
    assert phase.number == 1
    assert phase.tag == "agentic"
    assert len(phase.tasks) == 1
    assert phase.tracking_url is None


def test_phase_with_tracking_url() -> None:
    phase = Phase(
        number=2,
        title="Deploy",
        tag="manual",
        tasks=(),
        tracking_url="https://github.com/org/repo/issues/42",
    )
    assert phase.tracking_url == "https://github.com/org/repo/issues/42"


def test_phase_is_frozen() -> None:
    phase = Phase(number=1, title="Test", tag="agentic", tasks=(), tracking_url=None)
    with pytest.raises(AttributeError):
        phase.tag = "manual"  # type: ignore[misc]


# --- Plan ---


def test_flat_plan_all_tasks() -> None:
    """Flat plan: all_tasks returns tasks directly."""
    s = Step(number=1, title="Step", body="", state=" ")
    t1 = Task(number=1, title="First", tag="agentic", steps=(s,), files_mentioned=())
    t2 = Task(number=2, title="Second", tag="manual", steps=(s,), files_mentioned=())
    plan = Plan(
        title="Test Plan",
        spec="spec.md",
        status="Not Started",
        goal="Test it",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2),
    )
    assert plan.all_tasks == (t1, t2)
    assert plan.format is PlanFormat.FLAT


def test_phased_plan_all_tasks() -> None:
    """Phased plan: all_tasks flattens tasks from all phases."""
    s = Step(number=1, title="Step", body="", state=" ")
    t1 = Task(number=1, title="First", tag=None, steps=(s,), files_mentioned=())
    t2 = Task(number=1, title="Second", tag=None, steps=(s,), files_mentioned=())
    t3 = Task(number=2, title="Third", tag=None, steps=(s,), files_mentioned=())
    p1 = Phase(number=1, title="Setup", tag="agentic", tasks=(t1,), tracking_url=None)
    p2 = Phase(number=2, title="Build", tag="agentic", tasks=(t2, t3), tracking_url=None)
    plan = Plan(
        title="Test Plan",
        spec=None,
        status="In Progress",
        goal="Build it",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )
    assert plan.all_tasks == (t1, t2, t3)
    assert plan.format is PlanFormat.PHASED


def test_plan_is_frozen() -> None:
    plan = Plan(
        title="T",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(),
    )
    with pytest.raises(AttributeError):
        plan.title = "Changed"  # type: ignore[misc]


def test_plan_no_spec() -> None:
    """Plan with no spec reference."""
    plan = Plan(
        title="Quick Fix",
        spec=None,
        status="Not Started",
        goal="Fix bug",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(),
    )
    assert plan.spec is None


def test_checkbox_state_values() -> None:
    """CheckboxState type accepts the three valid literals."""
    states: list[CheckboxState] = [" ", "x", "-"]
    assert len(states) == 3
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.models'`

- [x] **Step 3: Implement src/vk/plan/models.py**

```python
"""Plan AST — frozen dataclasses for the plan document model.

Supports both flat (Task > Step) and phased (Phase > Task > Step) formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vk.plan.format import PlanFormat

CheckboxState = Literal[" ", "x", "-"]  # unchecked, done, skipped


@dataclass(frozen=True)
class Step:
    """A single checkbox step within a task."""

    number: int
    title: str
    body: str
    state: CheckboxState


@dataclass(frozen=True)
class Task:
    """A task containing ordered steps.

    In flat format, tasks are top-level and carry ``[manual]``/``[agentic]`` tags.
    In phased format, tasks are nested under phases and inherit the phase tag.
    """

    number: int
    title: str
    tag: Literal["manual", "agentic"] | None
    steps: tuple[Step, ...]
    files_mentioned: tuple[str, ...]


@dataclass(frozen=True)
class Phase:
    """A phase containing ordered tasks.  Only used in phased format."""

    number: int
    title: str
    tag: Literal["manual", "agentic"]
    tasks: tuple[Task, ...]
    tracking_url: str | None


@dataclass(frozen=True)
class Plan:
    """Root AST node for a parsed plan file."""

    title: str
    spec: str | None
    status: str
    goal: str
    format: PlanFormat
    phases: tuple[Phase, ...]  # populated in phased format
    tasks: tuple[Task, ...]  # populated in flat format

    @property
    def all_tasks(self) -> tuple[Task, ...]:
        """Return all tasks regardless of format.

        Flat: returns ``self.tasks`` directly.
        Phased: flattens tasks from all phases in order.
        """
        if self.format is PlanFormat.FLAT:
            return self.tasks
        return tuple(t for p in self.phases for t in p.tasks)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: PASS — all 14 tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/plan/models.py tests/unit/test_models.py
git commit -m "feat: add plan AST models — Plan, Phase, Task, Step, CheckboxState"
```

### Task 5: Filename slug derivation

**Files:**
- Create: `src/vk/plan/filename.py`
- Create: `tests/unit/test_filename.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_filename.py`:

```python
"""Tests for vk.plan.filename — slug derivation from plan file paths."""

from pathlib import Path

import pytest

from vk.plan.filename import derive_slug


def test_single_dash_pattern() -> None:
    """YYYY-MM-DD-name.md -> name"""
    assert derive_slug(Path("docs/plans/2026-04-12-scaffold.md")) == "scaffold"


def test_double_dash_pattern() -> None:
    """YYYY-MM-DD--layer--details.md -> layer--details"""
    assert derive_slug(Path("docs/plans/2026-04-12--vk-cli--p0-scaffold.md")) == "vk-cli--p0-scaffold"


def test_multi_word_slug() -> None:
    """Hyphenated name after date prefix."""
    assert derive_slug(Path("2026-04-12-vk-cli-p1-core-modules.md")) == "vk-cli-p1-core-modules"


def test_deep_path() -> None:
    """Works with deeply nested paths."""
    p = Path("/home/user/docs/superpowers/plans/2026-01-01-my-plan.md")
    assert derive_slug(p) == "my-plan"


def test_no_date_prefix_raises() -> None:
    """Filename without YYYY-MM-DD prefix raises ValueError."""
    with pytest.raises(ValueError, match="must start with YYYY-MM-DD"):
        derive_slug(Path("no-date-plan.md"))


def test_empty_slug_raises() -> None:
    """Date-only filename (no slug part) raises ValueError."""
    with pytest.raises(ValueError, match="Empty slug"):
        derive_slug(Path("2026-04-12.md"))


def test_date_only_with_trailing_dashes_raises() -> None:
    """Date with only dashes after it raises ValueError."""
    with pytest.raises(ValueError, match="Empty slug"):
        derive_slug(Path("2026-04-12--.md"))


def test_lstrip_single_dash() -> None:
    """Single leading dash is stripped."""
    assert derive_slug(Path("2026-04-12-foo.md")) == "foo"


def test_lstrip_double_dash() -> None:
    """Double leading dashes are stripped."""
    assert derive_slug(Path("2026-04-12--foo.md")) == "foo"


def test_lstrip_triple_dash() -> None:
    """Triple leading dashes are stripped."""
    assert derive_slug(Path("2026-04-12---foo.md")) == "foo"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_filename.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.filename'`

- [x] **Step 3: Implement src/vk/plan/filename.py**

```python
"""Filename slug derivation from plan file paths.

Handles both single-dash (YYYY-MM-DD-name.md) and double-dash
(YYYY-MM-DD--layer--details.md) patterns via lstrip("-").
See superpowers-for-vk#5 for discovery context.
"""

from __future__ import annotations

import re
from pathlib import Path


def derive_slug(plan_path: Path) -> str:
    """Extract the slug portion from a date-prefixed plan filename.

    Strips the YYYY-MM-DD prefix and any leading dashes, returning the
    remainder as the slug.  Raises ValueError if the filename has no
    date prefix or yields an empty slug.
    """
    stem = plan_path.stem
    m = re.match(r"^\d{4}-\d{2}-\d{2}", stem)
    if not m:
        msg = f"Plan filename must start with YYYY-MM-DD: {plan_path.name}"
        raise ValueError(msg)
    rest = stem[m.end() :]
    slug = rest.lstrip("-")
    if not slug:
        msg = f"Empty slug after stripping date prefix: {plan_path.name}"
        raise ValueError(msg)
    return slug
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_filename.py -v`
Expected: PASS — all 10 tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/plan/filename.py tests/unit/test_filename.py
git commit -m "feat: add filename slug derivation with lstrip dash handling"
```

- [x] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS — all tests pass across config, format, models, filename, and existing tests

- [x] **Step 7: Run ruff and mypy**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/`
Expected: PASS — no lint, format, or type errors. Fix any issues before proceeding.

- [x] **Step 8: Commit any lint/type fixes if needed**

```bash
git add -u
git commit -m "fix: resolve lint and type errors in Phase 1 modules"
```

---

## Phase 2: Parser, writer, and plan fixtures [agentic]

### Task 1: Plan fixture files

**Files:**
- Create: `tests/fixtures/plans/phased-small.md`
- Create: `tests/fixtures/plans/phased-large.md`
- Create: `tests/fixtures/plans/phased-dispatched.md`
- Create: `tests/fixtures/plans/flat-small.md`
- Create: `tests/fixtures/plans/flat-mixed-tags.md`
- Create: `tests/fixtures/plans/not-a-plan.md`

- [x] **Step 1: Create phased-small.md fixture**

Create `tests/fixtures/plans/phased-small.md`:

```markdown
# Small Phased Plan

**Spec:** `docs/superpowers/specs/2026-01-01-example.md`
**Status:** Not Started

**Goal:** A small phased plan for testing.

---

## Phase 1: Setup [agentic]

### Task 1: Create project structure

**Files:**
- Create: `src/main.py`
- Test: `tests/test_main.py`

- [x] **Step 1: Write the failing test**

Create `tests/test_main.py` with a basic import test.

- [x] **Step 2: Implement src/main.py**

Create the main module with a hello function.

- [x] **Step 3: Run tests**

Run: `uv run pytest -v`

## Phase 2: Documentation [manual]

### Task 1: Write README

- [x] **Step 1: Create README.md**

Write the project README with usage instructions.

- [x] **Step 2: Review documentation**

Verify all sections are complete.
```

- [x] **Step 2: Create phased-large.md fixture**

Create `tests/fixtures/plans/phased-large.md`:

```markdown
# Large Phased Plan

**Spec:** `docs/superpowers/specs/2026-02-15-big-feature.md`
**Status:** In Progress

**Goal:** A larger phased plan with multiple tasks per phase.

---

## Phase 1: Foundation [agentic]

### Task 1: Database schema

**Files:**
- Create: `migrations/001_init.sql`
- Test: `tests/test_schema.py`

- [x] **Step 1: Write schema test**

Create `tests/test_schema.py` with table existence checks.

- [x] **Step 2: Create migration**

Write the SQL migration file.

- [x] **Step 3: Run migration**

Apply and verify.

### Task 2: Configuration loader

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [x] **Step 1: Write config tests**

Test YAML loading with defaults.

- [x] **Step 2: Implement config module**

Build the config loader.

## Phase 2: API Layer [agentic]

### Task 1: REST endpoints

**Files:**
- Create: `src/api.py`
- Test: `tests/test_api.py`

- [x] **Step 1: Write API tests**

Test endpoint responses.

- [x] **Step 2: Implement endpoints**

Build the REST handlers.

### Task 2: Authentication middleware

**Files:**
- Create: `src/auth.py`
- Test: `tests/test_auth.py`

- [x] **Step 1: Write auth tests**

Test token validation.

- [x] **Step 2: Implement auth middleware**

Build the authentication layer.

## Phase 3: Deployment [manual]

### Task 1: CI/CD pipeline

- [x] **Step 1: Create workflow file**

Write `.github/workflows/deploy.yml`.

- [x] **Step 2: Configure secrets**

Set up repository secrets for deployment.
```

- [x] **Step 3: Create phased-dispatched.md fixture**

Create `tests/fixtures/plans/phased-dispatched.md`:

```markdown
# Dispatched Phased Plan

**Spec:** `docs/superpowers/specs/2026-03-01-dispatched.md`
**Status:** In Progress

**Goal:** A phased plan that has been dispatched to GitHub Issues.

---

## Phase 1: Core Implementation [agentic]

<!-- Tracking: https://github.com/derio-net/some-repo/issues/42 -->

### Task 1: Build the thing

**Files:**
- Create: `src/thing.py`
- Test: `tests/test_thing.py`

- [x] **Step 1: Write tests**

Create comprehensive test suite.

- [x] **Step 2: Implement**

Build the core module.

- [x] **Step 3: Commit**

Stage and commit all files.

## Phase 2: Integration [agentic]

<!-- Tracking: https://github.com/derio-net/some-repo/issues/43 -->

### Task 1: Wire up components

- [x] **Step 1: Integration tests**

Write integration test suite.

- [x] **Step 2: Connect modules**

Wire the modules together.

## Phase 3: Release [manual]

### Task 1: Version bump

- [x] **Step 1: Update version**

Bump version in pyproject.toml.
```

- [x] **Step 4: Create flat-small.md fixture**

Create `tests/fixtures/plans/flat-small.md`:

```markdown
# Small Flat Plan

**Spec:** `docs/superpowers/specs/2026-04-01-local-feature.md`
**Status:** Not Started

**Goal:** A small flat plan for local-mode repos.

---

### Task 1: Set up database schema [agentic]

**Files:**
- Create: `migrations/001_create_table.sql`
- Test: `tests/test_schema.py`

- [x] **Step 1: Write the failing test**

Create schema validation tests.

- [x] **Step 2: Create migration**

Write the SQL migration.

### Task 2: Configure DNS records [manual]

- [x] **Step 1: Log in to Cloudflare dashboard**

URL: https://dash.cloudflare.com/

- [x] **Step 2: Add A record**

Point domain to server IP.

### Task 3: Implement API endpoint [agentic]

**Files:**
- Create: `src/api.py`
- Test: `tests/test_api.py`

- [x] **Step 1: Write API tests**

Test the endpoint responses.

- [x] **Step 2: Implement handler**

Build the request handler.
```

- [x] **Step 5: Create flat-mixed-tags.md fixture**

Create `tests/fixtures/plans/flat-mixed-tags.md`:

```markdown
# Mixed Tags Flat Plan

**Status:** In Progress

**Goal:** Flat plan with alternating manual and agentic tasks.

---

### Task 1: Scaffold project [agentic]

- [x] **Step 1: Create directory structure**

Set up the project layout.

### Task 2: Order hardware [manual]

- [x] **Step 1: Submit purchase order**

File the PO with procurement.

- [x] **Step 2: Verify delivery**

Confirm hardware arrives.

### Task 3: Write firmware [agentic]

- [x] **Step 1: Implement bootloader**

Write the initial bootloader code.

### Task 4: Install hardware [manual]

- [x] **Step 1: Rack the server**

Mount in rack position U12.

### Task 5: Deploy software [agentic]

- [x] **Step 1: Build and push image**

Build the container and push to registry.

- [-] **Step 2: Run smoke tests**

Verify basic functionality.
```

- [x] **Step 6: Create not-a-plan.md fixture**

Create `tests/fixtures/plans/not-a-plan.md`:

```markdown
# Meeting Notes

## Attendees

- Alice
- Bob

## Discussion

We talked about the architecture.

## Action Items

- Alice will draft the design doc.
- Bob will set up the repo.
```

- [x] **Step 7: Commit all plan fixtures**

```bash
git add tests/fixtures/plans/
git commit -m "test: add plan fixture files for parser and writer tests"
```

### Task 2: Plan parser — parse_plan() for both formats

**Files:**
- Create: `src/vk/plan/parser.py`
- Create: `tests/unit/test_plan_parser.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_plan_parser.py`:

```python
"""Tests for vk.plan.parser — parse_plan() for flat and phased formats."""

from pathlib import Path

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import Plan
from vk.plan.parser import parse_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Phased format parsing ---


class TestPhasedSmall:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-small.md")

    def test_title(self, plan: Plan) -> None:
        assert plan.title == "Small Phased Plan"

    def test_spec(self, plan: Plan) -> None:
        assert plan.spec == "docs/superpowers/specs/2026-01-01-example.md"

    def test_status(self, plan: Plan) -> None:
        assert plan.status == "Not Started"

    def test_goal(self, plan: Plan) -> None:
        assert plan.goal == "A small phased plan for testing."

    def test_format(self, plan: Plan) -> None:
        assert plan.format is PlanFormat.PHASED

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 2

    def test_phase_1_tag(self, plan: Plan) -> None:
        assert plan.phases[0].tag == "agentic"
        assert plan.phases[0].title == "Setup"

    def test_phase_2_tag(self, plan: Plan) -> None:
        assert plan.phases[1].tag == "manual"
        assert plan.phases[1].title == "Documentation"

    def test_phase_1_task_count(self, plan: Plan) -> None:
        assert len(plan.phases[0].tasks) == 1

    def test_phase_1_task_1_steps(self, plan: Plan) -> None:
        task = plan.phases[0].tasks[0]
        assert task.title == "Create project structure"
        assert len(task.steps) == 3

    def test_step_states(self, plan: Plan) -> None:
        phase2_task1 = plan.phases[1].tasks[0]
        assert phase2_task1.steps[0].state == " "
        assert phase2_task1.steps[1].state == "x"

    def test_files_mentioned(self, plan: Plan) -> None:
        task = plan.phases[0].tasks[0]
        assert "src/main.py" in task.files_mentioned
        assert "tests/test_main.py" in task.files_mentioned

    def test_all_tasks_flattens(self, plan: Plan) -> None:
        assert len(plan.all_tasks) == 2


class TestPhasedLarge:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-large.md")

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 3

    def test_all_tasks_count(self, plan: Plan) -> None:
        assert len(plan.all_tasks) == 5

    def test_status(self, plan: Plan) -> None:
        assert plan.status == "In Progress"

    def test_phase_2_has_two_tasks(self, plan: Plan) -> None:
        assert len(plan.phases[1].tasks) == 2

    def test_mixed_step_states(self, plan: Plan) -> None:
        phase1_task1 = plan.phases[0].tasks[0]
        assert phase1_task1.steps[0].state == " "
        assert phase1_task1.steps[1].state == "x"
        assert phase1_task1.steps[2].state == "x"


class TestPhasedDispatched:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-dispatched.md")

    def test_tracking_urls(self, plan: Plan) -> None:
        assert plan.phases[0].tracking_url == "https://github.com/derio-net/some-repo/issues/42"
        assert plan.phases[1].tracking_url == "https://github.com/derio-net/some-repo/issues/43"
        assert plan.phases[2].tracking_url is None

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 3

    def test_dispatched_steps_checked(self, plan: Plan) -> None:
        phase1_task1 = plan.phases[0].tasks[0]
        assert all(s.state == "x" for s in phase1_task1.steps)


# --- Flat format parsing ---


class TestFlatSmall:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "flat-small.md")

    def test_title(self, plan: Plan) -> None:
        assert plan.title == "Small Flat Plan"

    def test_format(self, plan: Plan) -> None:
        assert plan.format is PlanFormat.FLAT

    def test_task_count(self, plan: Plan) -> None:
        assert len(plan.tasks) == 3

    def test_task_tags(self, plan: Plan) -> None:
        assert plan.tasks[0].tag == "agentic"
        assert plan.tasks[1].tag == "manual"
        assert plan.tasks[2].tag == "agentic"

    def test_spec(self, plan: Plan) -> None:
        assert plan.spec == "docs/superpowers/specs/2026-04-01-local-feature.md"

    def test_all_tasks_is_tasks(self, plan: Plan) -> None:
        assert plan.all_tasks == plan.tasks

    def test_files_mentioned(self, plan: Plan) -> None:
        assert "migrations/001_create_table.sql" in plan.tasks[0].files_mentioned
        assert "tests/test_schema.py" in plan.tasks[0].files_mentioned


class TestFlatMixedTags:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "flat-mixed-tags.md")

    def test_task_count(self, plan: Plan) -> None:
        assert len(plan.tasks) == 5

    def test_alternating_tags(self, plan: Plan) -> None:
        expected = ["agentic", "manual", "agentic", "manual", "agentic"]
        assert [t.tag for t in plan.tasks] == expected

    def test_no_spec(self, plan: Plan) -> None:
        assert plan.spec is None

    def test_skipped_step(self, plan: Plan) -> None:
        task5 = plan.tasks[4]
        assert task5.steps[1].state == "-"

    def test_checked_step(self, plan: Plan) -> None:
        task1 = plan.tasks[0]
        assert task1.steps[0].state == "x"


# --- Error cases ---


def test_not_a_plan_raises() -> None:
    with pytest.raises(ValueError, match="not a vk plan"):
        parse_plan(FIXTURES / "not-a-plan.md")


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_plan(Path("/nonexistent/path/plan.md"))
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_plan_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.parser'`

- [x] **Step 3: Implement src/vk/plan/parser.py**

```python
"""Plan parser — regex-driven, supports both flat and phased formats.

Produces a frozen Plan AST from a markdown file.  Body content between
headers is preserved as raw strings for lossless round-trip.
"""

from __future__ import annotations

import re
from pathlib import Path

from vk.plan.format import PlanFormat, detect
from vk.plan.models import Phase, Plan, Step, Task

# --- Header field patterns ---

_RE_TITLE = re.compile(r"^# (.+)$", re.MULTILINE)
_RE_SPEC = re.compile(r"^\*\*Spec:\*\*\s*`([^`]+)`", re.MULTILINE)
_RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)
_RE_GOAL = re.compile(r"^\*\*Goal:\*\*\s*(.+)$", re.MULTILINE)

# --- Structural patterns ---

_RE_PHASE = re.compile(
    r"^## Phase (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE
)
_RE_TASK = re.compile(
    r"^### Task (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE
)
_RE_STEP = re.compile(
    r"^- \[([x \-])\] \*\*Step (\d+):\s*(.+?)\*\*\s*$", re.MULTILINE
)
_RE_TRACKING = re.compile(
    r"^<!-- Tracking:\s*(https?://\S+)\s*-->", re.MULTILINE
)
_RE_FILE_MENTION = re.compile(
    r"^- (?:Create|Edit|Test|Delete|Move|Rename):\s*`([^`]+)`", re.MULTILINE
)


def parse_plan(path: Path) -> Plan:
    """Parse a plan markdown file into a frozen Plan AST.

    Raises FileNotFoundError if path does not exist.
    Raises ValueError if the file is not a valid vk plan.
    """
    text = path.read_text(encoding="utf-8")
    fmt = detect(text)

    title = _extract(text, _RE_TITLE, "Untitled Plan")
    spec = _extract_optional(text, _RE_SPEC)
    status = _extract(text, _RE_STATUS, "Not Started")
    goal = _extract(text, _RE_GOAL, "")

    if fmt is PlanFormat.PHASED:
        phases = _parse_phases(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=tuple(phases),
            tasks=(),
        )
    else:
        tasks = _parse_tasks(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=(),
            tasks=tuple(tasks),
        )


def _extract(text: str, pattern: re.Pattern[str], default: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else default


def _extract_optional(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _parse_phases(text: str) -> list[Phase]:
    """Parse all phases from phased-format markdown."""
    phase_matches = list(_RE_PHASE.finditer(text))
    phases: list[Phase] = []

    for i, pm in enumerate(phase_matches):
        start = pm.end()
        end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(text)
        section = text[start:end]

        tracking_match = _RE_TRACKING.search(section)
        tracking_url = tracking_match.group(1) if tracking_match else None

        tasks = _parse_tasks(section)
        phases.append(
            Phase(
                number=int(pm.group(1)),
                title=pm.group(2).strip(),
                tag=pm.group(3) or "agentic",
                tasks=tuple(tasks),
                tracking_url=tracking_url,
            )
        )

    return phases


def _parse_tasks(text: str) -> list[Task]:
    """Parse all tasks from a section of markdown."""
    task_matches = list(_RE_TASK.finditer(text))
    tasks: list[Task] = []

    for i, tm in enumerate(task_matches):
        start = tm.end()
        end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(text)
        section = text[start:end]

        # Don't cross into the next phase
        next_phase = _RE_PHASE.search(section)
        if next_phase:
            section = section[: next_phase.start()]

        steps = _parse_steps(section)
        files = _parse_files(section)
        tasks.append(
            Task(
                number=int(tm.group(1)),
                title=tm.group(2).strip(),
                tag=tm.group(3) or None,
                steps=tuple(steps),
                files_mentioned=tuple(files),
            )
        )

    return tasks


def _parse_steps(text: str) -> list[Step]:
    """Parse all steps from a task section."""
    step_matches = list(_RE_STEP.finditer(text))
    steps: list[Step] = []

    for i, sm in enumerate(step_matches):
        start = sm.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(text)
        body = text[start:end].strip()

        state_char = sm.group(1)
        state = state_char if state_char in (" ", "x", "-") else " "

        steps.append(
            Step(
                number=int(sm.group(2)),
                title=sm.group(3).strip(),
                body=body,
                state=state,  # type: ignore[arg-type]
            )
        )

    return steps


def _parse_files(text: str) -> list[str]:
    """Extract file mentions from a task section."""
    return [m.group(1) for m in _RE_FILE_MENTION.finditer(text)]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_plan_parser.py -v`
Expected: PASS — all tests pass

- [x] **Step 5: Run ruff and mypy on new code**

Run: `uv run ruff check src/vk/plan/parser.py tests/unit/test_plan_parser.py && uv run mypy src/vk/plan/parser.py`
Expected: PASS — no lint or type errors. Fix any issues.

- [x] **Step 6: Commit**

```bash
git add src/vk/plan/parser.py tests/unit/test_plan_parser.py
git commit -m "feat: add regex-driven plan parser for flat and phased formats"
```

### Task 3: Plan writer — write_plan() with round-trip fidelity

**Files:**
- Create: `src/vk/plan/writer.py`
- Create: `tests/unit/test_plan_writer.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_plan_writer.py`:

```python
"""Tests for vk.plan.writer — write_plan() with round-trip fidelity."""

from pathlib import Path

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Step, Task
from vk.plan.parser import parse_plan
from vk.plan.writer import write_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Round-trip: parse -> write -> parse = identical AST ---


@pytest.mark.parametrize(
    "fixture",
    [
        "phased-small.md",
        "phased-large.md",
        "phased-dispatched.md",
        "flat-small.md",
        "flat-mixed-tags.md",
    ],
)
def test_round_trip(fixture: str, tmp_path: Path) -> None:
    """parse -> write -> parse produces identical AST."""
    original = parse_plan(FIXTURES / fixture)
    output_path = tmp_path / fixture
    write_plan(original, output_path)
    reparsed = parse_plan(output_path)

    assert reparsed.title == original.title
    assert reparsed.spec == original.spec
    assert reparsed.status == original.status
    assert reparsed.goal == original.goal
    assert reparsed.format == original.format
    assert len(reparsed.all_tasks) == len(original.all_tasks)

    for orig_task, new_task in zip(original.all_tasks, reparsed.all_tasks):
        assert new_task.number == orig_task.number
        assert new_task.title == orig_task.title
        assert new_task.tag == orig_task.tag
        assert len(new_task.steps) == len(orig_task.steps)
        for orig_step, new_step in zip(orig_task.steps, new_task.steps):
            assert new_step.number == orig_step.number
            assert new_step.title == orig_step.title
            assert new_step.state == orig_step.state

    if original.format is PlanFormat.PHASED:
        assert len(reparsed.phases) == len(original.phases)
        for orig_phase, new_phase in zip(original.phases, reparsed.phases):
            assert new_phase.number == orig_phase.number
            assert new_phase.title == orig_phase.title
            assert new_phase.tag == orig_phase.tag
            assert new_phase.tracking_url == orig_phase.tracking_url


# --- Direct write tests ---


def test_write_flat_plan(tmp_path: Path) -> None:
    """Write a flat plan and verify structure."""
    s1 = Step(number=1, title="Write test", body="Create the test file.", state=" ")
    s2 = Step(number=2, title="Implement", body="Write the code.", state="x")
    t1 = Task(number=1, title="Setup", tag="agentic", steps=(s1, s2), files_mentioned=("a.py",))
    t2 = Task(number=2, title="Deploy", tag="manual", steps=(), files_mentioned=())
    plan = Plan(
        title="Test Plan",
        spec="spec.md",
        status="Not Started",
        goal="Test writing.",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()

    assert "# Test Plan" in text
    assert "**Spec:** `spec.md`" in text
    assert "**Status:** Not Started" in text
    assert "**Goal:** Test writing." in text
    assert "### Task 1: Setup [agentic]" in text
    assert "### Task 2: Deploy [manual]" in text
    assert "- [x] **Step 1: Write test**" in text
    assert "- [x] **Step 2: Implement**" in text
    assert "- Create: `a.py`" in text


def test_write_phased_plan(tmp_path: Path) -> None:
    """Write a phased plan and verify structure."""
    s1 = Step(number=1, title="Do it", body="Just do it.", state=" ")
    t1 = Task(number=1, title="Build", tag=None, steps=(s1,), files_mentioned=())
    p1 = Phase(number=1, title="Core", tag="agentic", tasks=(t1,), tracking_url=None)
    p2 = Phase(
        number=2,
        title="Release",
        tag="manual",
        tasks=(),
        tracking_url="https://github.com/org/repo/issues/99",
    )
    plan = Plan(
        title="Phased Plan",
        spec=None,
        status="In Progress",
        goal="Ship it.",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()

    assert "# Phased Plan" in text
    assert "**Spec:**" not in text  # no spec
    assert "**Status:** In Progress" in text
    assert "## Phase 1: Core [agentic]" in text
    assert "## Phase 2: Release [manual]" in text
    assert "<!-- Tracking: https://github.com/org/repo/issues/99 -->" in text
    assert "### Task 1: Build" in text


def test_write_skipped_step(tmp_path: Path) -> None:
    """Skipped steps render with [-]."""
    s = Step(number=1, title="Skip me", body="", state="-")
    t = Task(number=1, title="Task", tag="agentic", steps=(s,), files_mentioned=())
    plan = Plan(
        title="P",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t,),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()
    assert "- [-] **Step 1: Skip me**" in text
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_plan_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.writer'`

- [x] **Step 3: Implement src/vk/plan/writer.py**

```python
"""Plan writer — renders a Plan AST back to markdown.

Preserves body content for lossless round-trip:
parse -> write -> parse = identical AST.
"""

from __future__ import annotations

from pathlib import Path

from vk.plan.format import PlanFormat
from vk.plan.models import Plan, Phase, Task, Step


def write_plan(plan: Plan, path: Path) -> None:
    """Write a Plan AST to a markdown file."""
    lines: list[str] = []
    _write_header(lines, plan)
    lines.append("")
    lines.append("---")
    lines.append("")

    if plan.format is PlanFormat.PHASED:
        _write_phases(lines, plan.phases)
    else:
        _write_tasks(lines, plan.tasks)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_header(lines: list[str], plan: Plan) -> None:
    """Write the plan header block."""
    lines.append(f"# {plan.title}")
    lines.append("")
    if plan.spec:
        lines.append(f"**Spec:** `{plan.spec}`")
    lines.append(f"**Status:** {plan.status}")
    lines.append("")
    lines.append(f"**Goal:** {plan.goal}")


def _write_phases(lines: list[str], phases: tuple[Phase, ...]) -> None:
    """Write all phases in phased format."""
    for i, phase in enumerate(phases):
        if i > 0:
            lines.append("")
        lines.append(f"## Phase {phase.number}: {phase.title} [{phase.tag}]")
        lines.append("")
        if phase.tracking_url:
            lines.append(f"<!-- Tracking: {phase.tracking_url} -->")
            lines.append("")
        _write_tasks(lines, phase.tasks)


def _write_tasks(lines: list[str], tasks: tuple[Task, ...]) -> None:
    """Write all tasks."""
    for i, task in enumerate(tasks):
        if i > 0:
            lines.append("")
        tag_suffix = f" [{task.tag}]" if task.tag else ""
        lines.append(f"### Task {task.number}: {task.title}{tag_suffix}")
        lines.append("")
        if task.files_mentioned:
            lines.append("**Files:**")
            for f in task.files_mentioned:
                lines.append(f"- Create: `{f}`")
            lines.append("")
        _write_steps(lines, task.steps)


def _write_steps(lines: list[str], steps: tuple[Step, ...]) -> None:
    """Write all steps within a task."""
    for step in steps:
        lines.append(f"- [{step.state}] **Step {step.number}: {step.title}**")
        if step.body:
            lines.append("")
            lines.append(step.body)
        lines.append("")
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_plan_writer.py -v`
Expected: PASS — all tests pass. If round-trip tests fail, adjust the writer to match the parser's expectations (e.g., blank line placement, file mention format).

- [x] **Step 5: Debug and fix round-trip mismatches**

If any round-trip tests fail, compare the written output to the original fixture and adjust the writer. Common issues:
- Extra or missing blank lines between sections
- File mention prefix (the writer always uses "Create:" but the parser accepts Create/Edit/Test/Delete/Move/Rename — round-trip only needs to preserve files_mentioned tuple values, not the verb)
- Step body trailing whitespace

Run: `uv run pytest tests/unit/test_plan_writer.py -v` until all tests pass.

- [x] **Step 6: Commit**

```bash
git add src/vk/plan/writer.py tests/unit/test_plan_writer.py
git commit -m "feat: add plan writer with round-trip parse-write-parse fidelity"
```

### Task 4: Spec fixture files

**Files:**
- Create: `tests/fixtures/specs/spec-with-index.md`
- Create: `tests/fixtures/specs/spec-without-index.md`

- [x] **Step 1: Create spec-with-index.md fixture**

Create `tests/fixtures/specs/spec-with-index.md`:

```markdown
# Example Feature Design Spec

## Summary

This is an example spec with an existing implementation plans index.

## Design

Some design content here.

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| P0: Scaffold | superpowers-for-vk | `docs/superpowers/plans/2026-04-12-scaffold.md` | Complete | — |
| P1: Core | superpowers-for-vk | `docs/superpowers/plans/2026-04-12-core.md` | In Progress | P0 |
```

- [x] **Step 2: Create spec-without-index.md fixture**

Create `tests/fixtures/specs/spec-without-index.md`:

```markdown
# Another Feature Design Spec

## Summary

This spec has no implementation plans section yet.

## Design

Design details here.

## Testing Strategy

How to test the feature.
```

- [x] **Step 3: Commit spec fixtures**

```bash
git add tests/fixtures/specs/
git commit -m "test: add spec fixture files for spec_index tests"
```

- [x] **Step 4: Run full test suite and quality gates**

Run: `uv run pytest -v && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/`
Expected: PASS — all tests pass, no lint/format/type errors.

- [x] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve lint and type errors in Phase 2 modules"
```

---

## Phase 3: Converter, spec index, git/gh helpers [agentic]

### Task 1: Plan converter — to_flat, to_phased variants

**Files:**
- Create: `src/vk/plan/convert.py`
- Create: `tests/unit/test_plan_convert.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_plan_convert.py`:

```python
"""Tests for vk.plan.convert — format conversion between flat and phased."""

from pathlib import Path

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Step, Task
from vk.plan.convert import to_flat, to_phased_single, to_phased_one_per_task, to_phased_group_by_tag
from vk.plan.parser import parse_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Helpers ---


def _make_step(num: int, state: str = " ") -> Step:
    return Step(number=num, title=f"Step {num}", body=f"Body {num}", state=state)  # type: ignore[arg-type]


def _make_task(num: int, tag: str = "agentic", steps: int = 2) -> Task:
    return Task(
        number=num,
        title=f"Task {num}",
        tag=tag,  # type: ignore[arg-type]
        steps=tuple(_make_step(i + 1) for i in range(steps)),
        files_mentioned=(),
    )


def _make_phased_plan() -> Plan:
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "agentic")
    t3 = _make_task(1, "manual")
    p1 = Phase(number=1, title="Build", tag="agentic", tasks=(t1, t2), tracking_url=None)
    p2 = Phase(number=2, title="Deploy", tag="manual", tasks=(t3,), tracking_url=None)
    return Plan(
        title="Test",
        spec="spec.md",
        status="Not Started",
        goal="Convert",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )


def _make_flat_plan() -> Plan:
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "manual")
    t3 = _make_task(3, "agentic")
    t4 = _make_task(4, "manual")
    return Plan(
        title="Flat Test",
        spec=None,
        status="In Progress",
        goal="Convert",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2, t3, t4),
    )


# --- Phased to flat ---


def test_to_flat_task_count() -> None:
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.format is PlanFormat.FLAT
    assert len(flat.tasks) == 3


def test_to_flat_task_numbering() -> None:
    """Task numbers reset globally 1, 2, 3..."""
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert [t.number for t in flat.tasks] == [1, 2, 3]


def test_to_flat_inherits_phase_tag() -> None:
    """Each task inherits its parent phase's tag."""
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.tasks[0].tag == "agentic"
    assert flat.tasks[1].tag == "agentic"
    assert flat.tasks[2].tag == "manual"


def test_to_flat_preserves_metadata() -> None:
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.title == plan.title
    assert flat.spec == plan.spec
    assert flat.status == plan.status
    assert flat.goal == plan.goal


def test_to_flat_refuses_tracking_without_force() -> None:
    """Refuses conversion if plan has tracking comments."""
    plan = parse_plan(FIXTURES / "phased-dispatched.md")
    with pytest.raises(ValueError, match="tracking"):
        to_flat(plan)


def test_to_flat_tracking_with_force() -> None:
    """Allows conversion with force=True even with tracking comments."""
    plan = parse_plan(FIXTURES / "phased-dispatched.md")
    flat = to_flat(plan, force=True)
    assert flat.format is PlanFormat.FLAT


def test_to_flat_already_flat_raises() -> None:
    flat = _make_flat_plan()
    with pytest.raises(ValueError, match="already flat"):
        to_flat(flat)


# --- Flat to phased: single phase ---


def test_to_phased_single() -> None:
    flat = _make_flat_plan()
    phased = to_phased_single(flat)
    assert phased.format is PlanFormat.PHASED
    assert len(phased.phases) == 1
    assert len(phased.phases[0].tasks) == 4


def test_to_phased_single_dominant_tag() -> None:
    """Phase gets the dominant tag (most common among tasks)."""
    flat = _make_flat_plan()
    phased = to_phased_single(flat)
    # 2 agentic, 2 manual — tie-break to agentic
    assert phased.phases[0].tag in ("agentic", "manual")


def test_to_phased_single_already_phased_raises() -> None:
    phased = _make_phased_plan()
    with pytest.raises(ValueError, match="already phased"):
        to_phased_single(phased)


# --- Flat to phased: one per task ---


def test_to_phased_one_per_task() -> None:
    flat = _make_flat_plan()
    phased = to_phased_one_per_task(flat)
    assert phased.format is PlanFormat.PHASED
    assert len(phased.phases) == 4
    for i, phase in enumerate(phased.phases):
        assert phase.number == i + 1
        assert len(phase.tasks) == 1


def test_to_phased_one_per_task_inherits_tag() -> None:
    """Each phase inherits its task's tag."""
    flat = _make_flat_plan()
    phased = to_phased_one_per_task(flat)
    assert phased.phases[0].tag == "agentic"
    assert phased.phases[1].tag == "manual"


# --- Flat to phased: group by tag ---


def test_to_phased_group_by_tag() -> None:
    """Consecutive tasks with the same tag merge into one phase."""
    flat = _make_flat_plan()
    phased = to_phased_group_by_tag(flat)
    assert phased.format is PlanFormat.PHASED
    # agentic, manual, agentic, manual -> 4 groups (alternating)
    assert len(phased.phases) == 4


def test_to_phased_group_by_tag_consecutive() -> None:
    """Consecutive same-tag tasks merge."""
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "agentic")
    t3 = _make_task(3, "manual")
    flat = Plan(
        title="T",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2, t3),
    )
    phased = to_phased_group_by_tag(flat)
    assert len(phased.phases) == 2
    assert len(phased.phases[0].tasks) == 2
    assert phased.phases[0].tag == "agentic"
    assert len(phased.phases[1].tasks) == 1
    assert phased.phases[1].tag == "manual"


# --- Round-trip invariant ---


def test_round_trip_phased_flat_phased() -> None:
    """phased -> flat -> phased(single) preserves all task content and ordering."""
    original = _make_phased_plan()
    flat = to_flat(original)
    back = to_phased_single(flat)
    assert len(back.all_tasks) == len(original.all_tasks)
    for orig, converted in zip(original.all_tasks, back.all_tasks):
        assert orig.title == converted.title
        assert len(orig.steps) == len(converted.steps)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_plan_convert.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.plan.convert'`

- [x] **Step 3: Implement src/vk/plan/convert.py**

```python
"""Plan format converter — flat <-> phased conversions.

Four modes:
- to_flat: Phased -> flat (refuses tracking comments without force)
- to_phased_single: Flat -> single phase
- to_phased_one_per_task: Flat -> one phase per task
- to_phased_group_by_tag: Flat -> phases grouped by consecutive tag
"""

from __future__ import annotations

from collections import Counter
from itertools import groupby

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Task


def to_flat(plan: Plan, *, force: bool = False) -> Plan:
    """Convert a phased plan to flat format.

    Task numbering resets globally (1, 2, 3...).
    Each task inherits its parent phase's tag.
    Refuses if plan has tracking comments unless force=True.
    """
    if plan.format is PlanFormat.FLAT:
        msg = "Plan is already flat"
        raise ValueError(msg)

    if not force:
        has_tracking = any(p.tracking_url for p in plan.phases)
        if has_tracking:
            msg = (
                "Cannot convert to flat: plan has tracking comments linking to "
                "GitHub Issues. Use force=True to convert anyway (this will orphan "
                "the issue links)."
            )
            raise ValueError(msg)

    tasks: list[Task] = []
    num = 1
    for phase in plan.phases:
        for task in phase.tasks:
            tasks.append(
                Task(
                    number=num,
                    title=task.title,
                    tag=task.tag or phase.tag,
                    steps=task.steps,
                    files_mentioned=task.files_mentioned,
                )
            )
            num += 1

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.FLAT,
        phases=(),
        tasks=tuple(tasks),
    )


def to_phased_single(plan: Plan) -> Plan:
    """Convert a flat plan to a single phase.

    The phase gets the dominant tag (most common among tasks).
    On a tie, prefers 'agentic'.
    """
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    tag = _dominant_tag(plan.tasks)
    renumbered = _renumber_tasks(plan.tasks)
    phase = Phase(
        number=1,
        title=plan.title,
        tag=tag,
        tasks=renumbered,
        tracking_url=None,
    )

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=(phase,),
        tasks=(),
    )


def to_phased_one_per_task(plan: Plan) -> Plan:
    """Convert a flat plan to phased with one phase per task."""
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    phases: list[Phase] = []
    for i, task in enumerate(plan.tasks):
        renumbered_task = Task(
            number=1,
            title=task.title,
            tag=None,
            steps=task.steps,
            files_mentioned=task.files_mentioned,
        )
        phases.append(
            Phase(
                number=i + 1,
                title=task.title,
                tag=task.tag or "agentic",
                tasks=(renumbered_task,),
                tracking_url=None,
            )
        )

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=tuple(phases),
        tasks=(),
    )


def to_phased_group_by_tag(plan: Plan) -> Plan:
    """Convert a flat plan to phased, grouping consecutive same-tag tasks."""
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    phases: list[Phase] = []
    phase_num = 1

    for tag, group in groupby(plan.tasks, key=lambda t: t.tag or "agentic"):
        group_tasks = list(group)
        renumbered = _renumber_tasks(tuple(group_tasks))
        # Generate a title from the first task or a generic one
        if len(group_tasks) == 1:
            title = group_tasks[0].title
        else:
            title = f"Phase {phase_num}"

        phases.append(
            Phase(
                number=phase_num,
                title=title,
                tag=tag,  # type: ignore[arg-type]
                tasks=renumbered,
                tracking_url=None,
            )
        )
        phase_num += 1

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=tuple(phases),
        tasks=(),
    )


def _dominant_tag(tasks: tuple[Task, ...]) -> str:
    """Return the most common tag among tasks.  Tie-breaks to 'agentic'."""
    counts: Counter[str] = Counter()
    for t in tasks:
        counts[t.tag or "agentic"] += 1
    if not counts:
        return "agentic"
    max_count = max(counts.values())
    # If agentic is tied for max, prefer it
    if counts.get("agentic", 0) == max_count:
        return "agentic"
    return counts.most_common(1)[0][0]


def _renumber_tasks(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Renumber tasks starting from 1."""
    return tuple(
        Task(
            number=i + 1,
            title=t.title,
            tag=t.tag,
            steps=t.steps,
            files_mentioned=t.files_mentioned,
        )
        for i, t in enumerate(tasks)
    )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_plan_convert.py -v`
Expected: PASS — all tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/plan/convert.py tests/unit/test_plan_convert.py
git commit -m "feat: add plan converter with four flat/phased conversion modes"
```

### Task 2: Spec index — read/create/update implementation plans table

**Files:**
- Create: `src/vk/spec_index.py`
- Create: `tests/unit/test_spec_index.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_spec_index.py`:

```python
"""Tests for vk.spec_index — read/create/update Implementation Plans table."""

from pathlib import Path

import pytest

from vk.spec_index import read_index, upsert_entry, IndexEntry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "specs"


# --- Read ---


def test_read_existing_index() -> None:
    entries = read_index(FIXTURES / "spec-with-index.md")
    assert len(entries) == 2
    assert entries[0].plan == "P0: Scaffold"
    assert entries[0].status == "Complete"
    assert entries[1].plan == "P1: Core"
    assert entries[1].status == "In Progress"


def test_read_no_index() -> None:
    entries = read_index(FIXTURES / "spec-without-index.md")
    assert entries == []


def test_read_missing_file() -> None:
    entries = read_index(Path("/nonexistent/spec.md"))
    assert entries == []


# --- Upsert ---


def test_upsert_creates_section(tmp_path: Path) -> None:
    """Adds ## Implementation Plans section when missing."""
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n## Summary\n\nSome content.\n")
    entry = IndexEntry(
        plan="P0: Scaffold",
        repo="my-repo",
        file="plans/p0.md",
        status="Not Started",
        depends_on="—",
    )
    upsert_entry(spec, entry)
    text = spec.read_text()
    assert "## Implementation Plans" in text
    assert "P0: Scaffold" in text
    assert "Not Started" in text


def test_upsert_adds_row(tmp_path: Path) -> None:
    """Adds a new row to existing table."""
    spec = tmp_path / "spec.md"
    spec.write_text(
        (FIXTURES / "spec-with-index.md").read_text()
    )
    entry = IndexEntry(
        plan="P2: Dispatch",
        repo="superpowers-for-vk",
        file="plans/p2.md",
        status="Not Started",
        depends_on="P1",
    )
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 3
    assert entries[2].plan == "P2: Dispatch"


def test_upsert_updates_existing(tmp_path: Path) -> None:
    """Updates status of an existing plan row."""
    spec = tmp_path / "spec.md"
    spec.write_text(
        (FIXTURES / "spec-with-index.md").read_text()
    )
    entry = IndexEntry(
        plan="P1: Core",
        repo="superpowers-for-vk",
        file="plans/core.md",
        status="Complete",
        depends_on="P0",
    )
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 2
    p1 = [e for e in entries if e.plan == "P1: Core"][0]
    assert p1.status == "Complete"


def test_upsert_idempotent(tmp_path: Path) -> None:
    """Upserting the same entry twice doesn't create duplicates."""
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\n## Summary\n\nContent.\n")
    entry = IndexEntry(
        plan="P0: Init",
        repo="r",
        file="f.md",
        status="Not Started",
        depends_on="—",
    )
    upsert_entry(spec, entry)
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 1
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_spec_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.spec_index'`

- [x] **Step 3: Implement src/vk/spec_index.py**

```python
"""Spec index — read/create/update the Implementation Plans markdown table.

Each spec file may contain a ``## Implementation Plans`` section with a
markdown table tracking sub-project plans, their statuses, and dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IndexEntry:
    """A row in the Implementation Plans table."""

    plan: str
    repo: str
    file: str
    status: str
    depends_on: str


_RE_INDEX_HEADER = re.compile(r"^## Implementation Plans\s*$", re.MULTILINE)
_RE_TABLE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)


def read_index(spec_path: Path) -> list[IndexEntry]:
    """Read implementation plan entries from a spec file.

    Returns an empty list if the file doesn't exist or has no index section.
    """
    if not spec_path.exists():
        return []

    text = spec_path.read_text(encoding="utf-8")
    header_match = _RE_INDEX_HEADER.search(text)
    if not header_match:
        return []

    # Get the section after the header
    section = text[header_match.end():]

    entries: list[IndexEntry] = []
    for m in _RE_TABLE_ROW.finditer(section):
        plan, repo, file_col, status, depends = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(4).strip(),
            m.group(5).strip(),
        )
        # Skip the header row and separator
        if plan in ("Plan", "---", "------") or plan.startswith("-"):
            continue
        # Strip backticks from file column
        file_col = file_col.strip("`")
        entries.append(
            IndexEntry(plan=plan, repo=repo, file=file_col, status=status, depends_on=depends)
        )

    return entries


def upsert_entry(spec_path: Path, entry: IndexEntry) -> None:
    """Add or update an entry in the spec's Implementation Plans table.

    Creates the section and table if they don't exist.
    Updates the row if a matching plan name already exists.
    """
    text = spec_path.read_text(encoding="utf-8")
    header_match = _RE_INDEX_HEADER.search(text)

    if not header_match:
        # Append the section
        table = _build_table([entry])
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n## Implementation Plans\n\n{table}\n"
        spec_path.write_text(text, encoding="utf-8")
        return

    # Section exists — find the table boundaries
    section_start = header_match.end()

    # Find where the table ends (next ## header or end of file)
    next_section = re.search(r"^## ", text[section_start:], re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)

    section_text = text[section_start:section_end]

    # Read existing entries
    existing = read_index(spec_path)

    # Upsert
    found = False
    for i, e in enumerate(existing):
        if e.plan == entry.plan:
            existing[i] = entry
            found = True
            break
    if not found:
        existing.append(entry)

    # Rebuild the table
    table = _build_table(existing)
    new_text = text[:section_start] + f"\n{table}\n" + text[section_end:]
    spec_path.write_text(new_text, encoding="utf-8")


def _build_table(entries: list[IndexEntry]) -> str:
    """Build a markdown table from index entries."""
    lines = [
        "| Plan | Repo | File | Status | Depends on |",
        "|------|------|------|--------|------------|",
    ]
    for e in entries:
        lines.append(
            f"| {e.plan} | {e.repo} | `{e.file}` | {e.status} | {e.depends_on} |"
        )
    return "\n".join(lines)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_spec_index.py -v`
Expected: PASS — all tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/spec_index.py tests/unit/test_spec_index.py
git commit -m "feat: add spec_index module for Implementation Plans table management"
```

### Task 3: Git helpers — subprocess wrappers

**Files:**
- Create: `src/vk/git.py`
- Create: `tests/unit/test_git.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_git.py`:

```python
"""Tests for vk.git — subprocess wrappers for git operations."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from vk.git import repo_root, add, commit, status


class TestRepoRoot:
    def test_returns_path(self) -> None:
        with patch("vk.git._run_git", return_value="/home/user/repo") as mock:
            result = repo_root()
            assert result == Path("/home/user/repo")
            mock.assert_called_once_with(["rev-parse", "--show-toplevel"])

    def test_strips_trailing_newline(self) -> None:
        with patch("vk.git._run_git", return_value="/home/user/repo\n"):
            result = repo_root()
            assert result == Path("/home/user/repo")


class TestAdd:
    def test_add_single_file(self) -> None:
        with patch("vk.git._run_git") as mock:
            add(["src/main.py"])
            mock.assert_called_once_with(["add", "src/main.py"])

    def test_add_multiple_files(self) -> None:
        with patch("vk.git._run_git") as mock:
            add(["src/a.py", "src/b.py"])
            mock.assert_called_once_with(["add", "src/a.py", "src/b.py"])


class TestCommit:
    def test_commit_with_message(self) -> None:
        with patch("vk.git._run_git") as mock:
            commit("feat: add feature")
            mock.assert_called_once_with(["commit", "-m", "feat: add feature"])


class TestStatus:
    def test_status_returns_output(self) -> None:
        with patch("vk.git._run_git", return_value="M  src/main.py\n") as mock:
            result = status()
            assert "M  src/main.py" in result
            mock.assert_called_once_with(["status", "--porcelain"])


class TestRunGitError:
    def test_subprocess_error_raises(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                repo_root()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_git.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.git'`

- [x] **Step 3: Implement src/vk/git.py**

```python
"""Git subprocess wrappers.

Thin wrappers around git commands used by the vk toolchain.
All functions raise subprocess.CalledProcessError on failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def repo_root(cwd: Path | None = None) -> Path:
    """Return the root directory of the current git repository."""
    output = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(output.strip())


def add(paths: list[str], cwd: Path | None = None) -> None:
    """Stage files for commit."""
    _run_git(["add", *paths], cwd=cwd)


def commit(message: str, cwd: Path | None = None) -> None:
    """Create a commit with the given message."""
    _run_git(["commit", "-m", message], cwd=cwd)


def status(cwd: Path | None = None) -> str:
    """Return porcelain status output."""
    return _run_git(["status", "--porcelain"], cwd=cwd)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_git.py -v`
Expected: PASS — all tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/git.py tests/unit/test_git.py
git commit -m "feat: add git subprocess wrappers — repo_root, add, commit, status"
```

### Task 4: GitHub CLI helpers — subprocess wrappers

**Files:**
- Create: `src/vk/gh.py`
- Create: `tests/unit/test_gh.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/test_gh.py`:

```python
"""Tests for vk.gh — subprocess wrappers for gh CLI operations.

These are contract tests: they verify the correct gh invocations
are constructed, using mocked subprocess calls.
"""

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from vk.gh import create_issue, close_issue, add_to_project, set_field, auth_status


class TestCreateIssue:
    def test_basic_creation(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/42") as mock:
            url = create_issue(
                repo="org/repo",
                title="Phase 1: Setup",
                body="Implementation plan body.",
                labels=["vk-ready"],
            )
            assert url == "https://github.com/org/repo/issues/42"
            mock.assert_called_once_with([
                "issue", "create",
                "--repo", "org/repo",
                "--title", "Phase 1: Setup",
                "--body", "Implementation plan body.",
                "--label", "vk-ready",
            ])

    def test_multiple_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/43") as mock:
            create_issue(
                repo="org/repo",
                title="Task",
                body="Body.",
                labels=["vk-ready", "manual"],
            )
            args = mock.call_args[0][0]
            assert args.count("--label") == 2

    def test_no_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="url") as mock:
            create_issue(repo="org/repo", title="T", body="B", labels=[])
            args = mock.call_args[0][0]
            assert "--label" not in args


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            close_issue(repo="org/repo", number=42)
            mock.assert_called_once_with([
                "issue", "close",
                "--repo", "org/repo",
                "42",
            ])


class TestAddToProject:
    def test_add(self) -> None:
        with patch("vk.gh._run_gh", return_value="item-id-123") as mock:
            item_id = add_to_project(
                url="https://github.com/org/repo/issues/42",
                project_owner="org",
                project_number=5,
            )
            assert item_id == "item-id-123"
            mock.assert_called_once_with([
                "project", "item-add",
                "5",
                "--owner", "org",
                "--url", "https://github.com/org/repo/issues/42",
                "--format", "json",
            ])


class TestSetField:
    def test_set_text_field(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            set_field(
                project_owner="org",
                project_number=5,
                item_id="item-123",
                field_name="Status",
                field_value="In Progress",
            )
            mock.assert_called_once_with([
                "project", "item-edit",
                "--owner", "org",
                "--project-id", "5",
                "--id", "item-123",
                "--field-name", "Status",
                "--field-value", "In Progress",
            ])


class TestAuthStatus:
    def test_authenticated(self) -> None:
        with patch("vk.gh._run_gh", return_value="github.com\n  Logged in") as mock:
            result = auth_status()
            assert result is True
            mock.assert_called_once_with(["auth", "status"])

    def test_not_authenticated(self) -> None:
        with patch(
            "vk.gh._run_gh",
            side_effect=subprocess.CalledProcessError(1, "gh"),
        ):
            result = auth_status()
            assert result is False


class TestRunGhError:
    def test_subprocess_error_propagates(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "gh"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                create_issue(repo="org/repo", title="T", body="B", labels=[])
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_gh.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.gh'`

- [x] **Step 3: Implement src/vk/gh.py**

```python
"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
All functions (except auth_status) raise subprocess.CalledProcessError
on failure.  No direct GitHub API usage — we leverage gh's existing auth.
"""

from __future__ import annotations

import subprocess


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def create_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> str:
    """Create a GitHub Issue and return its URL."""
    args = [
        "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        args.extend(["--label", label])
    return _run_gh(args)


def close_issue(*, repo: str, number: int) -> None:
    """Close a GitHub Issue by number."""
    _run_gh([
        "issue", "close",
        "--repo", repo,
        str(number),
    ])


def add_to_project(
    *,
    url: str,
    project_owner: str,
    project_number: int,
) -> str:
    """Add an issue to a GitHub Project board and return the item ID."""
    return _run_gh([
        "project", "item-add",
        str(project_number),
        "--owner", project_owner,
        "--url", url,
        "--format", "json",
    ])


def set_field(
    *,
    project_owner: str,
    project_number: int,
    item_id: str,
    field_name: str,
    field_value: str,
) -> None:
    """Set a field value on a project board item."""
    _run_gh([
        "project", "item-edit",
        "--owner", project_owner,
        "--project-id", str(project_number),
        "--id", item_id,
        "--field-name", field_name,
        "--field-value", field_value,
    ])


def auth_status() -> bool:
    """Check if gh is authenticated.  Returns True if logged in."""
    try:
        _run_gh(["auth", "status"])
        return True
    except subprocess.CalledProcessError:
        return False
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_gh.py -v`
Expected: PASS — all tests pass

- [x] **Step 5: Commit**

```bash
git add src/vk/gh.py tests/unit/test_gh.py
git commit -m "feat: add gh CLI subprocess wrappers — issues, projects, auth"
```

### Task 5: Final quality gates and coverage check

**Files:**
- No new files — validation only

- [x] **Step 1: Run full test suite with coverage**

Run: `uv run pytest -v --cov=vk --cov-report=term-missing`
Expected: PASS — all tests pass, coverage >=85% on `src/vk/`

- [x] **Step 2: Run ruff lint and format check**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: PASS — no lint or format errors. If there are errors, fix them.

- [x] **Step 3: Run mypy strict type checking**

Run: `uv run mypy src/`
Expected: PASS — no type errors. If there are errors, fix them.

- [x] **Step 4: Fix any lint, format, or type errors**

Address all issues found in steps 1-3. Common fixes:
- Add missing type annotations
- Fix import ordering
- Add `from __future__ import annotations` where needed
- Fix line length violations

- [x] **Step 5: Commit fixes and verify clean**

```bash
git add -u
git commit -m "fix: resolve all lint, format, and type errors across P1 modules"
```

Run all gates one final time:

```bash
uv run pytest -v && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/
```

Expected: all green, coverage >=85%.
