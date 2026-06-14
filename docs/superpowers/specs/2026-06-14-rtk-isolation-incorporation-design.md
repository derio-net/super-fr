# rtk incorporation into the fr isolation / devcontainer stack

**Date:** 2026-06-14
**Status:** Seed spec (not yet approved, brainstorm deferred) — captured from
the 2026-06-14 rtk/secrets investigation so the analysis isn't re-derived later.
**Source:** operator brainstorm session 2026-06-14 (rtk token-filtering audit).
**Target repo:** derio-net/super-fr (package: `fr`, `fr.isolation`), with a
downstream tail in derio-net/runs-fr (k8s agent pods).

## Problem

`rtk` ("Rust Token Killer") saves 60–90% of tokens on dev command output by
rewriting recognised commands (`git status` → `rtk git status`) and filtering
their output. It hooks in **host-side** via `rtk hook claude` — a Claude Code
PreToolUse hook that rewrites the Bash *command string* before execution. It
can therefore only act on a command whose **outer token** it recognises.

`fr isolation exec -- <cmd>` runs `devcontainer exec … <cmd>`
(`packages/fr/src/fr/isolation/local.py:136`, verified 2026-06-14). The host
hook sees `fr` (or `devcontainer`) as the outer token, never the inner `<cmd>`,
and `devcontainer exec` is opaque to a string-rewriter. So **every command run
through the exec-bridge returns its full, unfiltered output** to the host
session. The same is true of any nesting wrapper (`uv run`, `ssh`,
`kubectl exec`) — this is a property of nesting depth, not of fr specifically.

## Investigation findings (2026-06-14)

Greenfield: **no `rtk` references** in super-fr or runs-fr before this spec.

**What is and isn't covered today:**

| Surface | Outer token rtk sees | Covered? |
|---|---|---|
| Host repo commands | `git`, `gh`, `grep`… | ✅ filtered |
| Worktree (host dir, no container) | `git`, `grep`… `cwd=worktree` | ✅ filtered |
| Subagent in a worktree | same user/session hooks | ✅ filtered |
| `fr isolation exec -- <cmd>` (devcontainer exec) | `fr` / `devcontainer` | ❌ **bypassed** |

**Magnitude (local only):** `rtk discover` over 23 sessions / 30 days reported
~115K tokens "saveable" — but that figure is an **upper bound that overstates
the opportunity**: discover reads the pre-rewrite transcript string, so it
cannot tell whether the host hook already filtered a command at execution
(it reported "already using RTK: 0.8%" against `rtk gain`'s 78.5% realised —
the two measure different things). The genuinely-unhandled wrapper class is
`fr isolation` (232 calls, mostly light `fr isolation status` output) and
`uv run` (19). So the **local** leak is modest and dominated by light status
calls, not heavy exec output.

**Measurement caveat:** `rtk gain` is structurally blind to the bypass — it
only tallies commands that *went through* rtk. Only a history scan
(`rtk discover`) can see bypassed calls, and even then only for sessions on
the local machine.

**Two execution loci behave differently** (verified against skills + code
2026-06-14):

- `fr-goal` → host devcontainer via `fr isolation exec` → rtk-reachable *in
  principle*, bypassed *today*. This is where wrapping would help.
- `fr-dispatch` → VibeKanban server-side workspaces (`fr_vk.runner`,
  `start_workspace`) → executes entirely outside the host's rtk hook. Baking
  rtk into the scaffold would **not** touch this path at all.
- **Future** runs-fr k8s agent pods → would consume the *same*
  `fr init scaffold` devcontainer, so rtk baked into that scaffold/image would
  cover the host path now and the pod path later with one investment. The
  heaviest in-container test/build output lives in these pods and is currently
  **unmeasured** (different machine, own/no rtk).

## Candidate direction (NOT yet decided)

1. Bake the `rtk` binary into the scaffolded devcontainer image
   (`fr.isolation.scaffold` / agent-images devcontainer feature).
2. In `LocalWorktreeDevcontainerTarget.exec()` (`local.py:136`), prefix the
   inner argv with `rtk` **only** for an allowlist of read-heavy commands
   (git/ls/grep/cat/find), leaving test/build runners raw — full pytest/build
   output is usually *wanted* in a TDD/debug loop, and rtk's summarisation
   would hide the failing assertion.

This keeps filtering inside the container; only the compressed result crosses
the bridge.

## Open questions / decision gates (resolve before a plan)

1. **Measure the pod first.** Does the in-pod runner / runs-fr agent pod have
   rtk? How much raw test/build output does it ship back per phase? This is the
   real leverage and the gating unknown — the local payoff alone likely does
   **not** justify the image + wrapping maintenance.
2. **Allowlist scope.** Which commands get wrapped; confirm test runners are
   excluded.
3. **Does it pay?** Net of image-size + wrapper-maintenance cost, given the
   modest local signal and the VK path being out of scope.

## Out of scope

- The `fr-dispatch` / VibeKanban server-side workspace path (outside the host
  rtk hook; wrapping the scaffold does nothing for it).
- Any change to rtk itself.

## Next step

Deferred. Before promoting this to a plan: run the pod measurement (gate 1),
then a focused brainstorm to decide go/no-go and finalise the allowlist. Tracked
by a GitHub issue referencing this file.
