# Label Lifecycle Fix Phase 1 Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-27-label-lifecycle-fix-design.md`
**Status:** Not Started

**Goal:** Make the dispatched-Issue lifecycle (`vk-ready → in-progress → pr-ready → closed`) self-contained inside `vk` and `vk-execute`, with canonical label colors and descriptions sourced from a single registry. After this plan ships, an agent in any repo running `vk-execute` flips its Issue through the lifecycle without depending on a harness-specific bridge, and dispatch bootstraps the full label set with consistent colors.

**Architecture:** Add a label registry module (`src/vk/labels.py`) that defines `LabelDef`s for every lifecycle and metadata label. Extend `gh.py` with a new `swap_issue_labels` helper, a richer `GhError` carrying stderr/returncode for retry classification, an `is_transient` classifier, and a `with_retry` helper. Wire `vk dispatch` to bootstrap labels with registry colors and to include `in-progress` / `pr-ready` in `required_labels`. Add two new `vk execute` subcommands (`claim`, `pr-opened`) that consume the helpers, with idempotency, network-only retry, and hard-fail with actionable messages on persistent errors. Update the `vk-execute` skill to call them at the right procedure points and remove the "best-effort" footnote. Bump the plugin version (minor — new user-visible subcommands).

**Tech Stack:** Python 3.11+, Typer, `gh` CLI, pytest.

**PR strategy:** Each phase ships as its own PR via the project's branch + PR workflow. Phase 4 contains the version bump, so it must merge last. Phase 2 and Phase 3 are independent of each other and may dispatch in parallel after Phase 1 lands.

> **Note added during dispatch:** The dispatch label scheme was changed to a three-tier identifier hierarchy: `spec:<spec-slug>` + `plan:<plan-name>` + `phase:<n>`. The derivation helpers `derive_spec_slug` and `derive_plan_name` already live in `src/vk/plan/filename.py`, and `dispatch_cmd.py` already emits the new scheme (see spec §1 "Identifier hierarchy" and §3). Phase 1 below should:
> - Add `spec_label(spec_slug)`, `plan_label(plan_name)`, and `phase_label(n)` templated helpers in the new `labels.py` registry (was: only `plan_label(slug)` and `phase_label(n)`).
> - In Phase 2's dispatch test cases, assert all three identifier labels (`spec:<>`, `plan:<>`, `phase:<n>`) appear in `required_labels` — not just `plan:<full-slug>` and `phase:<n>`.
> - Where this plan's existing tasks reference `plan_label(slug)`, read it as the new `plan_label(plan_name)` semantics, plus a peer `spec_label(spec_slug)` call. The `name_to_def` map in dispatch's bootstrap should look up the new label strings (`spec:<>`, `plan:<>`, `phase:<>`) — the registry's templated helpers know their canonical colors.

---

## Phase 1: Label registry and gh helpers [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/57 -->
**Depends on:** —

**Context:** Foundation work — no behavior change yet. Both Phase 2 (dispatch bootstrap) and Phase 3 (claim / pr-opened) consume the registry and the new `swap_issue_labels` / `with_retry` helpers. Splitting this off keeps the downstream phases focused on their actual feature work and makes the registry's color/description choices reviewable in isolation.

### Task 1: `src/vk/labels.py` registry

**Files:**
- Add: `src/vk/labels.py`
- Add: `tests/unit/test_labels.py`

- [x] **Step 1: TDD — registry tests**

`tests/unit/test_labels.py`:

```python
"""Tests for the canonical label registry."""

from __future__ import annotations

import re

import pytest

from vk import labels


HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


class TestLabelDef:
    def test_all_constants_have_six_char_hex_color(self) -> None:
        for ld in (labels.VK_READY, labels.MANUAL, labels.IN_PROGRESS,
                   labels.PR_READY, labels.VK_SYNCED):
            assert HEX_RE.match(ld.color), f"{ld.name}: bad color {ld.color!r}"

    def test_all_constants_have_non_empty_description(self) -> None:
        for ld in (labels.VK_READY, labels.MANUAL, labels.IN_PROGRESS,
                   labels.PR_READY, labels.VK_SYNCED):
            assert ld.description, f"{ld.name}: empty description"

    def test_lifecycle_names_are_unique(self) -> None:
        names = [labels.VK_READY.name, labels.MANUAL.name,
                 labels.IN_PROGRESS.name, labels.PR_READY.name,
                 labels.VK_SYNCED.name]
        assert len(names) == len(set(names))

    def test_lifecycle_names_match_spec(self) -> None:
        assert labels.VK_READY.name    == "vk-ready"
        assert labels.MANUAL.name      == "manual"
        assert labels.IN_PROGRESS.name == "in-progress"
        assert labels.PR_READY.name    == "pr-ready"
        assert labels.VK_SYNCED.name   == "vk-synced"


class TestSpecLabel:
    def test_renders_name(self) -> None:
        assert labels.spec_label("foo").name == "spec:foo"

    def test_color_is_canonical(self) -> None:
        assert labels.spec_label("foo").color == labels.SPEC_LABEL_COLOR

    def test_description_includes_slug(self) -> None:
        assert "foo" in labels.spec_label("foo").description


class TestPlanLabel:
    def test_renders_name(self) -> None:
        assert labels.plan_label("foo").name == "plan:foo"

    def test_color_is_canonical(self) -> None:
        assert labels.plan_label("foo").color == labels.PLAN_LABEL_COLOR

    def test_description_includes_name(self) -> None:
        assert "foo" in labels.plan_label("foo").description


class TestPhaseLabel:
    def test_renders_name(self) -> None:
        assert labels.phase_label(3).name == "phase:3"

    def test_color_is_canonical(self) -> None:
        assert labels.phase_label(3).color == labels.PHASE_LABEL_COLOR

    def test_description_includes_number(self) -> None:
        assert "3" in labels.phase_label(3).description


class TestRegistryLookup:
    def test_lifecycle_dict_keys_are_role_names(self) -> None:
        assert set(labels.LIFECYCLE.keys()) == {
            "vk_ready", "manual", "in_progress", "pr_ready"
        }

    def test_lifecycle_values_match_module_constants(self) -> None:
        assert labels.LIFECYCLE["vk_ready"]    is labels.VK_READY
        assert labels.LIFECYCLE["manual"]      is labels.MANUAL
        assert labels.LIFECYCLE["in_progress"] is labels.IN_PROGRESS
        assert labels.LIFECYCLE["pr_ready"]    is labels.PR_READY
```

- [x] **Step 2: Implement `src/vk/labels.py`**

```python
"""Canonical label registry — single source of truth for label colors,
descriptions, and dynamic templates used across vk dispatch, vk execute,
and vk admin labels-sync.

Color scheme (lifecycle gradient, board reads visually as a progression):
  vk-ready     blue    queued for an agent to pick up
  in-progress  orange  agent is actively working
  pr-ready     green   PR is open, awaiting review

manual is gray (human-only). vk-synced is olive (system metadata, set by
the vk-issue-bridge). plan:<slug> is dark red (already in the wild,
preserved for compat). phase:<n> is yellow (attribute, not state).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelDef:
    name: str           # the GitHub label string
    color: str          # 6-char hex without leading #
    description: str    # surfaces in the GitHub UI


# Lifecycle states (mutually exclusive — at most one on a given Issue)
VK_READY    = LabelDef("vk-ready",    "0E8AE6", "Queued for an agent to pick up")
MANUAL      = LabelDef("manual",      "BFBFBF", "Human-only; not routable to an agent")
IN_PROGRESS = LabelDef("in-progress", "D93F0B", "An agent is actively working on this")
PR_READY    = LabelDef("pr-ready",    "0E8A16", "PR is open; awaiting review")

# Bridge-managed (set by vk-issue-bridge after VK board sync)
VK_SYNCED   = LabelDef("vk-synced",   "6A630D", "Synced to VK board")

# Templated label colors (name is dynamic)
SPEC_LABEL_COLOR  = "B60205"
PLAN_LABEL_COLOR  = "1D76DB"
PHASE_LABEL_COLOR = "FBCA04"


def spec_label(spec_slug: str) -> LabelDef:
    """Return the LabelDef for `spec:<spec-slug>` (the umbrella identifier
    rolling up every Issue across every plan under one spec)."""
    return LabelDef(f"spec:{spec_slug}", SPEC_LABEL_COLOR, f"Part of spec {spec_slug}")


def plan_label(plan_name: str) -> LabelDef:
    """Return the LabelDef for `plan:<plan-name>` (the per-plan identifier
    within a spec; falls back to `phase-N` for descriptor-less plan
    filenames — see `derive_plan_name`)."""
    return LabelDef(f"plan:{plan_name}", PLAN_LABEL_COLOR, f"Plan: {plan_name}")


def phase_label(n: int) -> LabelDef:
    """Return the LabelDef for `phase:<n>` (the internal phase number
    within a plan)."""
    return LabelDef(f"phase:{n}", PHASE_LABEL_COLOR, f"Plan phase {n}")


# Role-name → LabelDef map. Keyed so dispatch.labels.<role> overrides apply
# cleanly. The dispatch config defaults must mirror these keys.
LIFECYCLE: dict[str, LabelDef] = {
    "vk_ready":    VK_READY,
    "manual":      MANUAL,
    "in_progress": IN_PROGRESS,
    "pr_ready":    PR_READY,
}
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_labels.py -q --no-cov
```

Expected: 11 passed.

### Task 2: `GhError` carries stderr and returncode

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

**Context:** The retry classifier in Task 4 needs to distinguish transient (5xx, network) from persistent (4xx, auth) failures by inspecting stderr. Today `GhError` is a bare `Exception` with just a message string — the original `subprocess.CalledProcessError`'s stderr and returncode are lost. Extend `GhError` to keep them.

- [x] **Step 1: TDD — `GhError` carries fields**

Add to `tests/unit/test_gh.py`:

```python
class TestGhErrorFields:
    def test_default_stderr_and_returncode(self) -> None:
        err = gh.GhError("boom")
        assert err.stderr == ""
        assert err.returncode == 0
        assert str(err) == "boom"

    def test_explicit_stderr_and_returncode(self) -> None:
        err = gh.GhError("boom", stderr="HTTP 503\n", returncode=1)
        assert err.stderr == "HTTP 503\n"
        assert err.returncode == 1
        assert str(err) == "boom"

    def test_run_gh_populates_fields_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess
        def fake_run(*a, **kw):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                returncode=1, cmd=["gh"], output="", stderr="HTTP 403\n"
            )
        monkeypatch.setattr(gh.subprocess, "run", fake_run)
        with pytest.raises(gh.GhError) as exc_info:
            gh._run_gh(["api", "user"])
        assert exc_info.value.stderr == "HTTP 403\n"
        assert exc_info.value.returncode == 1
```

- [x] **Step 2: Extend `GhError` and `_run_gh`**

Replace the `GhError` class and update `_run_gh` in `src/vk/gh.py`:

```python
class GhError(Exception):
    """Error from a gh CLI invocation."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int = 0) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout. Raises GhError on failure."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"gh exited with code {exc.returncode}"
        raise GhError(msg, stderr=exc.stderr or "", returncode=exc.returncode) from exc
    return result.stdout.strip()
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_gh.py -q --no-cov
```

Expected: existing tests still pass + 3 new ones green.

### Task 3: `gh.swap_issue_labels` helper

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

**Context:** `gh.edit_issue_labels` is add-only (`gh.py:198-208`). The lifecycle transitions need add + remove in one call. New helper, narrow contract.

- [x] **Step 1: TDD — `swap_issue_labels`**

Add to `tests/unit/test_gh.py`:

```python
class TestSwapIssueLabels:
    def test_emits_add_and_remove_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []
        def fake_run(args: list[str]) -> str:
            captured.append(args)
            return ""
        monkeypatch.setattr(gh, "_run_gh", fake_run)
        gh.swap_issue_labels(
            repo="o/r", number=42,
            add=["pr-ready"], remove=["in-progress", "vk-ready"],
        )
        assert captured == [[
            "issue", "edit", "42", "--repo", "o/r",
            "--add-label", "pr-ready",
            "--remove-label", "in-progress",
            "--remove-label", "vk-ready",
        ]]

    def test_empty_add_and_remove_is_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []
        monkeypatch.setattr(gh, "_run_gh",
                            lambda args: captured.append(args) or "")
        gh.swap_issue_labels(repo="o/r", number=42, add=[], remove=[])
        assert captured == []

    def test_propagates_gh_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(args: list[str]) -> str:
            raise gh.GhError("HTTP 404", stderr="HTTP 404\n", returncode=1)
        monkeypatch.setattr(gh, "_run_gh", fake_run)
        with pytest.raises(gh.GhError):
            gh.swap_issue_labels(repo="o/r", number=42,
                                 add=["x"], remove=[])
```

- [x] **Step 2: Implement `swap_issue_labels`**

Add to `src/vk/gh.py` (next to `edit_issue_labels`):

```python
def swap_issue_labels(
    *,
    repo: str,
    number: int,
    add: list[str],
    remove: list[str],
) -> None:
    """Add and remove labels on an Issue in a single gh call.

    No-op if both lists are empty. Failure propagates as GhError.
    """
    if not add and not remove:
        return
    args = ["issue", "edit", str(number), "--repo", repo]
    for lbl in add:
        args.extend(["--add-label", lbl])
    for lbl in remove:
        args.extend(["--remove-label", lbl])
    _run_gh(args)
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_gh.py::TestSwapIssueLabels -q --no-cov
```

Expected: 3 passed.

### Task 4: `is_transient` classifier and `with_retry` helper

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

**Context:** Phase 3's `claim` / `pr-opened` retry on network failures only. Permanent failures (auth, 404) hard-fail immediately. Classifier looks at stderr text — pragmatic, well-tested. Backoff: 1s, 2s, 4s (≤3 attempts, ~7s total worst-case).

- [x] **Step 1: TDD — classifier and retry**

Add to `tests/unit/test_gh.py`:

```python
class TestIsTransient:
    @pytest.mark.parametrize("stderr", [
        "HTTP 500: server error",
        "HTTP 502 Bad Gateway",
        "HTTP 503: temporarily unavailable",
        "could not resolve host: api.github.com",
        "connection reset by peer",
        "connection refused",
        "i/o timeout",
    ])
    def test_returns_true_for_transient(self, stderr: str) -> None:
        err = gh.GhError("x", stderr=stderr, returncode=1)
        assert gh.is_transient(err)

    @pytest.mark.parametrize("stderr", [
        "HTTP 401: Bad credentials",
        "HTTP 403: forbidden",
        "HTTP 404: not found",
        "validation failed",
        "label already exists",
        "",
    ])
    def test_returns_false_for_permanent(self, stderr: str) -> None:
        err = gh.GhError("x", stderr=stderr, returncode=1)
        assert not gh.is_transient(err)


class TestWithRetry:
    def test_succeeds_first_try(self) -> None:
        calls = {"n": 0}
        def op() -> str:
            calls["n"] += 1
            return "ok"
        assert gh.with_retry(op) == "ok"
        assert calls["n"] == 1

    def test_retries_transient_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[float] = []
        monkeypatch.setattr(gh.time, "sleep", lambda s: slept.append(s))
        attempts = {"n": 0}
        def op() -> str:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise gh.GhError("x", stderr="HTTP 503", returncode=1)
            return "ok"
        assert gh.with_retry(op) == "ok"
        assert attempts["n"] == 3
        assert slept == [1.0, 2.0]  # backoff before attempts 2 and 3

    def test_gives_up_after_max_attempts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        def op() -> str:
            raise gh.GhError("x", stderr="HTTP 503", returncode=1)
        with pytest.raises(gh.GhError):
            gh.with_retry(op)

    def test_no_retry_on_permanent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[float] = []
        monkeypatch.setattr(gh.time, "sleep", lambda s: slept.append(s))
        attempts = {"n": 0}
        def op() -> str:
            attempts["n"] += 1
            raise gh.GhError("x", stderr="HTTP 403", returncode=1)
        with pytest.raises(gh.GhError):
            gh.with_retry(op)
        assert attempts["n"] == 1
        assert slept == []
```

- [x] **Step 2: Implement classifier and retry**

Add to `src/vk/gh.py` (top: `import time`):

```python
import time

_TRANSIENT_PATTERNS = (
    "http 5",            # 500, 502, 503, 504, ...
    "could not resolve",
    "connection reset",
    "connection refused",
    "timeout",
    "temporarily unavailable",
)


def is_transient(err: GhError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast)."""
    text = (err.stderr + " " + str(err)).lower()
    return any(p in text for p in _TRANSIENT_PATTERNS)


def with_retry(
    op: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> T:
    """Run `op`; retry on transient GhError with backoff. Re-raise the
    last error if max_attempts is exhausted or the error is permanent.

    `backoff_seconds[i]` is the sleep before attempt i+1 (i.e. the gap
    between attempt i and attempt i+1)."""
    attempt = 0
    while True:
        try:
            return op()
        except GhError as exc:
            attempt += 1
            if attempt >= max_attempts or not is_transient(exc):
                raise
            time.sleep(backoff_seconds[attempt - 1])
```

Add type imports at top of file:

```python
from typing import Callable, TypeVar

T = TypeVar("T")
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_gh.py -q --no-cov
```

Expected: existing + 11 new (`TestIsTransient` 14 parametrised + `TestWithRetry` 4) — should all pass.

### Task 5: Format, type-check, full unit suite, commit

**Files:**
- Modify: nothing — verification only.

- [x] **Step 1: Format and type-check**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

Expected: clean.

- [x] **Step 2: Full unit suite**

```bash
uv run pytest -q --no-cov
```

Expected: green.

- [x] **Step 3: Commit**

```bash
git checkout -b phase-1-label-registry-and-gh-helpers
git add src/vk/labels.py src/vk/gh.py tests/unit/test_labels.py tests/unit/test_gh.py
git commit -m "feat(labels): registry module + gh helpers (swap_issue_labels, with_retry)"
git push -u origin phase-1-label-registry-and-gh-helpers
gh pr create --title "Phase 1 · Label registry and gh helpers" \
  --body "Foundation for the label-lifecycle-fix spec. No behavior change yet."
```

---

## Phase 2: DispatchConfig defaults and dispatch reads registry [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/58 -->
**Depends on:** Phase 1

**Context:** With the registry available, dispatch's bootstrap can drop its hardcoded label-list build and instead enumerate registry labels for `ensure_labels`. Two new keys (`in_progress`, `pr_ready`) join `agentic` and `manual` in `DispatchConfig.labels`. Existing `plan-config.yaml` files that override only `agentic`/`manual` continue to work — defaults merge in for missing keys.

### Task 1: Extend `DispatchConfig.labels` defaults

**Files:**
- Modify: `src/vk/config.py`
- Modify: `tests/unit/test_config.py`

- [x] **Step 1: TDD — defaults include new keys, user override merges**

Add to `tests/unit/test_config.py`:

```python
class TestDispatchLabelDefaults:
    def test_default_includes_all_four_lifecycle_keys(self) -> None:
        cfg = DispatchConfig()
        assert cfg.labels == {
            "agentic":     "vk-ready",
            "manual":      "manual",
            "in_progress": "in-progress",
            "pr_ready":    "pr-ready",
        }

    def test_yaml_partial_override_merges_with_defaults(self) -> None:
        # Simulates a user plan-config.yaml with only old keys present
        raw = {"target": "github-issues", "owner": "o",
               "labels": {"agentic": "ready", "manual": "human-only"}}
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        assert cfg.labels["agentic"]     == "ready"        # override
        assert cfg.labels["manual"]      == "human-only"   # override
        assert cfg.labels["in_progress"] == "in-progress"  # default
        assert cfg.labels["pr_ready"]    == "pr-ready"     # default

    def test_yaml_full_override(self) -> None:
        raw = {"target": "github-issues", "owner": "o",
               "labels": {"agentic": "a", "manual": "m",
                          "in_progress": "ip", "pr_ready": "pr"}}
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        assert cfg.labels == {"agentic": "a", "manual": "m",
                              "in_progress": "ip", "pr_ready": "pr"}
```

(The test file already imports `DispatchConfig` and `_parse_dispatch`; if not, add at top.)

- [x] **Step 2: Update `DispatchConfig` and `_parse_dispatch`**

In `src/vk/config.py`, replace the `labels` field default:

```python
labels: dict[str, str] = field(
    default_factory=lambda: {
        "agentic":     "vk-ready",
        "manual":      "manual",
        "in_progress": "in-progress",
        "pr_ready":    "pr-ready",
    }
)
```

Update `_parse_dispatch` to merge user overrides over defaults:

```python
default_labels = {
    "agentic":     "vk-ready",
    "manual":      "manual",
    "in_progress": "in-progress",
    "pr_ready":    "pr-ready",
}
return DispatchConfig(
    owner=raw.get("owner", "derio-net"),
    project_board=raw.get("project_board", "Derio Ops"),
    default_repo=raw.get("default_repo", ""),
    target=raw.get("target", "github-issues"),
    labels={**default_labels, **(raw.get("labels") or {})},
)
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_config.py -q --no-cov
```

Expected: existing + 3 new pass.

### Task 2: Dispatch bootstraps full registry with canonical colors

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `src/vk/gh.py`
- Modify: `tests/integration/test_dispatch.py`
- Modify: `tests/unit/test_gh.py`

**Context:** `gh.ensure_labels` currently takes `list[str]` and uses default gray (`ededed`) for color and empty description. To use registry colors, refactor `ensure_labels` to take `list[LabelDef]`. Update both callsites in `dispatch_cmd.py` (Issue create and migrate paths). For label strings that aren't in the registry (operator-overridden custom names), wrap in a default `LabelDef` with the original gray.

- [x] **Step 1: TDD — `ensure_labels` accepts `LabelDef`s**

Replace existing `TestEnsureLabels` in `tests/unit/test_gh.py` (or add new tests if the existing ones are signature-compatible) with:

```python
class TestEnsureLabels:
    def test_calls_ensure_label_per_def_with_color_and_desc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vk.labels import LabelDef
        captured: list[dict] = []
        def fake_ensure(*, repo: str, name: str, color: str = "ededed",
                        description: str = "") -> None:
            captured.append({"repo": repo, "name": name,
                             "color": color, "description": description})
        monkeypatch.setattr(gh, "ensure_label", fake_ensure)
        defs = [
            LabelDef("vk-ready", "0E8AE6", "queued"),
            LabelDef("phase:1",  "FBCA04", "phase 1"),
        ]
        gh.ensure_labels(repo="o/r", labels=defs)
        assert captured == [
            {"repo": "o/r", "name": "vk-ready", "color": "0E8AE6", "description": "queued"},
            {"repo": "o/r", "name": "phase:1",  "color": "FBCA04", "description": "phase 1"},
        ]

    def test_empty_list_is_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"n": 0}
        monkeypatch.setattr(gh, "ensure_label",
                            lambda **kw: called.__setitem__("n", called["n"] + 1))
        gh.ensure_labels(repo="o/r", labels=[])
        assert called["n"] == 0

    def test_first_failure_propagates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vk.labels import LabelDef
        seen: list[str] = []
        def fake_ensure(*, repo: str, name: str, color: str = "ededed",
                        description: str = "") -> None:
            seen.append(name)
            if name == "phase:1":
                raise gh.GhError("nope", stderr="", returncode=1)
        monkeypatch.setattr(gh, "ensure_label", fake_ensure)
        defs = [LabelDef("vk-ready", "0E8AE6", ""),
                LabelDef("phase:1",  "FBCA04", ""),
                LabelDef("phase:2",  "FBCA04", "")]
        with pytest.raises(gh.GhError):
            gh.ensure_labels(repo="o/r", labels=defs)
        assert seen == ["vk-ready", "phase:1"]  # third never reached
```

- [x] **Step 2: Update `gh.ensure_labels` signature**

In `src/vk/gh.py`:

```python
def ensure_labels(*, repo: str, labels: list[LabelDef]) -> None:
    """Ensure every label exists on the repo with the right color and
    description. First failure propagates."""
    for ld in labels:
        ensure_label(repo=repo, name=ld.name, color=ld.color,
                     description=ld.description)
```

Add `from vk.labels import LabelDef` to the imports.

- [x] **Step 3: TDD — `dispatch create` builds full registry list**

Add to `tests/integration/test_dispatch.py`:

```python
class TestDispatchUsesLabelRegistry:
    def test_required_labels_includes_in_progress_and_pr_ready(
        self, ...  # existing fixture for a minimal phased plan
    ) -> None:
        # Run vk dispatch create against a fake plan with 2 phases.
        # Assert ensure_labels was called with LabelDefs whose .name set ==
        # {"vk-ready", "manual", "in-progress", "pr-ready",
        #  "plan:<slug>", "phase:1", "phase:2"}
        ...

    def test_lifecycle_labels_use_registry_colors(self, ...) -> None:
        # Assert the LabelDef passed for vk-ready has color 0E8AE6,
        # in-progress D93F0B, etc. — sourced from labels module, not
        # hardcoded in dispatch_cmd.
        ...

    def test_yaml_override_for_label_string_falls_back_to_default_color(
        self, ...
    ) -> None:
        # plan-config.yaml has labels.agentic: "queued" (custom name).
        # Assert ensure_labels gets a LabelDef("queued", "ededed", "")
        # — not in registry → default color, empty description.
        ...
```

(The existing `tests/integration/test_dispatch.py` has fixtures and helper functions to mock `gh` calls — reuse them. Sketch left high-level here; the implementing agent fills in the test bodies using the existing pattern.)

- [x] **Step 4: Update `dispatch_cmd.py`**

Refactor `dispatch_cmd.py`'s `required_labels` build to consume the registry. The
spec/plan label derivation already lives in `dispatch_cmd.py` (the `spec_plan_labels`
list, set up earlier from `derive_spec_slug` / `derive_plan_name`). This task wraps the
existing string list in registry-aware `LabelDef`s so colors and descriptions land too:

```python
from vk import labels as _labels

# ... inside dispatch_create, after dispatch_cfg is loaded ...

agentic_name     = dispatch_cfg.labels.get("agentic",     "vk-ready")
manual_name      = dispatch_cfg.labels.get("manual",      "manual")
in_progress_name = dispatch_cfg.labels.get("in_progress", "in-progress")
pr_ready_name    = dispatch_cfg.labels.get("pr_ready",    "pr-ready")

# Map configured names to registry LabelDefs where possible; fall back
# to a default LabelDef (gray, no description) for operator-overridden
# names that aren't in the registry.
def _def_for(name: str, registry_def: _labels.LabelDef) -> _labels.LabelDef:
    if name == registry_def.name:
        return registry_def
    return _labels.LabelDef(name, "ededed", "")

# Identifier hierarchy: spec:<spec-slug> + plan:<plan-name> + phase:<n>.
# `plan.spec` is None for legacy spec-less plans → fall back to single-label
# `plan:<full-slug>` (preserves the pre-three-tier behavior for old repos).
identifier_defs: list[_labels.LabelDef] = []
if plan.spec:
    spec_slug = derive_spec_slug(Path(plan.spec))
    plan_name = derive_plan_name(plan_path_resolved, spec_slug)
    identifier_defs.append(_labels.spec_label(spec_slug))
    identifier_defs.append(_labels.plan_label(plan_name))
else:
    identifier_defs.append(_labels.plan_label(derive_slug(plan_path_resolved)))

required_labels: list[_labels.LabelDef] = [
    _def_for(agentic_name,     _labels.VK_READY),
    _def_for(manual_name,      _labels.MANUAL),
    _def_for(in_progress_name, _labels.IN_PROGRESS),
    _def_for(pr_ready_name,    _labels.PR_READY),
    *identifier_defs,
    *(_labels.phase_label(p.number) for p in plan.phases),
]
required_labels = sorted(required_labels, key=lambda d: d.name)

try:
    gh.ensure_labels(repo=target_repo, labels=required_labels)
except gh.GhError as exc:
    err_console.print(f"Error: Could not ensure labels on {target_repo}: {exc}")
    raise typer.Exit(4) from exc
```

Update the `dispatch migrate` callsite (line 543-548) similarly: build `[plan_label(slug), phase_label(r['phase_number'])]` and call `ensure_labels` with those.

- [x] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_gh.py tests/integration/test_dispatch.py -q --no-cov
```

Expected: green.

### Task 3: Format, type-check, full suite, commit

- [x] **Step 1: Format, type-check, full suite**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest -q --no-cov
```

Expected: clean / green.

- [ ] **Step 2: Commit**

```bash
git checkout -b phase-2-dispatch-reads-registry
git add src/vk/config.py src/vk/gh.py src/vk/commands/dispatch_cmd.py tests/
git commit -m "feat(dispatch): bootstrap full lifecycle label set with registry colors"
git push -u origin phase-2-dispatch-reads-registry
gh pr create --title "Phase 2 · Dispatch reads label registry" \
  --body "Wires labels.LIFECYCLE into dispatch's required_labels and ensures registry colors land on every dispatched repo. Depends on Phase 1."
```

---

## Phase 3: vk execute claim and pr-opened [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/59 -->
**Depends on:** Phase 1

**Context:** The substantial feature work. Two new subcommands flip the Issue between lifecycle states with idempotency, network-only retry, and hard-fail on persistent errors. `claim` is called between procedure steps 1 (check-deps) and 2 (scope) of vk-execute; `pr-opened` is called after step 6 (`gh pr create` succeeds).

### Task 1: `vk execute claim`

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Add: `tests/unit/test_execute_claim.py`

- [x] **Step 1: TDD — claim test cases**

`tests/unit/test_execute_claim.py`:

```python
"""Tests for `vk execute claim`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from vk.commands.execute_cmd import execute_app
from vk import gh, labels


runner = CliRunner()


def _stub_run_gh(monkeypatch: pytest.MonkeyPatch, responses: list):
    """Configure gh._run_gh to return / raise the given responses in order.

    Each response is either a string (stdout) or an exception to raise.
    Captures the args of every call into the returned list.
    """
    calls: list[list[str]] = []
    iterator = iter(responses)
    def fake(args: list[str]) -> str:
        calls.append(args)
        r = next(iterator)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(gh, "_run_gh", fake)
    return calls


def _labels_json(*names: str) -> str:
    return json.dumps({"labels": [{"name": n} for n in names]})


class TestClaimColdStart:
    def test_flips_vk_ready_to_in_progress(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("vk-ready", "plan:foo", "phase:1"),  # gh issue view
            "",  # gh label create --force (ensure in-progress)
            "",  # gh issue edit --add-label in-progress --remove-label vk-ready
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
        # Final call swaps the labels:
        last = calls[-1]
        assert "issue" in last and "edit" in last
        assert "--add-label" in last and "in-progress" in last
        assert "--remove-label" in last and "vk-ready" in last


class TestClaimIdempotent:
    def test_already_in_progress_is_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("in-progress", "plan:foo", "phase:1"),
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
        assert "already in-progress" in result.stdout.lower()
        assert len(calls) == 1  # only the view call, no edits


class TestClaimSelfHeal:
    def test_creates_in_progress_label_if_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("vk-ready"),  # view
            "",                        # ensure_label create
            "",                        # swap edit
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
        # Second call is the label create:
        assert calls[1][:3] == ["label", "create", labels.IN_PROGRESS.name]
        assert "--force" in calls[1]
        assert "--color" in calls[1]


class TestClaimManualHardFail:
    def test_manual_label_present_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_run_gh(monkeypatch, [
            _labels_json("manual", "plan:foo", "phase:1"),
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code != 0
        assert "manual" in result.stdout.lower()


class TestClaimNetworkRetry:
    def test_retries_on_5xx_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(monkeypatch, [
            _labels_json("vk-ready"),  # view
            "",                        # ensure_label
            gh.GhError("x", stderr="HTTP 503", returncode=1),  # edit fail 1
            gh.GhError("x", stderr="HTTP 503", returncode=1),  # edit fail 2
            "",                        # edit success
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0


class TestClaimHardFailOn403:
    def test_403_no_retry_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(monkeypatch, [
            _labels_json("vk-ready"),
            "",  # ensure_label
            gh.GhError("forbidden", stderr="HTTP 403", returncode=1),
        ])
        result = runner.invoke(execute_app, [
            "claim", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code != 0
        assert "403" in result.stdout or "forbidden" in result.stdout.lower()
```

- [x] **Step 2: Implement `claim`**

Add to `src/vk/commands/execute_cmd.py`:

```python
import json

from vk import gh, labels


def _read_issue_labels(*, repo: str, number: int) -> list[str]:
    """Return the current label names on the Issue."""
    out = gh._run_gh(["issue", "view", str(number), "--repo", repo,
                      "--json", "labels"])
    data = json.loads(out)
    return [lbl["name"] for lbl in data.get("labels", [])]


def _print_remediation(repo: str, number: int, add: list[str],
                       remove: list[str], pr_url: str | None = None) -> None:
    """Print a copy-paste recovery command after a hard-fail."""
    add_flags    = " ".join(f"--add-label {n}"    for n in add)
    remove_flags = " ".join(f"--remove-label {n}" for n in remove)
    err_console.print(
        f"\nManual recovery:\n"
        f"  gh issue edit {number} --repo {repo} {add_flags} {remove_flags}"
    )
    if pr_url:
        err_console.print(f"PR: {pr_url}")


@execute_app.command()
def claim(
    issue: int = typer.Option(..., "--issue", help="GitHub Issue number."),
    repo: str = typer.Option(..., "--repo", help="owner/repo of the Issue."),
) -> None:
    """Flip an Issue from vk-ready to in-progress.

    Called by the agent at the start of work, after `check-deps` passes.
    Idempotent: no-op if already in-progress. Hard-fails if the Issue
    carries the `manual` label.
    """
    in_progress = labels.IN_PROGRESS
    vk_ready    = labels.VK_READY
    manual      = labels.MANUAL

    try:
        current = _read_issue_labels(repo=repo, number=issue)
    except gh.GhError as exc:
        err_console.print(f"Error reading Issue #{issue} on {repo}: {exc}")
        raise typer.Exit(2) from exc

    if manual.name in current:
        err_console.print(
            f"Error: Issue #{issue} has the `{manual.name}` label; "
            f"agents do not claim manual work."
        )
        raise typer.Exit(2)

    if in_progress.name in current and vk_ready.name not in current:
        console.print(f"Issue #{issue} already {in_progress.name} (noop).")
        return

    # Self-heal: ensure the in-progress label exists on the repo.
    try:
        gh.ensure_label(repo=repo, name=in_progress.name,
                        color=in_progress.color,
                        description=in_progress.description)
    except gh.GhError as exc:
        err_console.print(
            f"Error ensuring `{in_progress.name}` label on {repo}: {exc}"
        )
        raise typer.Exit(3) from exc

    add = [in_progress.name] if in_progress.name not in current else []
    remove = [vk_ready.name] if vk_ready.name in current else []

    try:
        gh.with_retry(lambda: gh.swap_issue_labels(
            repo=repo, number=issue, add=add, remove=remove
        ))
    except gh.GhError as exc:
        err_console.print(f"Error transitioning Issue #{issue}: {exc}")
        _print_remediation(repo, issue, add, remove)
        raise typer.Exit(3) from exc

    console.print(f"Issue #{issue}: {vk_ready.name} → {in_progress.name}.")
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_execute_claim.py -q --no-cov
```

Expected: 7 passed.

### Task 2: `vk execute pr-opened`

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Add: `tests/unit/test_execute_pr_opened.py`

- [x] **Step 1: TDD — pr-opened test cases**

`tests/unit/test_execute_pr_opened.py`:

```python
"""Tests for `vk execute pr-opened`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vk.commands.execute_cmd import execute_app
from vk import gh


runner = CliRunner()


def _stub_run_gh(monkeypatch, responses):  # type: ignore[no-untyped-def]
    calls: list[list[str]] = []
    it = iter(responses)
    def fake(args: list[str]) -> str:
        calls.append(args)
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(gh, "_run_gh", fake)
    return calls


def _labels_json(*names: str) -> str:
    return json.dumps({"labels": [{"name": n} for n in names]})


class TestPrOpenedHappyPath:
    def test_in_progress_to_pr_ready(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("in-progress", "plan:foo", "phase:1"),  # view
            "",                                                  # ensure pr-ready
            "",                                                  # swap edit
        ])
        result = runner.invoke(execute_app, [
            "pr-opened", "--issue", "8", "--repo", "o/r",
            "--pr-url", "https://github.com/o/r/pull/14",
        ])
        assert result.exit_code == 0
        last = calls[-1]
        assert "--add-label" in last and "pr-ready" in last
        assert "--remove-label" in last and "in-progress" in last


class TestPrOpenedSkippedClaim:
    def test_vk_ready_directly_to_pr_ready(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover the case where claim was never run — Issue still on
        vk-ready when PR opens. Both vk-ready and any stray in-progress
        get removed; pr-ready is added."""
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("vk-ready", "plan:foo"),  # view
            "",                                    # ensure
            "",                                    # swap
        ])
        result = runner.invoke(execute_app, [
            "pr-opened", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
        last = calls[-1]
        assert "--remove-label" in last and "vk-ready" in last


class TestPrOpenedAlreadyPrReady:
    def test_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(monkeypatch, [
            _labels_json("pr-ready", "plan:foo"),
        ])
        result = runner.invoke(execute_app, [
            "pr-opened", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
        assert "already pr-ready" in result.stdout.lower()
        assert len(calls) == 1


class TestPrOpenedHardFailPrintsPrUrl:
    def test_403_includes_pr_url_and_remediation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(monkeypatch, [
            _labels_json("in-progress"),
            "",
            gh.GhError("forbidden", stderr="HTTP 403", returncode=1),
        ])
        result = runner.invoke(execute_app, [
            "pr-opened", "--issue", "8", "--repo", "o/r",
            "--pr-url", "https://github.com/o/r/pull/14",
        ])
        assert result.exit_code != 0
        assert "https://github.com/o/r/pull/14" in result.stdout
        assert "gh issue edit 8" in result.stdout


class TestPrOpenedNetworkRetry:
    def test_retries_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(monkeypatch, [
            _labels_json("in-progress"),
            "",
            gh.GhError("x", stderr="HTTP 503", returncode=1),
            "",
        ])
        result = runner.invoke(execute_app, [
            "pr-opened", "--issue", "8", "--repo", "o/r",
        ])
        assert result.exit_code == 0
```

- [x] **Step 2: Implement `pr-opened`**

Add to `src/vk/commands/execute_cmd.py`:

```python
@execute_app.command(name="pr-opened")
def pr_opened(
    issue: int = typer.Option(..., "--issue", help="GitHub Issue number."),
    repo: str = typer.Option(..., "--repo", help="owner/repo of the Issue."),
    pr_url: str | None = typer.Option(
        None, "--pr-url", help="The just-created PR URL (printed on hard-fail)."
    ),
) -> None:
    """Flip an Issue to pr-ready after `gh pr create` succeeded.

    Idempotent. Removes any prior-state label (vk-ready, in-progress).
    On hard-fail, prints the PR URL and the manual remediation command.
    """
    pr_ready    = labels.PR_READY
    in_progress = labels.IN_PROGRESS
    vk_ready    = labels.VK_READY

    try:
        current = _read_issue_labels(repo=repo, number=issue)
    except gh.GhError as exc:
        err_console.print(f"Error reading Issue #{issue} on {repo}: {exc}")
        if pr_url:
            err_console.print(f"PR: {pr_url}")
        raise typer.Exit(2) from exc

    if (pr_ready.name in current
            and in_progress.name not in current
            and vk_ready.name not in current):
        console.print(f"Issue #{issue} already {pr_ready.name} (noop).")
        return

    try:
        gh.ensure_label(repo=repo, name=pr_ready.name,
                        color=pr_ready.color, description=pr_ready.description)
    except gh.GhError as exc:
        err_console.print(
            f"Error ensuring `{pr_ready.name}` label on {repo}: {exc}"
        )
        if pr_url:
            err_console.print(f"PR: {pr_url}")
        raise typer.Exit(3) from exc

    add = [pr_ready.name] if pr_ready.name not in current else []
    remove = [n for n in (in_progress.name, vk_ready.name) if n in current]

    try:
        gh.with_retry(lambda: gh.swap_issue_labels(
            repo=repo, number=issue, add=add, remove=remove
        ))
    except gh.GhError as exc:
        err_console.print(f"Error transitioning Issue #{issue}: {exc}")
        _print_remediation(repo, issue, add, remove, pr_url=pr_url)
        raise typer.Exit(3) from exc

    console.print(f"Issue #{issue}: → {pr_ready.name}.")
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_execute_pr_opened.py -q --no-cov
```

Expected: 5 passed.

### Task 3: Format, type-check, full suite, commit

- [ ] **Step 1: Format, type-check, full suite**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest -q --no-cov
```

Expected: clean / green.

- [ ] **Step 2: Commit**

```bash
git checkout -b phase-3-execute-claim-and-pr-opened
git add src/vk/commands/execute_cmd.py tests/unit/test_execute_claim.py tests/unit/test_execute_pr_opened.py
git commit -m "feat(execute): claim and pr-opened subcommands for Issue lifecycle"
git push -u origin phase-3-execute-claim-and-pr-opened
gh pr create --title "Phase 3 · vk execute claim + pr-opened" \
  --body "Two new subcommands flip the dispatched Issue between lifecycle states with retry and hard-fail. Depends on Phase 1."
```

---

## Phase 4: vk-execute skill update and version bump [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/60 -->
**Depends on:** Phase 3

**Context:** With both subcommands shipped, update the skill to call them at the right procedure points. Remove the "best-effort" footnote — failures now hard-fail per the cross-cutting principle. Bump the plugin version (minor: new user-visible subcommands per `CLAUDE.md`'s release rule).

### Task 1: Update `skills/vk-execute/SKILL.md`

**Files:**
- Modify: `skills/vk-execute/SKILL.md`
- Modify: `tests/unit/test_skill_validation.py`

- [ ] **Step 1: TDD — skill validation asserts new shape**

Add or extend in `tests/unit/test_skill_validation.py`:

```python
class TestVkExecuteSkillReferencesLifecycleCommands:
    def test_skill_calls_vk_execute_claim(self) -> None:
        text = Path("skills/vk-execute/SKILL.md").read_text()
        assert "vk execute claim" in text

    def test_skill_calls_vk_execute_pr_opened(self) -> None:
        text = Path("skills/vk-execute/SKILL.md").read_text()
        assert "vk execute pr-opened" in text

    def test_skill_no_longer_says_best_effort(self) -> None:
        text = Path("skills/vk-execute/SKILL.md").read_text()
        assert "Best-effort" not in text
        assert "best-effort: failure does not block" not in text.lower()
```

- [ ] **Step 2: Update `skills/vk-execute/SKILL.md`**

Two changes.

(a) Replace the existing "Label lifecycle" section (currently lines 28-35) with:

```markdown
## Label lifecycle

The Issue moves through `vk-ready → in-progress → pr-ready → closed`.
`vk-execute` owns the two middle transitions. Both are dispatched-mode
only (Local mode has no Issue).

- `vk execute claim --issue <N> --repo <owner/repo>` — flips to `in-progress`.
  Called between procedure steps 1 (check-deps) and 2 (scope).
- `vk execute pr-opened --issue <N> --repo <owner/repo> --pr-url <url>` —
  flips to `pr-ready`. Called immediately after `gh pr create` succeeds.

Both are idempotent and retry on transient network errors. On persistent
failure (auth, 404, exhausted retries), they hard-fail with an actionable
error message and a manual recovery command. `pr-opened` failures also
print the PR URL so the operator can finish the transition by hand without
hunting for state.
```

(b) Update the "Procedure" list to insert the two new calls. After step 1 (`vk execute check-deps`), add:

```markdown
1.5. **Claim the Issue (dispatched mode only):**
   ```bash
   vk execute claim --issue $N --repo $REPO
   ```
```

After step 6 (`gh pr create` via `superpowers:finishing-a-development-branch`), add as step 6.5:

```markdown
6.5. **Mark Issue pr-ready (dispatched mode only):**
   ```bash
   vk execute pr-opened --issue $N --repo $REPO --pr-url $PR_URL
   ```
   Run before step 7 (VK MCP `update_issue`) so the GitHub label state is
   correct before the VK board sync, in case any board automation reads it.
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_skill_validation.py -q --no-cov
```

Expected: green.

### Task 2: Version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `uv.lock` (regenerated)

**Context:** Per `CLAUDE.md` release rule, this PR ships new user-visible subcommands → minor bump. Current version is `1.2.0` (from the vk-plan-rework feature). Bump to `1.3.0`.

- [ ] **Step 1: Confirm current version**

```bash
grep -E '"version"|^version' pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Expected: all three report `1.2.0`.

- [ ] **Step 2: Bump all three files to `1.3.0`**

In `pyproject.toml`: change `version = "1.2.0"` → `version = "1.3.0"`.
In `.claude-plugin/plugin.json`: change `"version": "1.2.0"` → `"version": "1.3.0"`.
In `.claude-plugin/marketplace.json`: change the first plugin's `"version": "1.2.0"` → `"version": "1.3.0"`.

- [ ] **Step 3: Refresh lockfile and confirm CLI**

```bash
uv sync
uv run vk --version
```

Expected: `vk --version` reports `1.3.0`.

- [ ] **Step 4: Format, type-check, full suite**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest -q --no-cov
```

Expected: clean / green.

- [ ] **Step 5: Commit and PR**

```bash
git checkout -b phase-4-skill-update-and-version-bump
git add skills/vk-execute/SKILL.md tests/unit/test_skill_validation.py \
        pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json uv.lock
git commit -m "feat: vk-execute owns label lifecycle + version bump 1.3.0"
git push -u origin phase-4-skill-update-and-version-bump
gh pr create --title "Phase 4 · vk-execute skill calls claim + pr-opened, bump 1.3.0" \
  --body "Final phase. Skill now calls the new subcommands at the right procedure points; best-effort footnote is gone. Minor bump per CLAUDE.md release rule. Depends on Phase 3."
```
