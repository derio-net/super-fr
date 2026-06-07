# Isolation guard `cd` transition allowance — design

**Issue:** [#279](https://github.com/derio-net/super-fr/issues/279)
**Status:** draft
**Date:** 2026-06-07

## Problem

The strict-mode isolation guard (`plugins/super-fr/hooks/fr-isolation-guard.sh`,
shipped in #265) deadlocks the documented host-side `gh`/`git` surface:

- The guard denies any Bash call whose **declared session cwd** (the `.cwd`
  field of the PreToolUse envelope) resolves inside the base repo, allowing
  only `fr isolation …`.
- Every fr pipeline session starts with its shell cwd in the base repo
  (that's where `fr isolation up` runs), and Claude Code resets the
  persistent shell cwd back there whenever a `cd` lands outside the
  session's allowed working directories.
- The hook sees the declared cwd, not the effect of inline `cd` chains — so
  `cd <worktree> && gh pr list` is evaluated with cwd = base repo and
  denied. Even a bare `cd <worktree>` is denied.

Result: `fr-isolation/SKILL.md`'s contract — "ALL GitHub interaction relies
on an AUTHENTICATED HOST… run them outside `exec`, from the worktree" — is
unreachable while the pipeline sentinel is live. The container is
deliberately tokenless, so there is **no allowed path** for `gh` reads,
pushes, or PR creation. Observed live on `derio-net/frank` (2026-06-07) and
reproduced in this repo during this run's own brainstorm.

An ephemeral patch lives in the operator's plugin cache
(`~/.claude/plugins/cache/derio-net/super-fr/3.1.1/hooks/fr-isolation-guard.sh`);
it is lost on the next plugin update. This spec is the durable fix.

## Decision record (operator Q&A, 2026-06-07)

| Decision | Choice |
|---|---|
| Allowance breadth | **fr worktrees + temp dirs** — narrower than the issue's field-tested "anywhere outside the repo" patch |
| Harness working-directory enhancement | **Defer** — file a follow-up issue; this fix is guard-only |
| Copy updates | **Both** — deny message gains the `cd <worktree> && …` hint; SKILL.md documents the compound shape |
| Post-merge Test Plan | **Yes** — short live-session verification after the 3.1.2 release |

## Design

### Transition allowance

Insert into `fr-isolation-guard.sh`, after the cwd-inside-repo check and
before the `fr isolation` allowlist check:

1. Extract a **leading** `cd <dir>` from the command (the issue's sed
   pattern: handles double-quoted, single-quoted, and bare targets; stops
   at whitespace, `;`, `&`, `|`). A command that does not *lead* with `cd`
   gets no allowance. Bare `cd` (no argument) is not matched and stays
   denied.
2. Expand a leading `~` to `$HOME`.
3. Resolve the target physically (`cd <dir> && pwd -P`). An unresolvable
   target falls through to the existing logic (deny unless `fr isolation`).
4. Allow iff the resolved target is inside one of the **allowed prefixes**
   AND outside the base repo root; otherwise fall through. The repo-root
   check takes precedence over prefix membership — a base repo that itself
   lives under an allowed prefix (e.g. a repo under `/tmp`, or the unit
   tests' `tmp_path` repos) must still be guarded. The guard re-evaluates
   every subsequent call against its own declared cwd, so nothing is lost.

Only the LEADING `cd` is evaluated — by design. A later segment of the same
compound command can `cd` back into the base repo
(`cd <worktree> && cd <repo> && make` is allowed); re-guarding would require
parsing arbitrary shell, and the guard's charter is a discipline backstop,
not a security boundary. Each *new* Bash call is still re-evaluated against
its declared cwd. A test pins this as intentional.

### Allowed prefixes

A colon-separated list, env-overridable for tests (precedent:
`FR_SENTINEL_DIR`):

```
FR_CD_ALLOW_PREFIXES   default: $HOME/.cache/fr/worktrees:/tmp:${TMPDIR:-}
```

- `$HOME/.cache/fr/worktrees` — the canonical worktree root
  (`packages/fr/src/fr/isolation/local.py` derives
  `~/.cache/fr/worktrees/<repo>/<branch with / → __>`).
- `/tmp` and `$TMPDIR` — temp dirs (macOS `$TMPDIR` is under
  `/var/folders/…`, distinct from `/tmp`; both are listed).
- Each prefix is itself resolved with `pwd -P` before matching (macOS
  `/tmp` → `/private/tmp`), and matching uses the existing
  trailing-slash idiom so `/tmp` never matches `/tmp-other`. A prefix that
  does not exist or is empty is skipped.

Worktrees created with `fr isolation up --path <custom>` outside the
canonical root are NOT covered by the default list — accepted: the default
path is the only one the fr pipeline itself produces, and the env override
exists for exotic setups.

**Divergence from the live cache patch:** the operator's 3.1.1 cache copy
allows *any* `cd` out of the repo; this shipped version is deliberately
tighter (worktrees + temp only). After the 3.1.2 plugin update replaces the
cache, e.g. `cd ~/Developer/foo && …` will be denied during a pipeline —
that is the chosen discipline, not a regression.

### Copy changes

- **Deny message** (same jq line, reworded): mention the transition shape,
  e.g. "Host-side git/gh ops: lead with `cd <worktree> && …` (run from the
  worktree cwd, not the base repo)."
- **`plugins/super-fr/skills/fr-isolation/SKILL.md`** (exec-bridge
  discipline section): one bullet documenting that the harness resets the
  persistent shell cwd, so every host-side git/gh op is a compound
  `cd <worktree> && gh …`, which the guard explicitly allows.

### Out of scope (follow-up issue)

`fr isolation up` suggesting — or automating — the addition of the worktree
as an additional Claude Code working directory, which would stop the
harness cwd resets entirely. Filed as a separate issue at delivery time.

## Tests

Extend `tests/unit/test_hooks_guard.py` (same harness: subprocess + env
injection). All tests set `FR_CD_ALLOW_PREFIXES` explicitly to
`tmp_path`-controlled dirs — never rely on the real `/tmp`/`$TMPDIR`
defaults, because pytest's `tmp_path` itself lives under `/tmp` (Linux) or
`$TMPDIR` (macOS) and would make breadth tests pass vacuously.

| Case | Expect |
|---|---|
| `cd <allowed-worktree> && gh pr list`, cwd = base repo | allowed |
| bare `cd <allowed-worktree>` alone | allowed |
| `cd <dir under second (temp) prefix> && ls` | allowed |
| quoted target with spaces: `cd "<allowed>/a b" && ls` | allowed |
| `~`-prefixed target resolving into an allowed prefix | allowed |
| `cd <repo subdir> && git status` | denied |
| `cd <outside both prefixes>` (the breadth tightening) | denied |
| unresolvable target | denied |
| non-leading cd: `echo x && cd <allowed> && gh …` | denied |
| prefix-collision: target `<prefix>-other` | denied |
| repo itself under an allowed prefix, `cd <repo subdir>` | denied (repo-root precedence) |
| deny reason mentions the `cd <worktree> && …` hint | message check |

Existing tests must keep passing unchanged (the allowance precedes the
`fr isolation` check but only fires on leading-`cd` commands).

## Versioning

Patch bump → **3.1.2** (`scripts/bump-version.py patch`): hook behavior and
skill copy are installer-shipped, user-observable surfaces.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-07-isolation-guard-cd-transition | `derio-net/super-fr` | `2026-06-07-isolation-guard-cd-transition` | — |

## Test Plan

Post-merge — operator-driven, after the v3.1.2 release and a plugin
update on this Mac:

1. Confirm the plugin cache now serves 3.1.2 and the ephemeral 3.1.1 patch
   is gone: `ls ~/.claude/plugins/cache/derio-net/super-fr/` shows `3.1.2`,
   and its `hooks/fr-isolation-guard.sh` contains the
   `FR_CD_ALLOW_PREFIXES` allowance.
2. In a fresh Claude Code session in any fr-enabled repo, invoke an fr-*
   pipeline skill, `fr isolation up --branch test/guard-check`, then:
   - `cd ~/.cache/fr/worktrees/<repo>/test__guard-check && gh pr list` →
     **allowed** (runs).
   - `git status` with cwd = base repo → **denied** with the new hint text.
   - `cd ~/Developer && ls` → **denied** (breadth tightening holds).
3. `fr isolation down --branch test/guard-check` to clean up.
