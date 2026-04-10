# superpowers-for-vk

VK-aware planning and dispatch skills for Claude Code. Wraps the upstream
[superpowers](https://github.com/obra/superpowers) plugin with VibeKanban
integration — phase-based plans, automated dispatch, and agentic execution.

## Skills

| Skill | Description |
|-------|-------------|
| `vk-plan` | Write phase-structured plans with `[manual]`/`[agentic]` phases |
| `vk-dispatch` | Dispatch plan phases to GitHub Issues + VK workspaces |
| `vk-execute` | Execute an agentic phase (agent-facing) |
| `vk-progress` | Sync VK card + GitHub Issue state back to plan |

## Installation

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "superpowers-for-vk@derio-net": true
  }
}
```

## Requirements

- [superpowers](https://github.com/obra/superpowers) plugin installed
- VK MCP server available (`npx vibe-kanban@latest --mcp`)
- GitHub CLI (`gh`) authenticated
