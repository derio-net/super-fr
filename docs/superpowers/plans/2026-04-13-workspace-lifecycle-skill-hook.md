# Workspace Lifecycle Skill Hook Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-13-workspace-lifecycle-automation-design.md`
**Status:** In Progress

**Goal:** Modify the `vk-execute` skill to call VK MCP `update_issue(status: "In Review")` after the agent creates a PR, closing the lifecycle gap between agent completion and operator review.
**Architecture:** Two files change: the thin CLI wrapper (`skills/vk-execute/SKILL.md`) gets a new Step 7 after PR creation, and the cached plugin skill (`skills/vk-execute/SKILL.md` in the plugin cache) gets the corresponding detailed procedure. The change is purely additive — a new final step that is best-effort and dispatch-mode only.
**Tech Stack:** Markdown (skill prose), pytest (validation)

---

## Phase 0: Add lifecycle transition step to vk-execute skill [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/7 -->

### Task 1: Update the thin CLI wrapper skill

**Files:**
- Modify: `skills/vk-execute/SKILL.md`

- [x] **Step 1: Write a failing validation test for the new step**

Add a test to `tests/unit/test_skill_validation.py` that verifies the `vk-execute` skill mentions the "In Review" transition:

```python
def test_vk_execute_has_lifecycle_transition(self, skill_dir: Path) -> None:
    """vk-execute must include the post-PR lifecycle transition step."""
    if skill_dir.name != "vk-execute":
        pytest.skip("Only applies to vk-execute")
    text = (skill_dir / "SKILL.md").read_text()
    assert "In Review" in text, "vk-execute must reference 'In Review' lifecycle transition"
```

Run: `cd /home/claude/repos/superpowers-for-vk && uv run pytest tests/unit/test_skill_validation.py::TestSkillValidation::test_vk_execute_has_lifecycle_transition -v`
Expected: FAIL — "In Review" not found in current skill file.

- [x] **Step 2: Add Step 7 to the thin CLI wrapper**

Edit `skills/vk-execute/SKILL.md`. After the existing step 6 ("Delegate to `superpowers:finishing-a-development-branch`."), add a new step 7:

```markdown
7. Transition VK Issue to "In Review" (dispatch mode only):
   - Extract the GitHub Issue number from the plan's tracking comment (`<!-- Tracking: ...issues/<N> -->`)
   - Call VK MCP `list_issues` with `search: "gh#<N>"` to resolve the VK Issue ID
   - Call VK MCP `update_issue(issue_id: "<id>", status: "In Review")`
   - If MCP is unavailable or calls fail, skip silently — the server fallback will handle it
```

Verify the file stays under 120 lines (current: 48 lines, adding ~5 lines is well within budget).

- [x] **Step 3: Run validation tests**

Run: `cd /home/claude/repos/superpowers-for-vk && uv run pytest tests/unit/test_skill_validation.py -v`
Expected: ALL PASS, including the new `test_vk_execute_has_lifecycle_transition`.

- [x] **Step 4: Commit**

```bash
git add skills/vk-execute/SKILL.md tests/unit/test_skill_validation.py
git commit -m "feat: add post-PR lifecycle transition to vk-execute skill"
```

### Task 2: Verify and run full CI checks

The thin wrapper in `skills/vk-execute/SKILL.md` is the source of truth. The cached plugin version at `~/.claude/plugins/cache/.../skills/vk-execute/SKILL.md` is a copy from a previous install — it will be updated when the plugin is reinstalled in Task 3. No separate edit needed.

**Files:** (none — verification only)

- [x] **Step 1: Run full test suite**

Run: `cd /home/claude/repos/superpowers-for-vk && uv run pytest -v`
Expected: ALL PASS.

- [x] **Step 2: Run linting and type checks**

Run: `cd /home/claude/repos/superpowers-for-vk && uv run ruff check . && uv run mypy src/`
Expected: Clean.

### Task 3: Update plugin version and reinstall

**Files:**
- Modify: `pyproject.toml` (version bump)

- [x] **Step 1: Bump plugin patch version**

Edit `pyproject.toml` to bump the version (e.g., `0.2.2` → `0.2.3` or whatever the current version is). Check current version first:

```bash
grep 'version' pyproject.toml | head -1
```

- [x] **Step 2: Reinstall skills to update plugin cache**

```bash
cd /home/claude/repos/superpowers-for-vk && uv run vk install-skills
```

Verify the cached skill file now contains "In Review".

- [x] **Step 3: Commit version bump**

```bash
git add pyproject.toml
git commit -m "chore: bump version for lifecycle transition feature"
```
