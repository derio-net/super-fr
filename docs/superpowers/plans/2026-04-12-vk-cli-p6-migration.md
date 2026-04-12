# VK CLI Migration + Validation Sweep Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Verify every workspace repo has a valid `plan-config.yaml` under the new fail-closed gate, existing plans still parse, and the `vk` CLI is installed and working.
**Architecture:** Operator runbook backed by parameterized shell scripts in `scripts/migration/`. All scripts take the workspace directory as a required positional argument — no hardcoded paths.
**Tech Stack:** vk CLI, gh CLI, git, bash

**Scripts:**
- `scripts/migration/audit-repos.sh <workspace-dir>` — categorize repos by config state
- `scripts/migration/init-unconfigured.sh <workspace-dir>` — run `vk init` + commit for unconfigured repos
- `scripts/migration/find-phased-local.sh <workspace-dir>` — find phased plans in local-only repos
- `scripts/migration/smoke-test.sh <workspace-dir> <dispatch-repo> <local-repo>` — CLI + gate smoke test

---

## Phase 1: Migration and validation sweep [manual]

### Task 1: Audit existing repos

- [ ] **Step 1: Run the audit script**

```bash
./scripts/migration/audit-repos.sh /path/to/workspace
```

Expected: A list of repos categorized into three groups:
- Has dispatch block (dispatch-enabled)
- No dispatch block (local-only, explicitly configured)
- No plan-config.yaml (unconfigured)

- [ ] **Step 2: Record the audit results**

Create a checklist of repos and their current state. Note which repos need:
- `vk init` (unconfigured)
- `vk init --dispatch` (should be dispatch-enabled but missing config)
- No change (already correctly configured)

### Task 2: Configure unconfigured repos

- [ ] **Step 1: Run the init script**

```bash
./scripts/migration/init-unconfigured.sh /path/to/workspace
```

Expected: For each repo without a `plan-config.yaml`, creates a local-only config, `docs/superpowers/{specs,plans,archived-plans}/` directories, and commits.

- [ ] **Step 2: Verify the created configs**

Spot-check a few repos:

```bash
cat /path/to/workspace/<repo>/docs/superpowers/plan-config.yaml
```

Should have `plan:` and `header:` sections, no `dispatch:` block.

### Task 3: Verify dispatch-enabled repos

- [ ] **Step 1: Check dispatch config fields**

For each repo that HAS a `dispatch:` block (identified in Task 1):

```bash
cd /path/to/workspace/<repo>
vk dispatch --dry-run docs/superpowers/plans/<any-existing-plan>.md
```

Expected: Either a valid dry-run preview (fields all present) or a clear error about missing fields.

If fields are missing, add them to `plan-config.yaml`:
- `dispatch.owner` — the GitHub owner/org
- `dispatch.project_board` — project board name
- `dispatch.default_repo` — `owner/repo` slug
- `dispatch.labels.agentic` — label for agentic phases (default: `vk-ready`)
- `dispatch.labels.manual` — label for manual phases (default: `manual`)

### Task 4: Test plan conversion for local-only repos

- [ ] **Step 1: Find phased plans in local-only repos**

```bash
./scripts/migration/find-phased-local.sh /path/to/workspace
```

- [ ] **Step 2: Dry-run conversion for each identified plan**

For each plan listed by the script:

```bash
vk plan convert <plan-path> --to flat --dry-run
```

Review the dry-run output. For each plan, decide:
- **Convert:** Plan is no longer dispatched and should be flat. Run with `--yes`.
- **Leave:** Plan has historical value in phased format. Skip.
- **Force-convert:** Plan has tracking comments from a past dispatch. Run with `--force --yes`.

### Task 5: Replace old SKILL.md files

- [ ] **Step 1: Remove old skill files and marketplace duplicates**

```bash
rm -rf ~/.claude/skills/vk-plan
rm -rf ~/.claude/skills/vk-dispatch
rm -rf ~/.claude/skills/vk-progress
rm -rf ~/.claude/skills/vk-execute
rm -rf ~/.claude/plugins/marketplaces/derio-net/skills/vk-plan
rm -rf ~/.claude/plugins/marketplaces/derio-net/skills/vk-dispatch
rm -rf ~/.claude/plugins/marketplaces/derio-net/skills/vk-progress
rm -rf ~/.claude/plugins/marketplaces/derio-net/skills/vk-execute
```

- [ ] **Step 2: Install new skills via CLI**

```bash
vk install-skills
```

This also removes any remaining marketplace duplicates automatically.

Expected: Symlinks created:
- `~/.claude/skills/vk-plan -> <repo>/skills/vk-plan`
- `~/.claude/skills/vk-dispatch -> <repo>/skills/vk-dispatch`
- `~/.claude/skills/vk-progress -> <repo>/skills/vk-progress`
- `~/.claude/skills/vk-execute -> <repo>/skills/vk-execute`

Verify:

```bash
ls -la ~/.claude/skills/vk-*
head -5 ~/.claude/skills/vk-dispatch/SKILL.md
```

Expected: First line is `---` (YAML frontmatter), file is under 80 lines. No vk-* entries in `~/.claude/plugins/marketplaces/derio-net/skills/`.

### Task 6: Smoke test

- [ ] **Step 1: Run the smoke test script**

```bash
./scripts/migration/smoke-test.sh /path/to/workspace superpowers-for-vk kid-laptops
```

Expected: All CLI help commands pass, dispatch dry-run works in dispatch-enabled repo, progress board works in local repo, dispatch gate refuses in local repo.

### Task 7: Verify CI and re-enable dispatch

- [ ] **Step 1: Push and verify CI in superpowers-for-vk**

```bash
cd /path/to/workspace/superpowers-for-vk
git push origin main
```

Wait for GitHub Actions to complete.

Expected: All three jobs (lint, typecheck, test) pass. Verify at:
`https://github.com/derio-net/superpowers-for-vk/actions`

- [ ] **Step 2: Re-enable dispatch for superpowers-for-vk**

Edit `docs/superpowers/plan-config.yaml` to restore the `dispatch:` block:

```yaml
dispatch:
  target: github-issues
  owner: derio-net
  project_board: "Derio Ops"
  default_repo: derio-net/superpowers-for-vk
  labels:
    agentic: vk-ready
    manual: manual
```

```bash
git add docs/superpowers/plan-config.yaml
git commit -m "chore: re-enable dispatch for superpowers-for-vk"
git push
```
