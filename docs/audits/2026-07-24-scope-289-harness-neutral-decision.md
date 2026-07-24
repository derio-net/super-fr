# Scope decision — #289 "harness-neutral multi-agent story"

**Date:** 2026-07-24
**Issue:** [derio-net/super-fr#289](https://github.com/derio-net/super-fr/issues/289) — *"multi-agent support"*
**Type:** scoping decision (no implementation)
**Recommendation:** **CLOSE #289** as substantially delivered and superseded by
the established per-harness compat pattern. Open one narrow follow-up (a
"how to add a harness" playbook); handle each future harness as its own compat
issue, exactly as OpenCode (#368) and Hermes (#393) already were.

---

## 1. What #289 originally proposed

> Skills, plugins, hooks, rules etc, currently are only used/tested for Claude.
> Perhaps we need a new project (multi-fr?) that converts and maintains
> multi-agent setups from harness-specific to a common AGENTS.md format
> (idempotent, ci tested). The folder concept from Clief Notes can be used.

Three claims are bundled here:

1. **Premise:** super-fr is Claude-only.
2. **A common format** everything converts to/from (`AGENTS.md`).
3. **A converter** that is idempotent and CI-tested — proposed to live in a
   **separate project** (`multi-fr`).

## 2. Landed reality (as of 2026-07-24)

The premise is stale and the goal is substantially met — **in-repo**, not as a
separate project.

| #289 asked for | Landed today |
|---|---|
| Not Claude-only | **Three harnesses**: Claude Code, OpenCode (#368), Hermes Agent (#393) |
| A common `AGENTS.md` format | `AGENTS.md` is the canonical agent guide. `CLAUDE.md` is `@AGENTS.md`; `HERMES.md` points to it; OpenCode loads it via `opencode.json`'s `instructions`. Skills share one harness-neutral `SKILL.md` shape (`name`+`description` frontmatter) that all three consume unchanged. |
| An idempotent converter | Per-harness generators: `scripts/sync-opencode.py`, `scripts/sync-hermes.py`. Both have a `--check` mode (idempotent; no writes, non-zero on drift). |
| CI-tested | Drift tripwires (`test_tripwire_opencode_*_sync.py`, `test_tripwire_hermes_*_sync.py`) and install-wiring tests (`test_install_copies_*`). |
| A separate `multi-fr` project | **Deliberately not built** — support ships in-repo via `install.sh`, so a version bump delivers every harness atomically with no cross-repo drift. |

## 3. Why the literal proposal was superseded, not merely deferred

The Hermes design (`docs/superpowers/specs/2026-07-23-hermes-agent-compat-design.md`,
merged as #393 on 2026-07-23) states the current model and its rejected
alternative explicitly — **the exact question #289 raises was decided last
week**:

- *"There is **no abstraction layer; each harness is hand-wired**. The OpenCode
  track is the **template** this design parallels."*
- Non-goal: *"**No general 'harness registry' refactor.** Like Claude Code and
  OpenCode, Hermes is added as a parallel, mostly-hardcoded delivery track."*

Two structural facts make the "one universal converter" of #289 the wrong
shape, not just unbuilt:

- **Harness discovery surfaces are irreducibly different.** OpenCode has three
  surfaces (skills / an `instructions` array / slash commands); Hermes has a
  single `SOUL.md` global + category skill dirs; Claude Code has the
  plugin/marketplace layout + `~/.claude/rules/`. There is no single converter
  to extract — the per-harness logic *is* the work. `sync-opencode.py` (304 LoC)
  and `sync-hermes.py` (188 LoC) differ because the targets differ, not because
  of accidental duplication.
- **Direction is source → harnesses, not harness → common.** #289 imagined
  `AGENTS.md` as the format everything converts *from*. Reality inverts it: the
  canonical sources are `plugins/super-fr/skills/` + `plugins/super-fr/rules/`
  (plus a hand-authored `AGENTS.md`), mirrored *out* to each harness. Because
  the `SKILL.md` shape is already harness-neutral, no reverse conversion is
  needed — the "common format" exists without a bidirectional converter.

A separate `multi-fr` repo would add cross-repo version drift, a second install
path, and a second CI surface — with **no second consumer** to justify it. That
is the YAGNI/rejected alternative, and the in-repo outcome is strictly better.

## 4. Decision

**Close #289.** Its spirit — not-Claude-only, a shared format, an idempotent
CI-tested converter — is delivered. Its letter — a separate `multi-fr` project
with one universal converter — is a rejected alternative on sound grounds.

**Going-forward model:** each new harness is its own **per-harness compat
issue**, paralleling the previous harness as a template (the proven #368 → #393
path). This is already how the last two shipped; #289 as an open umbrella adds
no coordination value over that pattern and misleadingly implies a
build-a-framework track that has been explicitly declined twice.

## 5. The one genuine residual → a narrow follow-up

The per-harness playbook is real but **tacit** today — encoded only in the
Hermes spec's "parallel the OpenCode template" table and in each sync script's
docstring. The single highest-value cheap improvement is to **codify the
"adding a new harness" checklist** as a short doc (or an `AGENTS.md` section) so
the next harness is mechanical:

1. Delivery channels to parallel: **skills**, **rules**, **enforcement**
   (edit-gate + bash/push guards + session-start nag).
2. A `scripts/sync-<harness>.py` generator with a `--check` (idempotent) mode.
3. Install/uninstall wiring in `install.sh` (opt-in gated; uninstall removes
   only super-fr's own files).
4. Drift tripwire + install-wiring tests.
5. Reuse the `fr models` `harness → tier → model` seam (do not rebuild it).
6. Docs + a version bump (user-observable plugin behavior).

### 5.1 The deferred `harness_sync` helper — what and why

A second, larger residual is worth naming precisely so it is a *decision on
record*, not a blind spot: the two sync generators
(`scripts/sync-opencode.py`, `scripts/sync-hermes.py`) share a skeleton that a
third would triplicate.

**What it would be.** A small shared module (`fr`-internal, or a
`scripts/_harness_sync.py`) that owns the *transport mechanics* common to every
harness track — the parts that are identical no matter what the target is:

- **Mirror maps** — build the `skill-name → path` dicts for a
  `(canonical_dir, mirror_dir)` pair (today: `canonical_skills()` /
  `mirror_skills()`, near-duplicated across both scripts and thrice within
  `sync-opencode.py` for skills/commands/instructions).
- **Drift detection** — the byte-compare that powers every tripwire
  (`if canonical.read_text() != mirror.read_text(): report`). This is
  safety-critical scaffolding: a tripwire is only as honest as this compare,
  and it currently exists in ~5 hand-written copies.
- **Frontmatter parse** — the `---`-delimited YAML reader (`_skill_frontmatter`)
  that any harness deriving commands/metadata from a `SKILL.md` needs.
- **Mirror write** — `mkdir -p` + `write_text` + the "generated, do not
  hand-edit" source-note header.
- **`--check`/write driver** — the `main()` shape: iterate surfaces, collect
  drift, exit non-zero on `--check`.

Each harness script then shrinks to a **declaration** — "here are my surfaces
and their target paths" — plus the one or two genuinely bespoke *render*
functions the transport can't know (OpenCode's `render_command` from skill
frontmatter; Hermes's `render_rules_block`, which concatenates rules into a
single delimited `SOUL.md` managed block rather than one file per rule). The
irreducibly per-harness part stays per-harness; only the plumbing is shared.

**Why build it (eventually).**

- **One place to be correct.** Drift detection and the source-note contract are
  the load-bearing safety mechanism behind every `test_tripwire_*_sync` test.
  With N hand-copied versions, a fix to one (normalize a trailing newline,
  handle a missing mirror dir, follow a symlink) silently fails to reach the
  others. A shared helper collapses that to a single tested surface.
- **It directly cheapens the going-forward model.** §4 commits to "each new
  harness = its own compat issue." The helper is exactly what makes that issue
  small: a new-harness author writes a surface declaration and their one weird
  render function, not another ~200-line copy of the scaffolding.
- **Testable once.** Frontmatter edge cases and drift semantics get unit-tested
  against the helper directly, instead of being re-exercised indirectly through
  each harness's tripwire.

**Why not now (rule of three).** At N=2 the two scripts *look* similar but their
surfaces diverge structurally — Hermes has no commands surface at all, and the
two rules-delivery models differ in kind (per-file mirrors vs. one concatenated
managed block), not just in path. Extracting today would guess the abstraction
boundary from two points; the **third** harness is what reveals which seams are
truly invariant versus coincidentally alike. Premature extraction risks a helper
the third harness has to fight or re-open anyway.

**Recommended trigger.** Do the extraction *as part of* the third harness's
compat work, where it pays for itself immediately by making that very harness
cheaper — not as speculative refactor beforehand. Until then, the two scripts
staying parallel-by-copy is the correct, lower-risk state.

## 6. Handoff

- No `fr-plan` handoff and no build: this brainstorm's outcome is a decision to
  close, not a design to implement.
- **No acceptance-matrix rows are owed.** A scoping decision that recommends
  closing an issue ships no new operator-facing surface or capability, so there
  is no business-level "operator can do X" claim to pin. (New harnesses, when
  they come, carry their own rows via their own compat issue — as #368 and #393
  did.)
- Suggested issue action: close #289 with a comment linking this record and the
  proposed follow-up; file the "adding a new harness" playbook as a fresh issue.
