# Placement resolver, quiet, stealth and moves (plan 3 of 3)

Plan 3 of `2026-11-04-repo-feature-settings-design.md` (R29): R1 and R23–R28,
plus the parts plans 1 and 2 deferred to it. Those are `fr settings init
--quiet`/`--stealth`, R5's stealth rule, R18's logical references resolved
through R1's resolver instead of repo paths, and R23's atomic push. It adds no
artifact kind (spec §5). It changes the hooks, the OpenCode plugin (`bun test`)
and the Hermes hook, with their `parity.yaml` rows.

## Phases

1. **The resolver** (R1 Python side, R18; skeleton). `fr.artifacts.paths` is
   the one module that names an artifact directory. Every other module asks it.
   - `ArtifactKind.locator` becomes the resolver's `repo` output.
   - `fr.acceptance.logical.resolve_logical` resolves through it.
   - `fr settings paths --shell|--json` prints its answers.
   - A tripwire (AST, string constants outside docstrings) refuses an artifact
     path literal anywhere else in `packages/*/src`. Its allowlist of modules
     not yet converted may only shrink, and phase 2 empties it.
   - Only `repo` is served; behaviour does not change.
2. **Every caller on the resolver** (R1, rest of the Python side). The ~115
   modules the inventory found, in both forms (`"docs/superpowers/…"` and
   `root / "docs" / "superpowers"`), across `fr`, `fr-dispatch`, `fr-vk` and
   `fr-herdr`, plus the CI templates in `fr/acceptance/scaffold.py`. The
   tripwire's allowlist ends empty.
3. **Quiet** (R2's quiet source, R3 `init --quiet`, R23). The switch lives on
   `refs/remotes/origin/fr`. The placement is sticky in the isolation state.
   - fr's artifacts and `chore(fr):` commits go to a second worktree of `fr`.
   - `fr push` pushes the code and `fr` with `git push --atomic`. On a
     rejected `fr` it fetches, replays and retries; bookkeeping is pushed alone.
   - Nothing reaches the product branches, and runner dispatch is refused.
4. **Stealth** (R2's stealth source, R3 `init --stealth`, R5's stealth rule,
   R24). Stealth is chosen per run (`mode=stealth`). The marker and state
   record it and the tracking ref.
   - Every state write pushes compare-and-swap, and a failed push is fatal.
   - The privacy guard refuses a tracking repo more visible than the target.
   - Resume reconciles the product head the state recorded with the branch.
   - The skills learn `mode=stealth`.
5. **Merged status outside `repo`** (R17's quiet/stealth clause, R25). A
   feature's merged status and order come from its code branch's merge into
   the product's default ref. `merged: <sha>` records are a cache, and archive
   appends one and moves nothing.
6. **Hooks, OpenCode, Hermes** (R1 shell side, R26).
   - The bash decision library, `fr-worktree-create.sh`, the nag hooks, the
     OpenCode plugin and the Hermes hook read `fr settings paths --shell` (or
     its JSON). The plugin falls back to the plans test only when `fr` is
     absent, and says so at load.
   - A valid `fr`-branch switch and a stealth-state workspace count as
     fr-enabled, with `parity.yaml` rows.
7. **Placement moves** (R27, R28). `fr placement move` copies, verifies,
   switches and removes, restartably. `fr placement migrate-branch` makes the
   branch migration its own commit. The CLI gate, `fr push`, `deliver` and
   `validate-artifacts` detect a mismatched branch and refuse, naming
   `migrate-branch`; CI never migrates.

## Decisions the spec left to the plan

- **One layout everywhere.** Under `quiet` and `stealth`, a feature's
  artifacts keep their `repo` layout below a feature root: `features/<feature-id>/docs/superpowers/…`
  and `features/<feature-id>/docs/acceptance/features/…`. That root is in the
  `fr` worktree (quiet) or below `<host>--<owner>--<repo>/` in the tracking
  worktree (stealth). The resolver changes the root, never the relative layout,
  so every reader keeps its shape. Cross-feature reads (the fold, logical spec
  lookup, the plans test) iterate the feature roots through one resolver
  function.
- **The feature id** is fr's branch slug (`/` → `__`, as isolation already
  names worktrees). One feature path per branch gives R23's "each commit
  touches one feature's path". A spec shared by several plans is found across
  features by its logical slug.
- **Reading the placement.** The precedence is: a stealth marker or state in
  this workspace, then a valid `origin/fr` switch, then `repo`. The settings
  file at the placement's own location is the policy source (R2).
- **`--no-fetch` at `up`** reads the last fetched `refs/remotes/origin/fr`,
  says so, and is not a reachability check. Without it, an unreachable origin
  refuses (R23).
- **The tracking worktree** is at `~/.cache/fr/worktrees/<repo>/stealth--<tracking-slug>`,
  beside the quiet `fr` worktree.

## Why these splits

- Phase 1 is the skeleton: the resolver lands before anything depends on it.
- Phase 2 is review size: ~115 mechanical call-site rewrites would drown the
  resolver's own review.
- Phases 3, 4 and 7 are one row each: `placement-quiet`, `placement-stealth`
  and `placement-move-and-drift`, each with its scenario under `tests/scenarios/`.
- Phase 5 is shared by quiet and stealth, and is an ask of its own (R17, R25).
- Phase 6 is a different surface and harness set (bash, TypeScript, Hermes),
  and needs the switch and state shapes phases 3–4 define.

## Risks

- **Phase 2 touches nearly every module.** The tripwire and the unchanged
  suite are its proof, since `repo` must stay byte-identical.
- **Quiet moves fr's own commit seam** (`commit_paths`) and the push. A wrong
  root writes artifacts onto the product branch, which is exactly what R23
  forbids. The scenario asserts the product branches carry no fr path and no
  `chore(fr):` subject.
- **Stealth's fatal push** changes resolve's failure mode. It must never leave
  the cursor moved while the tracking ref did not.
- **R23's reachability refusal** changes `up` for repos with an unreachable
  origin. Today `up` warns; under plan 3 it refuses, as the spec requires.
