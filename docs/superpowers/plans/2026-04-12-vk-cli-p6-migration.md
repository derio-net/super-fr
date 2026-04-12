# VK CLI Migration + Validation Sweep Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Verify every HOMELAB repo has a valid `plan-config.yaml` under the new fail-closed gate, existing plans still parse, and the `vk` CLI is installed and working.
**Architecture:** Operator runbook — no code, all manual verification and configuration steps.
**Tech Stack:** vk CLI, gh CLI, git, shell

---

## Phase 1: Migration and validation sweep [manual]

### Task 1: Audit existing repos

- [ ] **Step 1: List all repos with superpowers config**

Run:

```bash
for dir in ~/Docs/projects/HOMELAB/*/; do
  repo=$(basename "$dir")
  config="$dir/docs/superpowers/plan-config.yaml"
  if [ -f "$config" ]; then
    has_dispatch=$(grep -c '^dispatch:' "$config" 2>/dev/null || echo 0)
    if [ "$has_dispatch" -gt 0 ]; then
      echo "$repo: HAS dispatch block"
    else
      echo "$repo: NO dispatch block (local-only)"
    fi
  else
    echo "$repo: NO plan-config.yaml"
  fi
done
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

- [ ] **Step 1: Run vk init for each unconfigured repo**

For each repo with NO `plan-config.yaml`:

```bash
cd ~/Docs/projects/HOMELAB/<repo>
vk init
```

Expected: Creates `docs/superpowers/plan-config.yaml` with no dispatch block (fail-closed), creates `docs/superpowers/{specs,plans,archived-plans}/` directories.

Verify: `cat docs/superpowers/plan-config.yaml` — should have `plan:` and `header:` sections, no `dispatch:` block.

- [ ] **Step 2: Commit the new config in each repo**

```bash
git add docs/superpowers/
git commit -m "chore: add plan-config.yaml (local-only, no dispatch)"
```

### Task 3: Verify dispatch-enabled repos

- [ ] **Step 1: Check dispatch config fields**

For each repo that HAS a `dispatch:` block:

```bash
cd ~/Docs/projects/HOMELAB/<repo>
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

- [ ] **Step 1: Identify phased plans in local-only repos**

```bash
for dir in ~/Docs/projects/HOMELAB/*/; do
  config="$dir/docs/superpowers/plan-config.yaml"
  if [ -f "$config" ] && ! grep -q '^dispatch:' "$config"; then
    # Local-only repo — check for phased plans
    grep -rl '^## Phase ' "$dir/docs/superpowers/plans/" 2>/dev/null | while read plan; do
      echo "LOCAL-ONLY phased plan: $plan"
    done
  fi
done
```

- [ ] **Step 2: Dry-run conversion for each phased plan in local-only repos**

```bash
vk plan convert <plan-path> --to flat --dry-run
```

Review the dry-run output. For each plan, decide:
- **Convert:** Plan is no longer dispatched and should be flat. Run with `--yes`.
- **Leave:** Plan has historical value in phased format. Skip.
- **Force-convert:** Plan has tracking comments from a past dispatch. Run with `--force --yes`.

### Task 5: Replace old SKILL.md files

- [ ] **Step 1: Remove old skill files**

```bash
rm -rf ~/.claude/skills/vk-plan
rm -rf ~/.claude/skills/vk-dispatch
rm -rf ~/.claude/skills/vk-progress
rm -rf ~/.claude/skills/vk-execute
```

- [ ] **Step 2: Install new skills via CLI**

```bash
vk install-skills
```

Expected: Symlinks created:
- `~/.claude/skills/vk-plan -> <repo>/skills/vk-plan`
- `~/.claude/skills/vk-dispatch -> <repo>/skills/vk-dispatch`
- `~/.claude/skills/vk-progress -> <repo>/skills/vk-progress`
- `~/.claude/skills/vk-execute -> <repo>/skills/vk-execute`

Verify:

```bash
ls -la ~/.claude/skills/vk-*
cat ~/.claude/skills/vk-dispatch/SKILL.md | head -5
```

Expected: First line is `---` (YAML frontmatter), file is under 80 lines.

### Task 6: Smoke test

- [ ] **Step 1: Verify CLI basics**

```bash
vk --version
vk --help
vk plan --help
vk dispatch --help
vk progress --help
vk execute --help
```

Expected: All commands print help text, no errors.

- [ ] **Step 2: Smoke test dispatch in a dispatch-enabled repo**

```bash
cd ~/Docs/projects/HOMELAB/superpowers-for-vk
vk dispatch docs/superpowers/plans/<existing-plan>.md --dry-run
```

Expected: Valid dry-run output showing phases, target repo, project board.

- [ ] **Step 3: Smoke test local mode in a local-only repo**

```bash
cd ~/Docs/projects/HOMELAB/kid-laptops
vk progress board
```

Expected: Local plan status table (or "no plans found" if no plans exist).

- [ ] **Step 4: Verify dispatch gate refuses in local-only repo**

```bash
cd ~/Docs/projects/HOMELAB/kid-laptops
vk dispatch docs/superpowers/plans/<any-plan>.md --dry-run
```

Expected: Exit code 1, message: "Dispatch unavailable — no `dispatch:` block in `docs/superpowers/plan-config.yaml` for this repo."

### Task 7: Verify CI

- [ ] **Step 1: Push and verify CI in superpowers-for-vk**

```bash
cd ~/Docs/projects/HOMELAB/superpowers-for-vk
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
