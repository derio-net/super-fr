# `fr isolation up` `/add-dir` hint — design

**Issue:** [#281](https://github.com/derio-net/super-fr/issues/281)
**Status:** draft
**Date:** 2026-06-07
**Follows:** [#279](https://github.com/derio-net/super-fr/issues/279) — this is its
deferred "Out of scope" item (see
`docs/superpowers/implemented/specs/2026-06-07-isolation-guard-cd-transition-design.md`).

## Problem

The Claude Code harness resets the persistent shell cwd back to the base repo
whenever a `cd` lands outside the session's allowed working directories. #279
made the isolation guard *tolerate* this by allowing a leading
`cd <worktree> && …`, but the reset itself still fires — so every host-side
git/gh op must re-prefix `cd <worktree> &&`, and the cwd never persists in the
worktree. Observed live this run:

```
$ cd ~/.cache/fr/worktrees/super-fr/feat__issue-281 && env | grep CLAUDE
…
Shell cwd was reset to /Users/derio/Docs/projects/DERIO_NET/super-fr
```

Claude Code already has the mechanism to stop this: registering the worktree
as an **additional working directory** makes `cd` into it persist. The fr
pipeline knows the worktree path at `up` time but never tells the operator to
register it.

## Research (2026-06-07)

How Claude Code exposes "additional working directories" (official docs,
verified via claude-code-guide):

| Mechanism | Effect | Usable here? |
|---|---|---|
| `/add-dir <path>` slash command, typed live | Takes effect **immediately** mid-session; absolute paths OK | **Yes** — the only thing that persists the cwd in the *current* run |
| `permissions.additionalDirectories` in `settings.json` | Loaded **only at session start** | No — useless for the live run; would pollute a gitignored file with ephemeral worktree paths |
| `--add-dir <path>` CLI flag | Startup only | No — session already running |
| Any hook output field | **No** hook can register a working dir | No |
| External process → running session | **No** documented mechanism | No |

**Consequence:** true mid-session automation is impossible. `/add-dir` is
operator-only (the agent cannot invoke slash commands). So the durable fix is
a **suggestion**: `fr isolation up` prints a copy-pasteable `/add-dir` line and
the operator runs it once per workspace.

## Decision record (operator Q&A, 2026-06-07)

| Decision | Choice |
|---|---|
| Suggest vs automate | **Print `/add-dir` hint only** — no settings write, nothing to clean up (the settings route only helps the *next* session and pollutes `settings.local.json`) |
| Surfacing | **From `fr isolation up`, gated on `CLAUDECODE`** — the tip is a Claude Code slash command, meaningless in a plain shell; the guard deny message stays as-is (#279) |
| Post-merge Test Plan | **Yes** — the tip→`/add-dir`→cwd-persists chain is only provable in a live session the agent can't drive |

## Design

### Hint emission

In `packages/fr/src/fr/commands/isolation_cmd.py`, command `up()`, **after** the
existing summary echo:

```python
typer.echo(
    f"isolation up: worktree={state.worktree} profile={state.profile} branch={state.branch}"
)
if os.environ.get("CLAUDECODE"):
    typer.echo(
        "tip: register the worktree as a Claude Code working directory so the "
        "shell cwd persists there (no more `cd <worktree> && …` for host git/gh):\n"
        f"    /add-dir {state.worktree}"
    )
```

- Requires adding `import os` to the module (currently `json`, `Path`, `typer`).
- **Gating:** `os.environ.get("CLAUDECODE")` — truthy only inside a Claude Code
  session. A plain human shell, a script, or a non-CC agent sees only the
  summary line. `CLAUDECODE` is confirmed set in-session (verified this run);
  precedent for env-gated behavior already exists in the guard
  (`FR_CD_ALLOW_PREFIXES`, `FR_SENTINEL_DIR`).
- **Path:** `state.worktree` is the absolute worktree path — the same value
  `/add-dir` needs.
- **stdout, after the summary:** the summary line stays first and unchanged, so
  nothing that reads the first line is affected. The hint is purely additive.
- **No "already added?" detection:** the CLI cannot see the session's allowed
  dirs, so the tip prints every `up` (idempotent re-runs included). Re-running
  `/add-dir` on an already-registered path is a harmless no-op. Accepted.

The hint lives at the CLI layer (`isolation_cmd.py`), not in the `up()` Target
method (`local.py`) — the Target is the agent-agnostic lifecycle object; UX
copy and `CLAUDECODE` gating belong to the CLI surface, matching the existing
`typer.echo` summary that already lives there.

### Skill copy

`plugins/super-fr/skills/fr-isolation/SKILL.md`, the exec-bridge bullet that
documents the cwd reset (currently lines 64–69): add one sentence that
`fr isolation up` prints an `/add-dir <worktree>` tip in a Claude Code session,
and running it once stops the resets — after which a bare `cd <worktree>`
persists and the `cd <worktree> &&` prefix is no longer required for host-side
ops. The #279 compound form remains the fallback when the dir hasn't been added.

### Out of scope

- Writing `permissions.additionalDirectories` (rejected above — wrong lifecycle,
  pollutes settings).
- Surfacing the tip from the isolation-guard deny message (operator chose the
  `up`-only surface; the guard is untouched this round).
- A `fr isolation down` `/remove-dir` reminder: `/add-dir` registrations are
  session-scoped and vanish when the session ends, so no teardown is needed.

## Tests

Extend `tests/unit/test_isolation_cmd.py` (existing `CliRunner` harness;
`runner.invoke(..., env=…)` controls `CLAUDECODE` per the click/typer API —
`env={"CLAUDECODE": None}` removes it, `env={"CLAUDECODE": "1"}` sets it, so the
tests don't depend on the ambient session).

| Case | Expect |
|---|---|
| `up` with `env={"CLAUDECODE": "1"}` | output contains `/add-dir ` **and** the worktree path |
| `up` with `env={"CLAUDECODE": None}` | output contains the summary but **no** `/add-dir` |
| existing happy-path / no-profile / idempotency tests | unchanged-passing — their assertions are substring checks (`"worktree" in …`; `"a"`/`"b"` against the *status* output), which the purely-additive hint cannot break, so no env gating of existing tests is required |

## Versioning

Patch bump → **3.1.3** (`scripts/bump-version.py patch`): `src/**` (CLI output)
and `skills/**` (SKILL.md) are installer-shipped, user-observable surfaces.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-07-isolation-up-add-dir-hint | `derio-net/super-fr` | `2026-06-07-isolation-up-add-dir-hint` | — |

## Test Plan

Post-merge — operator-driven, after the v3.1.3 release and a plugin update on
this Mac:

1. Confirm the cache serves 3.1.3: `ls ~/.claude/plugins/cache/derio-net/super-fr/`
   shows `3.1.3`.
2. In a fresh Claude Code session in any fr-enabled repo, invoke an fr-*
   pipeline skill, then `fr isolation up --branch test/add-dir`. The output
   shows the summary line **and** a `tip: … /add-dir <worktree>` line.
3. Run the printed `/add-dir <worktree>`. Then
   `cd <worktree> && pwd` → cwd **persists** (no "Shell cwd was reset" message),
   and a bare host op (`git status`) run from that cwd works without the
   `cd <worktree> &&` prefix.
4. Confirm gating: the hint is Claude-Code-only — covered by unit test (a plain
   shell `fr isolation up` prints no tip).
5. `fr isolation down --branch test/add-dir` to clean up.
