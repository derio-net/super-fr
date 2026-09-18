# Run anchors — bc88

Arm G did **not** use the prepared clean room. Recorded here so its numbers stay
recoverable from the shared store.

| | Arm P | Arm G |
|---|---|---|
| Config | `cfg-P` (clean, as designed) | **default global config** — no `XDG_CONFIG_HOME` set |
| Data store | `data-P/opencode/opencode.db` (isolated) | **shared** `~/.local/share/opencode/opencode.db` |
| Working dir | `experiment-bc88/planned` | `~/Docs/projects/blog-craft` → fr worktree `blog-craft/gh-88` |
| Recording | `planned.cast` | **none** |
| Base | `2874f35c3755` | `2874f35c3755` (verified: the worktree contains the pin) |

**Arm G root session: `ses_f494e3317ffeho2OL5ZqKi`** (started 2026-09-19 00:45,
directory `~/Docs/projects/blog-craft`). Subagents attach to it as children, so:

```sql
-- arm G totals, from the shared db
WITH g(root) AS (VALUES('ses_f494e3317ffeho2OL5ZqKi'))
SELECT COUNT(*), SUM(parent_id IS NOT NULL), ROUND(SUM(cost),2)
FROM session, g WHERE id = g.root OR parent_id = g.root;
```

## Confounds this introduces, to carry into the write-up

1. **No recording for arm G.** asciinema cannot attach to a running process, so
   this is unrecoverable. The session transcript (`opencode export`) is the
   substitute and is arguably richer, just not screenable.
2. **Arm G has more context than arm P**: the full global config — 25 skills,
   19 commands and the `gebit-mcp` server — where arm P has only blog-craft's
   repo tooling plus nothing. fr is therefore *not* the single variable between
   the arms; extra tooling and an MCP server ride along with it.
3. **Shared store**: arm G's cost/token totals must be filtered by the root
   session above, never summed over the whole db.
