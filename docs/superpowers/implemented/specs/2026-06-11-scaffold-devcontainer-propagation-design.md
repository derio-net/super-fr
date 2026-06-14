# Scaffold commits the devcontainer profile so the isolation worktree can see it

**Date:** 2026-06-11
**Status:** Approved
**Repo:** derio-net/super-fr
**Closes:** part 2 of #299 (parts 1 & 3 shipped in #305)

## Implementation Plans

| Plan | Target repo | Slug | Status |
|------|-------------|------|--------|
| 2026-06-11-scaffold-devcontainer-propagation | `derio-net/super-fr` | `2026-06-11-scaffold-devcontainer-propagation` | — |

## Problem

On a repo with **no devcontainer profile yet**, the fr-goal bootstrap
deadlocks at the hand-off from `fr init scaffold` to `fr isolation up`:

- `fr init scaffold` (`isolation/scaffold.py`) only **writes**
  `.devcontainer/<profile>/devcontainer.json` + `.devcontainer/fr-profiles.yaml`
  into the base working tree (`write_text`, never `git add`/`commit`). The
  module docstring even labels them "(committed)" — an *intent*, not an action.
- `fr isolation up` (`isolation/local.py:88`) cuts the worktree from the
  branch's **committed** tree (`git worktree add … <branch>`), then runs
  `devcontainer up --config=<worktree>/.devcontainer/<profile>/devcontainer.json`
  (`local.py:90,95-104`).
- The scaffolded config is uncommitted → absent from the worktree → `devcontainer
  up` fails with a cryptic "Dev container config … not found".

The fr-init skill says "commit the `.devcontainer` files", but base-repo git
ops are gate-denied for the agent (the gate even after #305 only allows `fr
init`, not `git commit`), so the agent can't satisfy that step. The operator
must hand-commit — the bootstrap is not agent-completable.

`resolve_profile` already reads from the **base** repo (`local.py:77` passes
`self.repo_root`); only the `config` *path* (`:90`) is worktree-bound. So the
sole missing piece is getting the profile into the worktree's committed tree.

## Decision (operator-approved)

**Approach A — scaffold commits the profile**, chosen over having `up` copy an
uncommitted `.devcontainer` into the worktree (B/B′) or fall back to the base
config path (F). A devcontainer profile is permanent repo infrastructure that
belongs on the base branch, committed once, so every future feature inherits it
and `up` stays trivial; B/B′ bundle the profile into an unrelated feature
branch, and F never lands it (the deadlock silently recurs).

**Committing is intrinsic, not opt-in.** A scaffold whose files aren't
committed isn't a usable profile (since `up` needs them committed), so scaffold
**commits by default**; `--no-commit` is a write-only escape hatch for tests /
advanced staging.

| Decision | Choice |
|---|---|
| How the profile reaches the worktree | A — `scaffold` commits it |
| Commit default | **On.** `--no-commit` opts out (write-only) |
| Commit target | the current branch (HEAD) — during bootstrap that's `main` |
| Commit scope | exactly the files scaffold wrote: `.devcontainer/<profile>/` + `.devcontainer/fr-profiles.yaml`. Never the operator's other changes. The host secrets env-file lives outside the repo and is never committed |

## Design

### 1. `scaffold` commits the profile (default on)

After `scaffold_profile(...)` writes the files, it makes a **scoped** commit on
the current branch:

```
git add .devcontainer/<profile>/ .devcontainer/fr-profiles.yaml
git commit -m "chore(fr): scaffold <profile> devcontainer profile"
```

- **Scoped add** — only the two paths scaffold wrote are staged; a dirty base
  tree (the operator's unrelated changes, staged or not) is untouched and not
  swept into the commit.
- Gate behind a `commit: bool = True` parameter on the writer; the
  `fr init scaffold` CLI exposes `--no-commit` (store_false) to set it `False`.
- Commit on **HEAD** — no branch creation or switching. During bootstrap HEAD
  is `main`, so the profile lands as permanent infra; the later feature PR
  carries only the feature.

**Edge cases (each a test):**
- **Nothing to commit** (re-scaffold of an unchanged profile): the scoped `add`
  stages nothing → detect (`git diff --cached --quiet`) and **skip the commit**
  (no empty commit, no error).
- **Zero-commit repo** (brand-new `git init`, no commits yet): the scoped commit
  becomes the repo's initial commit — works, no special-casing needed.
- **`.devcontainer` is git-ignored**: the `add` stages nothing (ignored) →
  **warn** ("`.devcontainer` is git-ignored — profile written but not committed;
  `up` won't see it") and skip, rather than a silent no-op.
- **`--no-commit`**: today's behavior exactly — files written, no git side
  effect.

### 2. `fr isolation up` — actionable error (complementary UX fix)

`up` logic is otherwise unchanged. Before `devcontainer up`, if the worktree's
`config` path is missing **and** the base repo's copy is **genuinely
uncommitted** (`git status --porcelain -- <path>` non-empty — untracked or
dirty), raise a targeted `IsolationError`. The porcelain gate matters: a
profile that *is* committed (on `main`) but merely absent on an older target
branch must NOT be misreported as "not committed" — that case falls through to
the normal path. Message:

> profile `<name>` is written in the base repo but not committed, so the
> worktree can't see it — run `fr init scaffold --profile <name>` (which now
> commits) or commit `.devcontainer/` yourself, then retry `fr isolation up`.

This converts the deadlock's cryptic symptom ("devcontainer up failed: config
not found") into its cure. It is a safety net; with default-on commit it should
rarely fire.

### 3. Skill wiring

- **fr-init skill:** drop the "now commit the `.devcontainer` files" manual step
  (gate-blocked for the agent); committing is now part of `fr init scaffold`.
- **fr-goal / fr-brainstorming bootstrap notes:** align — after `fr init
  scaffold` the profile is committed, so the immediately-following `fr isolation
  up --branch feat/<slug>` finds it. With #305 (part 1) allowing `fr init`
  through the gate and this part committing, the fr-goal bootstrap of a fresh
  repo is now fully agent-completable end-to-end.

## Testing (TDD)

`tests/unit/test_init_scaffold.py` (real-git-repo fixture already present):

- **default commits the profile** — after `scaffold`, `git log` shows the
  `chore(fr): scaffold …` commit and `.devcontainer/<profile>/devcontainer.json`
  + `fr-profiles.yaml` are tracked at HEAD.
- **scope** — a pre-existing dirty file (staged and unstaged) in the base tree
  is **not** in the scaffold commit, and remains dirty afterward.
- **`--no-commit`** — files written, `git log` unchanged (no new commit).
- **re-scaffold unchanged** — second `scaffold` of the same profile makes **no**
  new commit (and doesn't error).
- **zero-commit repo** — `scaffold` in a freshly `git init`'d repo creates the
  initial commit containing the profile.
- **git-ignored `.devcontainer`** — warns, makes no commit, exits 0.

`tests/unit/test_isolation_cmd.py` / `test_isolation.py`:
- **up actionable error** — with an uncommitted base `.devcontainer/<profile>`
  and a worktree lacking it, `up` raises the targeted "not committed" error
  (not the raw `devcontainer up failed`).

## Files touched

- `packages/fr/src/fr/isolation/scaffold.py` — commit logic + `commit` param
- `packages/fr/src/fr/commands/init_cmd.py` (or wherever `fr init scaffold` is
  defined) — `--no-commit` flag
- `packages/fr/src/fr/isolation/local.py` — actionable missing-config error
- `plugins/super-fr/skills/fr-init/SKILL.md` (+ fr-goal / fr-brainstorming
  bootstrap notes) — drop the manual-commit step
- `tests/unit/test_init_scaffold.py`, `tests/unit/test_isolation_cmd.py`

## Out of scope

- #299 parts 1 (gate allowlist) and 3 (exec workspace resolution) — shipped in
  #305.
