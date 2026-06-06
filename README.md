# super-fr

Canonical planning and work lifecycle skills for derio-net repos. Wraps the upstream
[superpowers](https://github.com/obra/superpowers) plugin with phase-based plans,
profile-driven per-repo behavior, and work lifecycle tracking.

## Skills

| Skill | Description |
|-------|-------------|
| `fr-plan` | Canonical plan skill — phase-structured plans with profile-driven behavior and spec index maintenance |
| `fr-dispatch` | Dispatch plan phases to GitHub Issues with profile-aware config |
| `fr-execute` | Execute an agentic phase (agent-facing, Phase > Task > Step) |
| `fr-progress` | Work lifecycle — plan sync, status board, create/transition, health, audit |

## Installation

### Option 1: Plugin (recommended)

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "super-fr@derio-net": true
  }
}
```

### Option 2: User-level install

```bash
git clone https://github.com/derio-net/super-fr
cd super-fr
./scripts/install.sh   # installs skills + rules + vk CLI (via uv tool)
```

### vk CLI only

If skills are already installed via plugin but you need the CLI:

```bash
uv tool install path/to/super-fr   # or: uv tool install git+https://github.com/derio-net/super-fr
```

## Per-Repo Profile

Each repo can define `docs/superpowers/plan-config.yaml` to control:
- Filename patterns, required headers, status values
- Post-deploy phases (auto-appended by fr-plan)
- Dispatch config (project board, labels, target repo)

## Plan Model

- **One plan = one repo's worth of work.** Plans live in the repo they modify.
- **One phase = one GitHub Issue = one PR.** Phases are scoped for reviewability.
- **Cross-repo features use multiple plans**, coordinated via the spec's "Implementation Plans" section (maintained automatically by fr-plan).

## Requirements

- [superpowers](https://github.com/obra/superpowers) plugin installed
- GitHub CLI (`gh`) authenticated
- VK MCP server (optional): `npx vibe-kanban@latest --mcp`

## Validator

`scripts/validate-plans.sh` — canonical, profile-driven plan validator. Per-repo thin wrappers delegate here.
