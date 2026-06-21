# Plan: isolation cold-start fetch + base on origin/<default>

Implements [spec](../../specs/2026-06-21-isolation-fetch-origin-base-design.md)
for [#322](https://github.com/derio-net/super-fr/issues/322).

## Goal

A genuinely **new** isolation branch must be cut from a freshly-fetched
`origin/<default-branch>`, not the base repo's current (possibly feature-parked
or stale) HEAD — so an isolated fix never silently inherits unrelated un-merged
commits into its PR. Reuse and continuation flows (existing worktree, existing
branch) are untouched.

## Why this shape

`_git_worktree_add` already has three code paths and only one of them — the
brand-new-branch `-b` path — forks from current HEAD. The fix lives entirely in
that path, so corner case #1 ("continuation/reuse must NOT rebase onto main") is
honored by construction; we add **no** new reuse-vs-cold-start branching.

## Phases

1. **Cold-start base resolution in the Target (TDD).** The core: a real
   bare-origin test harness, RED tests for the full behavior matrix (default
   origin/<default>, `--base HEAD`/`<ref>`, `--no-fetch`, no-remote and
   fetch-failure auto-fallback, the default-branch resolution chain, and a
   reuse-never-rebases guard), then the GREEN implementation
   (`_has_origin_remote`, `_fetch_origin`, `_resolve_default_branch`,
   `_cold_start_base`, params threaded through `up` / `_git_worktree_add`).

2. **CLI flags and Target protocol (TDD).** `--base` / `--no-fetch` typer
   options on `fr isolation up`, forwarded to the Target; the `Target` Protocol
   `up` signature gains the two defaulted params.

3. **Skill docs and version bump.** Document the new default + escape hatches in
   fr-isolation / fr-debugging / fr-brainstorming (respecting the 120-line cap),
   then `bump-version.py patch` (3.4.1 → 3.4.2) and the full local CI gate.

## Decisions (from the batched Q&A)

- Default for a new cold-start branch: fetch `origin` + base on
  `origin/<default>`.
- Default-branch resolution: `git symbolic-ref refs/remotes/origin/HEAD`
  (refreshed by `git remote set-head origin --auto`) → `gh repo view` → `main`.
- Overrides: `--base <ref>` and `--no-fetch`, plus an automatic
  fall-back-to-HEAD-with-WARNING when there is no remote or the fetch fails
  (never error).

## Out of scope

Per-repo config key for the base policy; touching the local `main` ref;
changing reuse semantics; a `--base` that also fetches.
