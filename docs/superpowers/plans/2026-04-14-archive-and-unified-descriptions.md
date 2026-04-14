# Archive And Unified Descriptions Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-14-archive-and-unified-descriptions-design.md`
**Status:** Not Started

**Goal:** Ship archive-on-Complete in `vk progress sync`, unified work-item descriptions across Issue/workspace/PR surfaces, and fail-loud dispatch output whose deps match the VK Issue Bridge's regex — plus a `vk dispatch migrate` command to retrofit in-flight Issues.
**Architecture:** Changes live in `src/vk/commands/{progress_cmd,dispatch_cmd}.py`, `src/vk/config.py`, and the three `skills/vk-*` SKILL.md files. TDD throughout — unit tests in `tests/unit/` gate each builder/validator change; integration tests in `tests/integration/` cover archive flow and migrate flow against mocked `gh`. Secure-agent-kali bridge changes live in a separate plan.
**Tech Stack:** Python 3.11+, uv, typer, pyyaml, pytest, ruff, mypy

---

## Phase 0: Impact audit across repos [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/9 -->

### Task 1: Enumerate title/label/body consumers

**Files:**
- Create: `docs/superpowers/2026-04-14-unified-descriptions-audit.md`

- [ ] **Step 1: Grep for slug-phase-tag title regex consumers**

Run this command from the repo root and append the raw output to a scratchpad in `/tmp/audit-title.txt`:

```bash
for repo in /home/claude/repos/superpowers-for-vk /home/claude/repos/secure-agent-kali /home/claude/repos/frank /home/claude/repos/willikins /home/claude/repos/vibe-kanban; do
  echo "=== $repo ==="
  rg -n --no-heading '(\{slug\}-\{phase\}-\{tag\}|-\d+-(?:agentic|manual))' "$repo" 2>/dev/null || true
done > /tmp/audit-title.txt
```

Expected: at least one hit in `src/vk/commands/progress_cmd.py` (the `seen_titles` regex at line 391) and one in `src/vk/commands/dispatch_cmd.py::_build_issue_title`.

- [ ] **Step 2: Grep for vk-ready / vk-synced / in-progress / pr-ready label consumers**

```bash
for repo in /home/claude/repos/superpowers-for-vk /home/claude/repos/secure-agent-kali /home/claude/repos/frank /home/claude/repos/willikins; do
  echo "=== $repo ==="
  rg -n --no-heading '(vk-ready|vk-synced|pr-ready|in-progress)' "$repo" 2>/dev/null || true
done > /tmp/audit-labels.txt
```

Expected: hits in `secure-agent-kali/scripts/vk-issue-bridge.py` (GH_LABEL_READY/SYNCED) and in `superpowers-for-vk/src/vk/commands/dispatch_cmd.py` (labels map).

- [ ] **Step 3: Enumerate open Issues with old-format titles across derio-net repos**

```bash
for repo in derio-net/superpowers-for-vk derio-net/secure-agent-kali derio-net/frank derio-net/willikins; do
  gh issue list --repo "$repo" --state open --label vk-ready --json number,title,url --limit 100 \
    | jq -r --arg R "$repo" '.[] | [$R, .number, .title, .url] | @tsv'
done > /tmp/audit-open-issues.tsv
```

Expected: a TSV with the Frank hextra phases (5 rows for #68–#72) and any other open `vk-ready` Issues.

- [ ] **Step 4: Confirm bridge is singleton**

```bash
ls -la /opt/scripts/vk-issue-bridge.py /home/claude/.local/bin/vk-issue-bridge.py /home/claude/repos/secure-agent-kali/scripts/vk-issue-bridge.py 2>&1
```

All three paths should resolve to the same inode OR the `secure-agent-kali` copy is the source of truth and the others are copies/symlinks. Record which case applies.

- [ ] **Step 5: Check willikins transition script for title parsing**

```bash
rg -n 'title|Title' /home/claude/repos/willikins/scripts/hooks/vk-lifecycle-transition.sh 2>&1
```

Expected: no hits (the script takes a URL, not a title). If hits found, note them as additional consumers.

### Task 2: Write the audit report

**Files:**
- Create: `docs/superpowers/2026-04-14-unified-descriptions-audit.md`

- [ ] **Step 1: Write the report**

Synthesize the four `/tmp/audit-*.txt` and `.tsv` outputs into a markdown report at `docs/superpowers/2026-04-14-unified-descriptions-audit.md` with these sections:

- **Title consumers found** — list each file:line that matches or parses the old title format.
- **Label consumers found** — list each file:line that reads/writes the labels.
- **Open Issues to migrate** — the TSV contents rendered as a table, plus a total count.
- **Bridge singleton status** — `secure-agent-kali/scripts/vk-issue-bridge.py` is canonical; others are (symlinks | stale copies | unrelated).
- **Additional title parsers outside expected surfaces** — anything surprising in `willikins` or `vibe-kanban`. If none: "None found."

Keep the report under 150 lines. If any consumer requires a plan scope extension, flag it explicitly with "⚠️ scope impact".

- [ ] **Step 2: Commit the audit**

```bash
git add docs/superpowers/2026-04-14-unified-descriptions-audit.md
git commit -m "docs(audit): unified-descriptions impact audit (phase 0)"
```

---

## Phase 1: Dispatch output — titles, body, labels, validator [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/10 -->

### Task 1: Body builder — tracking block and dash-prefixed deps

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `tests/unit/test_dispatch_body.py`

- [ ] **Step 1: Add failing test for tracking block in body**

Append to `tests/unit/test_dispatch_body.py` inside `class TestBuildIssueBody`:

```python
    def test_tracking_block_includes_repo_plan_spec(self) -> None:
        body = _build_issue_body(
            _make_phase(1, title="Bootstrap"),
            Path("docs/superpowers/plans/2026-04-14-feature.md"),
            "org/repo",
            prev_num=None,
            total_phases=3,
            spec="docs/superpowers/specs/2026-04-14-feature-design.md",
            goal="Build a thing that does X.",
        )
        assert "📦 Repo:   org/repo" in body
        assert "📋 Plan:   docs/superpowers/plans/2026-04-14-feature.md" in body
        assert "📐 Spec:   docs/superpowers/specs/2026-04-14-feature-design.md" in body
        assert "🎯 Phase:  1/3 — Bootstrap [agentic]" in body
        assert "**Goal (from plan):** Build a thing that does X." in body
```

Run `pytest tests/unit/test_dispatch_body.py -x 2>&1 | tail -20`. Expected: TypeError on unexpected kwargs `total_phases`/`spec`/`goal` — confirming the builder signature must be extended.

- [ ] **Step 2: Add failing test for dash-prefixed Blocked by**

Append to `TestBuildIssueBody`:

```python
    def test_dependencies_use_dash_prefix(self) -> None:
        body = _build_issue_body(
            _make_phase(2), Path("/p.md"), "org/repo",
            prev_num=42, total_phases=3, spec="s.md", goal="G.",
        )
        assert "## Dependencies\n\n- Blocked by #42" in body

    def test_phase_zero_no_blocker_line(self) -> None:
        body = _build_issue_body(
            _make_phase(0), Path("/p.md"), "org/repo",
            prev_num=None, total_phases=3, spec="s.md", goal="G.",
        )
        assert "None — no blocking phases." in body
        assert "- Blocked by" not in body
```

Run the test file; both new tests fail.

- [ ] **Step 3: Update _build_issue_body signature and body composition**

In `src/vk/commands/dispatch_cmd.py`, replace `_build_issue_body` (lines 69–112) with:

```python
def _build_issue_body(
    phase: Phase,
    plan_path: Path,
    target_repo: str,
    prev_num: int | None,
    total_phases: int,
    spec: str,
    goal: str,
) -> str:
    """Build an Issue body: tracking block + Instruction/Workspace/Dependencies.

    The body is consumed by the VK Issue Bridge, which requires the
    ``- Blocked by #N`` dash prefix in ``## Dependencies`` for gating.
    """
    if phase.number == 0:
        deps_block = "None — no blocking phases."
    elif prev_num is not None:
        deps_block = f"- Blocked by #{prev_num}"
    else:
        raise ValueError(
            f"Phase {phase.number} has no prev_num but is not phase 0. "
            "Cannot emit parseable dependency line. "
            "Fix: ensure earlier phases were dispatched first."
        )

    tracking_block = (
        f"📦 Repo:   {target_repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.number}/{total_phases} — {phase.title} [{phase.tag}]\n"
        f"🔗 Issue:  (assigned on create)\n"
        f"\n"
        f"**Goal (from plan):** {goal}\n"
    )

    return (
        f"{tracking_block}"
        f"\n---\n\n"
        f"## Instruction\n\n"
        f"Use superpowers-for-vk:vk-execute to implement Phase {phase.number} of this plan.\n\n"
        f"## Workspace\n\n"
        f"Repos: {target_repo}\n\n"
        f"## Dependencies\n\n"
        f"{deps_block}\n"
    )
```

- [ ] **Step 4: Update all existing tests for new signature**

Existing `TestBuildIssueBody` tests (test_contains_instruction_section, test_contains_workspace_section, test_contains_dependencies_section, test_phase_zero_no_blocking, test_phase_one_no_prev_issue, test_phase_with_prev_issue, test_header_contains_phase_info, test_manual_type, test_plan_path_in_body, test_footer_contains_phase_title, test_instruction_references_phase_number) need `total_phases=3, spec="s.md", goal="G."` added.

Note: `test_phase_one_no_prev_issue` expects `"Phases 0-0 complete."` and `test_phase_with_prev_issue` expects `"Phases 0-2 complete. Blocked by #42."`. These now become incorrect — update to assert `"- Blocked by #42"` for the prev-num case and change `test_phase_one_no_prev_issue` to assert the builder raises ValueError (since phase 1 with `prev_num=None` is invalid per the new contract).

Note: `test_footer_contains_phase_title` asserts `"**Phase:** 2 — Integration"` — update to assert `"🎯 Phase:  2/3 — Integration"`.

Run `pytest tests/unit/test_dispatch_body.py 2>&1 | tail -10`. Expected: all pass.

- [ ] **Step 5: Update dispatch_cmd.dispatch() call site**

In `src/vk/commands/dispatch_cmd.py::dispatch`, at the loop `for phase in plan.phases:` (around line 248), the body call (line 255) becomes:

```python
        body = _build_issue_body(
            phase,
            plan_path_resolved,
            target_repo,
            prev_num,
            total_phases=len(plan.phases),
            spec=plan.spec or "",
            goal=plan.goal,
        )
```

Run `pytest tests/ 2>&1 | tail -15`. Expect test_dispatch.py integration tests need adjustment in the next step.

### Task 2: Title builder — human-readable format

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `tests/unit/test_dispatch_body.py`

- [ ] **Step 1: Add failing test for new title format**

Append to `tests/unit/test_dispatch_body.py`:

```python
from vk.commands.dispatch_cmd import _build_issue_title


class TestBuildIssueTitle:
    def test_title_format(self) -> None:
        phase = Phase(number=2, title="Content Migration", tag="agentic", tasks=(), tracking_url=None)
        title = _build_issue_title("blog-hextra", phase, target_repo="derio-net/frank", total=5)
        assert title == "[derio-net/frank] blog-hextra · Phase 2/5 · Content Migration"

    def test_manual_phase_title(self) -> None:
        phase = Phase(number=0, title="Operator Review", tag="manual", tasks=(), tracking_url=None)
        title = _build_issue_title("my-plan", phase, target_repo="org/repo", total=1)
        assert title == "[org/repo] my-plan · Phase 0/1 · Operator Review"
```

Run the test file; both new tests fail because `_build_issue_title` signature differs.

- [ ] **Step 2: Update _build_issue_title signature**

Replace lines 64–66 of `src/vk/commands/dispatch_cmd.py`:

```python
def _build_issue_title(slug: str, phase: Phase, target_repo: str, total: int) -> str:
    """Human-readable title: [{repo}] {slug} · Phase {n}/{total} · {phase_title}."""
    return f"[{target_repo}] {slug} · Phase {phase.number}/{total} · {phase.title}"
```

Update call sites in `dispatch_cmd.py`: `_print_dry_run` loop (around line 138) and the main apply loop (around line 252) need `target_repo=target_repo, total=len(phases_or_plan.phases)`.

Run `pytest tests/unit/test_dispatch_body.py 2>&1 | tail -10`. Expected: pass.

### Task 3: Structured labels on create

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `tests/integration/test_dispatch.py`

- [ ] **Step 1: Add failing integration test for structured labels**

Open `tests/integration/test_dispatch.py` and find the existing dispatch success test. Append a new test:

```python
def test_dispatch_adds_plan_and_phase_labels(tmp_path, monkeypatch, phased_plan_file, dispatch_config):
    """Each created Issue must carry plan:<slug> and phase:<n> labels."""
    captured_labels: list[list[str]] = []

    def fake_create_issue(repo, title, body, labels):
        captured_labels.append(list(labels))
        return "https://github.com/org/repo/issues/100"

    monkeypatch.setattr("vk.gh.create_issue", fake_create_issue)
    monkeypatch.setattr("vk.gh.extract_issue_number", lambda url: 100)

    from typer.testing import CliRunner
    from vk.cli import app
    runner = CliRunner()
    runner.invoke(app, ["dispatch", str(phased_plan_file), "--yes"])

    for labs in captured_labels:
        assert any(lab.startswith("plan:") for lab in labs), f"Missing plan: label in {labs}"
        assert any(lab.startswith("phase:") for lab in labs), f"Missing phase: label in {labs}"
```

Note: the fixture names (`phased_plan_file`, `dispatch_config`) must match existing fixtures in `tests/integration/conftest.py`. If names differ, use whatever is there.

Run `pytest tests/integration/test_dispatch.py::test_dispatch_adds_plan_and_phase_labels -x 2>&1 | tail -10`. Expected: fail (labels don't include plan:/phase: yet).

- [ ] **Step 2: Add structured labels in dispatch loop**

In `src/vk/commands/dispatch_cmd.py`, at the `gh.create_issue(...)` call (around line 258), replace the `labels=[...]` argument:

```python
            tag_label = (
                dispatch_cfg.labels.get("agentic", "vk-ready")
                if phase.tag == "agentic"
                else dispatch_cfg.labels.get("manual", "manual")
            )
            issue_url = gh.create_issue(
                repo=target_repo,
                title=title,
                body=body,
                labels=[tag_label, f"plan:{slug}", f"phase:{phase.number}"],
            )
```

Run the test; expect pass. Then run `pytest tests/ 2>&1 | tail -10`. Fix any fallout in other tests.

### Task 4: Body validator

**Files:**
- Create: `src/vk/commands/dispatch_body_validator.py`
- Create: `tests/unit/test_dispatch_body_validator.py`
- Modify: `src/vk/commands/dispatch_cmd.py`

- [ ] **Step 1: Write failing tests for validator**

Create `tests/unit/test_dispatch_body_validator.py`:

```python
"""Tests for validate_issue_body."""
from __future__ import annotations

import pytest

from vk.commands.dispatch_body_validator import BodyValidationError, validate_issue_body


class TestValidateIssueBody:
    def test_accepts_complete_phase_zero_body(self) -> None:
        body = (
            "📦 Repo:   org/repo\n\n---\n\n"
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: org/repo\n\n"
            "## Dependencies\n\nNone — no blocking phases.\n"
        )
        validate_issue_body(body, phase_number=0)  # no raise

    def test_accepts_complete_phase_n_body(self) -> None:
        body = (
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: org/repo\n\n"
            "## Dependencies\n\n- Blocked by #42\n"
        )
        validate_issue_body(body, phase_number=2)

    def test_rejects_missing_instruction(self) -> None:
        body = "## Workspace\n\nRepos: x\n\n## Dependencies\n\n- Blocked by #1\n"
        with pytest.raises(BodyValidationError, match="## Instruction"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_missing_workspace(self) -> None:
        body = "## Instruction\n\nUse ...\n\n## Dependencies\n\n- Blocked by #1\n"
        with pytest.raises(BodyValidationError, match="## Workspace"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_missing_dependencies(self) -> None:
        body = "## Instruction\n\nUse ...\n\n## Workspace\n\nRepos: x\n"
        with pytest.raises(BodyValidationError, match="## Dependencies"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_phase_n_without_dash_blocker(self) -> None:
        body = (
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: x\n\n"
            "## Dependencies\n\nBlocked by #42\n"  # missing dash prefix
        )
        with pytest.raises(BodyValidationError, match="- Blocked by"):
            validate_issue_body(body, phase_number=2)
```

Run: `pytest tests/unit/test_dispatch_body_validator.py 2>&1 | tail -10`. Expected: ImportError (module doesn't exist).

- [ ] **Step 2: Implement the validator**

Create `src/vk/commands/dispatch_body_validator.py`:

```python
"""Validator for Issue bodies produced by vk dispatch.

Fail-loud: any missing required section or wrong dependency format
raises BodyValidationError with an actionable message.
"""
from __future__ import annotations


class BodyValidationError(ValueError):
    """Raised when a generated Issue body fails the dispatch contract."""


_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")


def validate_issue_body(body: str, phase_number: int) -> None:
    """Raise BodyValidationError if body is not bridge-compatible.

    Checks:
    - All required sections present.
    - For phase_number > 0, the Dependencies section contains '- Blocked by #N'.
    """
    for section in _REQUIRED_SECTIONS:
        if section not in body:
            raise BodyValidationError(
                f"Generated body missing required section '{section}'. "
                f"The VK Issue Bridge will fail to parse this Issue. "
                f"Fix: investigate _build_issue_body in dispatch_cmd.py."
            )

    if phase_number > 0:
        deps_idx = body.index("## Dependencies")
        deps_block = body[deps_idx:]
        if "- Blocked by #" not in deps_block:
            raise BodyValidationError(
                f"Phase {phase_number} body's Dependencies section lacks "
                f"the required '- Blocked by #N' dash-prefixed line. "
                f"The bridge's dep-gating regex requires the dash. "
                f"Fix: investigate _build_issue_body in dispatch_cmd.py."
            )
```

Run the test file; expect pass.

- [ ] **Step 3: Wire validator into dispatch apply loop**

In `src/vk/commands/dispatch_cmd.py`, after building `body` and before calling `gh.create_issue`, add:

```python
            from vk.commands.dispatch_body_validator import validate_issue_body
            validate_issue_body(body, phase.number)
```

Move the import to the top-of-file imports. Run `pytest tests/ 2>&1 | tail -15`. Expect pass.

### Task 5: Remove quiet git-commit swallow

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `tests/integration/test_dispatch.py`

- [ ] **Step 1: Write failing test for git commit failure propagation**

In `tests/integration/test_dispatch.py`, add:

```python
def test_dispatch_git_commit_failure_surfaces(tmp_path, monkeypatch, phased_plan_file, dispatch_config):
    """A failing git commit must surface, not be silently swallowed."""
    import subprocess
    original_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "git" and "commit" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="pre-commit hook failed")
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("vk.gh.create_issue", lambda **kw: "https://github.com/org/repo/issues/1")
    monkeypatch.setattr("vk.gh.extract_issue_number", lambda url: 1)
    monkeypatch.setattr("subprocess.run", fake_run)

    from typer.testing import CliRunner
    from vk.cli import app
    result = CliRunner().invoke(app, ["dispatch", str(phased_plan_file), "--yes"])
    assert result.exit_code != 0
    assert "pre-commit hook failed" in (result.output + str(result.exception))
```

Run; expect fail (today: `except Exception: pass` swallows the error and exit is 0).

- [ ] **Step 2: Remove the silent except**

In `src/vk/commands/dispatch_cmd.py` lines 282–296, replace the try/except wrapping the git commit with direct subprocess calls:

```python
    subprocess.run(
        ["git", "add", str(plan_path_resolved)],
        check=True, capture_output=True, text=True, cwd=repo_root,
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: link plan phases to GitHub Issues (vk dispatch)"],
        check=True, capture_output=True, text=True, cwd=repo_root,
    )
```

Run the test; expect pass. Run full suite `pytest tests/ 2>&1 | tail -15`; fix any fallout.

### Task 6: Inject issue URL into tracking block after create

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`

- [ ] **Step 1: Write failing test that Issue body is updated with its own URL**

In `tests/integration/test_dispatch.py`, add:

```python
def test_dispatch_updates_body_with_issue_url(tmp_path, monkeypatch, phased_plan_file, dispatch_config):
    """After Issue creation, the body's '🔗 Issue:' line gets the real URL."""
    edits: list[tuple[str, str]] = []

    def fake_create(repo, title, body, labels):
        assert "(assigned on create)" in body
        return "https://github.com/org/repo/issues/77"

    def fake_edit(repo, number, body):
        edits.append((repo, body))

    monkeypatch.setattr("vk.gh.create_issue", fake_create)
    monkeypatch.setattr("vk.gh.extract_issue_number", lambda url: 77)
    monkeypatch.setattr("vk.gh.edit_issue_body", fake_edit)

    from typer.testing import CliRunner
    from vk.cli import app
    CliRunner().invoke(app, ["dispatch", str(phased_plan_file), "--yes"])
    assert edits, "expected at least one edit_issue_body call"
    for _, body in edits:
        assert "🔗 Issue:  https://github.com/org/repo/issues/77" in body
```

Expected: fail — `gh.edit_issue_body` may not exist; dispatch doesn't re-edit the body.

- [ ] **Step 2: Add gh.edit_issue_body helper**

In `src/vk/gh.py`, add:

```python
def edit_issue_body(repo: str, number: int, body: str) -> None:
    """Update the body of an existing Issue via `gh issue edit`."""
    _run_gh(["issue", "edit", str(number), "--repo", repo, "--body", body])
```

Use whatever `_run_gh`/equivalent helper already exists in that module. Add a minimal unit test in `tests/unit/test_gh.py` mirroring existing patterns.

- [ ] **Step 3: Call edit_issue_body after create in dispatch loop**

After `issue_num = gh.extract_issue_number(issue_url)` in the apply loop:

```python
            updated_body = body.replace("(assigned on create)", issue_url)
            gh.edit_issue_body(target_repo, issue_num, updated_body)
```

Run `pytest tests/ 2>&1 | tail -10`; expect pass.

---

## Phase 2: Archive-on-Complete in vk progress sync [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/11 -->

### Task 1: Add plan.archive_to config key

**Files:**
- Modify: `src/vk/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: Failing test for archive_to default and override**

In `tests/unit/test_config.py`, add:

```python
def test_plan_archive_to_default(tmp_path):
    from vk.config import load_profile
    p = tmp_path / "plan-config.yaml"
    p.write_text("plan:\n  save_to: docs/plans/\n")
    profile = load_profile(p)
    assert profile.plan.archive_to == "docs/superpowers/archived-plans/"


def test_plan_archive_to_override(tmp_path):
    from vk.config import load_profile
    p = tmp_path / "plan-config.yaml"
    p.write_text("plan:\n  archive_to: custom/archive/\n")
    profile = load_profile(p)
    assert profile.plan.archive_to == "custom/archive/"
```

Run; expect AttributeError.

- [ ] **Step 2: Add archive_to to PlanConfig**

In `src/vk/config.py`, update `PlanConfig`:

```python
@dataclass(frozen=True)
class PlanConfig:
    filename: str = "YYYY-MM-DD-{name}.md"
    save_to: str = "docs/superpowers/plans/"
    archive_to: str = "docs/superpowers/archived-plans/"
```

And in `_parse_plan`:

```python
    return PlanConfig(
        filename=str(raw.get("filename", PlanConfig.filename)),
        save_to=str(raw.get("save_to", PlanConfig.save_to)),
        archive_to=str(raw.get("archive_to", PlanConfig.archive_to)),
    )
```

Run tests; expect pass.

### Task 2: Archive flow in sync

**Files:**
- Modify: `src/vk/commands/progress_cmd.py`
- Modify: `tests/integration/test_progress.py`

- [ ] **Step 1: Failing test — sync-to-Complete offers archive prompt**

In `tests/integration/test_progress.py`, add:

```python
def test_sync_to_complete_prompts_archive(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from vk.cli import app
    # Set up a repo with a plan whose checkboxes are all checked
    repo = tmp_path / "repo"
    (repo / "docs/superpowers/plans").mkdir(parents=True)
    (repo / "docs/superpowers/archived-plans").mkdir(parents=True)
    (repo / "docs/superpowers").joinpath("plan-config.yaml").write_text(
        "plan:\n  save_to: docs/superpowers/plans/\n"
    )
    plan = repo / "docs/superpowers/plans/p.md"
    plan.write_text(
        "# P\n**Spec:** `s.md`\n**Status:** In Progress\n\n"
        "## Phase 0: X [agentic]\n### Task 1: T\n- [x] **Step 1: done**\n"
    )
    import subprocess
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["progress", "sync", str(plan), "--yes"])
    assert result.exit_code == 0
    assert not plan.exists(), "plan should be moved out of plans/"
    assert (repo / "docs/superpowers/archived-plans/p.md").exists()
```

Run; expect fail (sync today does not archive).

- [ ] **Step 2: Failing test — dry-run shows "Would archive"**

```python
def test_sync_dry_run_previews_archive(tmp_path):
    # ... same setup as above up to `monkeypatch.chdir(repo)` ...
    result = CliRunner().invoke(app, ["progress", "sync", str(plan), "--dry-run"])
    assert "Would archive" in result.output
    assert plan.exists(), "dry-run must not move the file"
```

Run; expect fail.

- [ ] **Step 3: Failing test — destination collision refused**

```python
def test_sync_archive_refuses_overwrite(tmp_path):
    # ... setup ... then also create archived-plans/p.md beforehand
    (repo / "docs/superpowers/archived-plans/p.md").write_text("existing")
    result = CliRunner().invoke(app, ["progress", "sync", str(plan), "--yes"])
    assert result.exit_code != 0
    assert "already exists" in (result.output + str(result.exception))
    assert plan.exists(), "plan must remain in place on refusal"
```

Run; expect fail.

- [ ] **Step 4: Implement _archive_plan helper in progress_cmd.py**

Add to `src/vk/commands/progress_cmd.py`:

```python
import shutil


def _archive_plan(plan_path: Path, profile: Profile, repo_root: Path,
                  action: ConfirmAction) -> Path | None:
    """Move a Complete plan to the archive directory. Returns new path or None.

    Interactive: prompt first (default No).
    --yes:       auto-archive.
    --dry-run:   print preview, no move.
    """
    dest_dir = repo_root / profile.plan.archive_to
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / plan_path.name

    if dest.exists():
        err_console.print(
            f"Archive destination already exists: {dest}. Refusing to overwrite."
        )
        raise typer.Exit(2)

    if action is ConfirmAction.DRY_RUN:
        console.print(f"Would archive: {plan_path} -> {dest}")
        return None
    if action is ConfirmAction.PROMPT:
        if not typer.confirm(
            f"Plan is Complete. Archive to {profile.plan.archive_to}?",
            default=False,
        ):
            return None

    # git mv (preserves history), fall back to shutil.move
    try:
        subprocess.run(
            ["git", "mv", str(plan_path), str(dest)],
            check=True, capture_output=True, text=True, cwd=repo_root,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.move(str(plan_path), str(dest))
        subprocess.run(
            ["git", "add", str(dest)], check=False, capture_output=True, cwd=repo_root
        )

    subprocess.run(
        ["git", "commit", "-m", f"chore(plan): archive {plan_path.stem} on completion"],
        check=True, capture_output=True, text=True, cwd=repo_root,
    )
    console.print(f"Archived: {plan_path.name} -> {profile.plan.archive_to}")
    return dest
```

- [ ] **Step 5: Wire into sync() after Status write**

At the end of the `sync` function in `progress_cmd.py`, after `_reconcile_spec_index(...)` when `new_status == "Complete"`:

```python
    archived_path: Path | None = None
    if new_status == "Complete":
        save_to = Path(profile.plan.save_to)
        try:
            plan_path.relative_to(repo_root / save_to)
        except ValueError:
            pass  # not under save_to, skip archiving
        else:
            archived_path = _archive_plan(plan_path, profile, repo_root, action)
            if archived_path:
                # Re-reconcile with new path
                _reconcile_spec_index(
                    archived_path, plan.title, new_status, repo_root
                )
```

Run the three new tests; expect pass. Then full suite `pytest tests/ 2>&1 | tail -15`.

### Task 3: Update spec index file path on archive

**Files:**
- Modify: `src/vk/commands/progress_cmd.py`
- Modify: `tests/integration/test_progress.py`

- [ ] **Step 1: Failing test — spec index file: column reflects archive path**

```python
def test_archive_updates_spec_index_file_column(tmp_path):
    # ... setup repo with spec and plan linked; complete and archive ...
    # After sync --yes, read the spec file and assert the index row's
    # file: column points to docs/superpowers/archived-plans/p.md
    spec_text = (repo / "docs/superpowers/specs/s.md").read_text()
    assert "docs/superpowers/archived-plans/p.md" in spec_text
```

Wire the full fixture (create `docs/superpowers/specs/s.md` with an `## Implementation Plans` table). Refer to `src/vk/spec_index.py` and existing fixtures.

Run; expect fail (spec index still shows `docs/superpowers/plans/p.md`).

- [ ] **Step 2: Implementation already handled**

The re-reconcile in Task 2 Step 5 already passes `archived_path` to `_reconcile_spec_index`. But verify `_reconcile_spec_index` writes the correct `file:` via `IndexEntry.file`. If not, update it to use `archived_path.relative_to(repo_root)` when archived.

Run the new test; expect pass.

---

## Phase 3: vk dispatch migrate [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/12 -->

### Task 1: Scaffold subcommand

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `src/vk/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Failing test — subcommand registered**

In `tests/unit/test_cli.py`:

```python
def test_dispatch_migrate_command_exists():
    from typer.testing import CliRunner
    from vk.cli import app
    result = CliRunner().invoke(app, ["dispatch", "migrate", "--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output.lower()
```

Run; expect fail.

- [ ] **Step 2: Convert dispatch to a subcommand group**

In `src/vk/commands/dispatch_cmd.py`, wrap the existing `dispatch` function as the default command of a typer sub-app:

```python
dispatch_app = typer.Typer(invoke_without_command=True, help="Dispatch plans to GitHub Issues.")

@dispatch_app.callback(invoke_without_command=True)
def dispatch_default(ctx: typer.Context, ...):  # existing params
    if ctx.invoked_subcommand is None:
        # existing dispatch body
        ...

@dispatch_app.command("migrate")
def migrate(
    plan_path: Path = typer.Argument(..., exists=True),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Retrofit existing open Issues to the new title/body format."""
    console.print("migrate stub")  # filled in next task
```

Update `src/vk/cli.py` to register `dispatch_app` as `app.add_typer(dispatch_app, name="dispatch")` instead of the bare command.

Run the new test; expect pass. Run existing dispatch tests; fix any routing issues.

### Task 2: Migrate logic

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Create: `tests/integration/test_dispatch_migrate.py`

- [ ] **Step 1: Failing test — missing tracking comment aborts**

Create `tests/integration/test_dispatch_migrate.py`:

```python
from pathlib import Path
from typer.testing import CliRunner
from vk.cli import app


def _write_plan(path: Path, phases_with_tracking: list[tuple[int, str, str | None]]) -> None:
    body = (
        "# P\n"
        "**Spec:** `docs/superpowers/specs/s.md`\n"
        "**Status:** In Progress\n\n"
        "**Goal:** G.\n\n---\n\n"
    )
    for n, title, url in phases_with_tracking:
        body += f"## Phase {n}: {title} [agentic]\n"
        if url:
            body += f"<!-- Tracking: {url} -->\n"
        body += "\n### Task 1: T\n- [ ] **Step 1: s**\n\n"
    path.write_text(body)


def test_migrate_aborts_on_missing_tracking(tmp_path, monkeypatch):
    plan = tmp_path / "plan.md"
    _write_plan(plan, [(0, "A", "https://github.com/org/r/issues/1"), (1, "B", None)])
    # Also create plan-config.yaml with dispatch enabled
    (tmp_path / "plan-config.yaml").write_text(
        "dispatch:\n  owner: org\n  default_repo: org/r\n"
        "  project_board: Derio Ops\n  labels:\n    agentic: vk-ready\n    manual: manual\n"
    )
    monkeypatch.chdir(tmp_path)
    # Point config lookup at this dir
    monkeypatch.setenv("VK_CONFIG_PATH", str(tmp_path / "plan-config.yaml"))
    result = CliRunner().invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
    assert result.exit_code != 0
    assert "Phase 1" in result.output and "no tracking comment" in result.output.lower()
```

Note: if the config-lookup path in the codebase doesn't support env override, either add it or symlink to the repo-root-walked location. Adapt as needed.

Run; expect fail.

- [ ] **Step 2: Implement migrate — tracking-comment collection and validation**

In `dispatch_cmd.py::migrate`, after parsing the plan:

```python
    tracked = _get_already_tracked(plan_path.read_text())
    missing = [p.number for p in plan.phases if p.number not in tracked]
    if missing:
        err_console.print(
            f"Phase(s) {missing} have no tracking comment in {plan_path}. "
            f"Run 'vk dispatch <plan>' to create Issues for pending phases first."
        )
        raise typer.Exit(2)
```

Run the test; expect pass.

- [ ] **Step 3: Failing test — dry-run prints diff**

```python
def test_migrate_dry_run_prints_diff(tmp_path, monkeypatch):
    plan = tmp_path / "plan.md"
    _write_plan(plan, [(0, "A", "https://github.com/org/r/issues/1")])
    (tmp_path / "plan-config.yaml").write_text("dispatch:\n  owner: org\n  default_repo: org/r\n  project_board: X\n  labels:\n    agentic: vk-ready\n    manual: manual\n")

    def fake_view(repo, number):
        return {"state": "OPEN", "title": "old title",
                "body": "OLD BODY", "labels": [{"name": "vk-ready"}]}
    monkeypatch.setattr("vk.gh.view_issue", fake_view, raising=False)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["dispatch", "migrate", str(plan), "--dry-run"])
    assert result.exit_code == 0
    assert "[org/r]" in result.output  # new title format appears
    assert "old title" in result.output  # old title shown in diff
```

Run; expect fail.

- [ ] **Step 4: Implement dry-run flow**

Add `view_issue` to `src/vk/gh.py`:

```python
def view_issue(repo: str, number: int) -> dict:
    """Fetch an Issue's title, body, labels, state via gh issue view --json."""
    out = _run_gh(["issue", "view", str(number), "--repo", repo,
                   "--json", "title,body,labels,state"])
    return json.loads(out)
```

In `migrate()`:

```python
    from vk.commands.dispatch_body_validator import validate_issue_body
    rewrites: list[dict] = []
    for phase in plan.phases:
        url = tracked[phase.number]
        number = gh.extract_issue_number(url)
        issue_repo = url.split("/issues/")[0].replace("https://github.com/", "")
        info = gh.view_issue(issue_repo, number)
        if info.get("state") == "CLOSED":
            console.print(f"Skip #{number}: CLOSED")
            continue
        new_title = _build_issue_title(slug, phase, target_repo=issue_repo, total=len(plan.phases))
        prev_num = gh.extract_issue_number(tracked[phase.number - 1]) if phase.number > 0 else None
        new_body = _build_issue_body(
            phase, plan_path, issue_repo, prev_num,
            total_phases=len(plan.phases),
            spec=plan.spec or "",
            goal=plan.goal,
        )
        new_body = new_body.replace("(assigned on create)", url)
        validate_issue_body(new_body, phase.number)
        rewrites.append({"repo": issue_repo, "number": number,
                         "old_title": info["title"], "new_title": new_title,
                         "new_body": new_body})

    if action is ConfirmAction.DRY_RUN:
        for r in rewrites:
            console.print(f"\n#{r['number']}  {r['old_title']}  →  {r['new_title']}")
        raise typer.Exit(0)
```

Run the test; expect pass.

- [ ] **Step 5: Failing test — --yes applies edits and aborts on gh failure**

```python
def test_migrate_yes_applies_edits(tmp_path, monkeypatch):
    # ... same setup ...
    applied: list[dict] = []
    monkeypatch.setattr("vk.gh.view_issue", lambda repo, n: {
        "state": "OPEN", "title": "old", "body": "b", "labels": []})
    def fake_edit(repo, number, title, body, add_labels):
        applied.append({"n": number, "title": title})
    monkeypatch.setattr("vk.gh.edit_issue", fake_edit, raising=False)
    # ...
    result = CliRunner().invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
    assert result.exit_code == 0
    assert applied[0]["title"].startswith("[org/r]")


def test_migrate_aborts_mid_run_on_gh_error(tmp_path, monkeypatch):
    # two phases; second fails
    def fake_edit(repo, number, title, body, add_labels):
        if number == 2: raise Exception("gh boom")
    # ... assert exit != 0 and only first edit applied
```

Run; expect fail.

- [ ] **Step 6: Implement --yes apply path**

Add `gh.edit_issue` (title + body + labels in one call):

```python
def edit_issue(repo: str, number: int, title: str, body: str,
               add_labels: list[str]) -> None:
    args = ["issue", "edit", str(number), "--repo", repo,
            "--title", title, "--body", body]
    for lbl in add_labels:
        args.extend(["--add-label", lbl])
    _run_gh(args)
```

In `migrate()` after the dry-run branch:

```python
    for r in rewrites:
        gh.edit_issue(
            r["repo"], r["number"], r["new_title"], r["new_body"],
            add_labels=[f"plan:{slug}", f"phase:{phase.number}"],
        )
        console.print(f"Migrated #{r['number']}")
```

Run tests; expect pass. Run full suite `pytest tests/ 2>&1 | tail -15`.

---

## Phase 4: Skill and documentation updates [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/13 -->

### Task 1: Update vk-execute skill

**Files:**
- Modify: `skills/vk-execute/SKILL.md`
- Modify: `tests/unit/test_skill_validation.py`

- [ ] **Step 1: Failing test — skill mentions pr-ready label and unified PR title**

In `tests/unit/test_skill_validation.py`, add:

```python
def test_vk_execute_mentions_pr_ready_label(self, skill_dir: Path) -> None:
    if skill_dir.name != "vk-execute":
        return
    text = (skill_dir / "SKILL.md").read_text()
    assert "pr-ready" in text, "vk-execute must document the pr-ready label swap"

def test_vk_execute_mentions_unified_pr_title(self, skill_dir: Path) -> None:
    if skill_dir.name != "vk-execute":
        return
    text = (skill_dir / "SKILL.md").read_text()
    assert "[{owner}/{repo}]" in text or "[owner/repo]" in text, \
        "vk-execute must document the unified PR title format"
```

Run; expect fail.

- [ ] **Step 2: Update the skill**

Open `skills/vk-execute/SKILL.md`. Read current contents. Add a new section before the existing lifecycle steps:

```markdown
## PR format (unified)

When creating the PR for an agentic phase:

- **Title:** `[{owner}/{repo}] Phase {n}/{total} · {phase_title}` — matches the Issue title shape so VK/GH/PR surfaces align.
- **Body:** first content block is the tracking block copied verbatim from the Issue body (the `📦 Repo:` / `📋 Plan:` / ... lines plus the `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

## Label lifecycle

After `gh pr create` succeeds:

    gh issue edit <issue_number> --repo <owner/repo> \
       --add-label pr-ready --remove-label in-progress

Best-effort: failure does not block PR creation.
```

Run the new tests; expect pass.

### Task 2: Update vk-dispatch skill

**Files:**
- Modify: `skills/vk-dispatch/SKILL.md`

- [ ] **Step 1: Document migrate and unified title**

Edit `skills/vk-dispatch/SKILL.md`. Add under "Integration":

```markdown
## Retroactive migration

For plans dispatched before the unified-title format, run:

    vk dispatch migrate <plan-path> --dry-run
    vk dispatch migrate <plan-path> --yes

Rewrites open Issues' titles + bodies to the current format. Closed Issues are skipped.
```

Update the "Procedure" section if it still references the old `slug-phase-tag` title shape. The new shape is `[owner/repo] slug · Phase n/total · phase_title`.

No automated test for this prose; a quick re-read is enough.

### Task 3: Update vk-progress skill

**Files:**
- Modify: `skills/vk-progress/SKILL.md`

- [ ] **Step 1: Document archive-on-Complete**

Append to `skills/vk-progress/SKILL.md`:

```markdown
## Archive-on-Complete

When `sync` flips Status to `Complete`, it interactively offers to move the plan
file to `docs/superpowers/archived-plans/`:

- Interactive: prompts `"Plan is Complete. Archive ... [y/N]"`
- `--yes`: archives without prompt.
- `--dry-run`: prints `"Would archive: <src> -> <dest>"`.

The destination is set by `profile.plan.archive_to` in `plan-config.yaml`
(default `docs/superpowers/archived-plans/`). The spec index row is updated
to point at the new archived path.
```

---

## Phase 5: Operational migration [manual]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/14 -->

### Task 1: Verify bridge changes deployed

- [ ] **Step 1: Confirm secure-agent-kali plan is Complete**

```bash
grep '^**Status:**' /home/claude/repos/secure-agent-kali/docs/superpowers/plans/2026-04-14-bridge-fail-loud-and-blocker-preamble.md
```

Expected: `**Status:** Complete` (or the plan has been archived — check `archived-plans/`).

- [ ] **Step 2: Confirm bridge script on production host matches source**

```bash
diff /opt/scripts/vk-issue-bridge.py /home/claude/repos/secure-agent-kali/scripts/vk-issue-bridge.py
```

Expected: no output (files identical). If output shows changes, deployment is incomplete — abort operational migration until resolved.

### Task 2: Migrate Frank hextra plan

- [ ] **Step 1: Dry-run migrate**

```bash
cd /home/claude/repos/frank
vk dispatch migrate docs/superpowers/plans/2026-04-13--repo--blog-hextra-migration.md --dry-run
```

Expected: 5 rewrites printed (phases 1–5), each showing old title → new `[derio-net/frank] blog-hextra-migration · Phase N/5 · ...` title. If any Issue is CLOSED, the line reads `Skip #N: CLOSED`.

- [ ] **Step 2: Apply migrate**

```bash
vk dispatch migrate docs/superpowers/plans/2026-04-13--repo--blog-hextra-migration.md --yes
```

Expected: 5 `Migrated #N` lines (or fewer, for CLOSED phases).

- [ ] **Step 3: Confirm bridge ingests phase 1, defers others**

Wait for the next bridge cron tick (≤ 2 minutes), then:

```bash
ssh secure-agent-pod 'tail -80 /var/log/supercronic/vk-issue-bridge.log'
```

Expected log contents: `p derio-net/frank#69: blocked by #68` (and similar for #70, #71, #72). Phase 1 (#68) should either be already-synced (has `vk-synced` label) or sync now if it wasn't before. No workspace created for phases 2–5 until phase 1 closes.

### Task 3: Migrate remaining open plans

- [ ] **Step 1: Enumerate open plans across repos**

```bash
for repo in /home/claude/repos/superpowers-for-vk /home/claude/repos/secure-agent-kali /home/claude/repos/frank /home/claude/repos/willikins; do
  for plan in "$repo"/docs/superpowers/plans/*.md; do
    status=$(grep -m1 '^**Status:**' "$plan" | sed 's/**Status:**\s*//')
    [ "$status" = "Complete" ] || echo "$plan ($status)"
  done
done
```

Review the output. Any plan that was dispatched before this work shipped is a migration candidate.

- [ ] **Step 2: Migrate each candidate**

For each plan from Step 1 with tracking comments:

```bash
vk dispatch migrate <plan> --dry-run
vk dispatch migrate <plan> --yes
```

Spot-check one migrated Issue in the GitHub UI — confirm the new title format and tracking block render as expected.

### Task 4: Verify bridge behavior end-to-end

- [ ] **Step 1: Confirm dep-gating active across all repos**

```bash
ssh secure-agent-pod 'tail -200 /var/log/supercronic/vk-issue-bridge.log' | grep -E '(blocked|deferred|synced)' | tail -30
```

Expected: `p ... blocked by ...` lines for every migrated multi-phase plan's non-phase-0 Issues whose blockers remain open. Absence of such lines when blockers exist is a regression — abort and open a bug.

- [ ] **Step 2: Mark this plan Complete**

Edit this file's `**Status:**` header to `Complete`, then:

```bash
vk progress sync docs/superpowers/plans/2026-04-14-archive-and-unified-descriptions.md --yes
```

The archive flow from Phase 2 moves the plan to `archived-plans/` and commits.
