# Codex harness adapter — implementation plan

**Spec:** `docs/superpowers/specs/2026-09-16-codex-harness-adapter-design.md`
**Status:** Not Started

## What this builds

super-fr's fourth harness track. Codex CLI joins Claude Code, OpenCode and
Hermes Agent: the `fr-*` skills become discoverable in a Codex session,
super-fr's standing rules reach the user through Codex's global instruction
surface, and the fr-isolation gate — **edits and bash** — is wired as Codex
PreToolUse hooks.

The shape deliberately parallels the Hermes track, because Hermes solved the
same problem: skills mirror + rules managed-block + thin hook entrypoints over
the shared decision library + a tested `fr <harness> install` for the invasive,
user-owned-file mutations.

## Why it is worth doing

Two observed failures, not a hypothesis:

1. A Codex session in `derio-net/willikins` (PR #405) added "Codex
   compatibility" while knowing nothing about fr — it edited the base clone
   instead of an isolation workspace, wrote a v1 flat plan, and put review
   reports in an ad-hoc `docs/reviews/`. Every one of those is a rule super-fr
   already ships to three other harnesses.
2. The operator's `~/.codex/skills/fr-*` links were all dangling. **Codex skips
   a dangling skill symlink silently** — verified: exit 0, empty stderr, the
   skill simply vanishes from the catalog. There is no error to notice, which
   is why they stayed broken. That single fact is why phase 5 ships
   `fr codex doctor` rather than a one-time relink.

## The two traps this plan exists to avoid

Both would produce a gate that looks healthy and enforces nothing.

**Relative paths (phase 2, task 1).** `fr_isolation_decide_edit()` returns
ALLOW for any non-absolute path — deliberately, so a relative path can't be
resolved against the wrong repo. apply_patch paths are repo-relative. An
entrypoint that forwards them verbatim allows *every* patch while every other
test stays green. Phase 2 proves the fix can fail by removing it and watching
the test go red.

**Atomicity (phase 2, task 2).** A patch carries many files and Codex cannot
partially apply. The tempting bug is to allow once the first path passes, so
the test asserts a mixed patch denies **in both file orders**.

A third, quieter trap is handled in phase 2 task 4: the brief asked for a
"fail-open when jq is absent" test, which would assert nothing, because the
shared library resolves python3 first and jq only as a fallback. It is replaced
by two honest tests — armed-without-jq, and explicit-refusal-with-no-parser.

## Phase map

| # | Phase | Depends on | Why here |
|---|---|---|---|
| 1 | Walking skeleton: path extractor + edit gate | — | Smallest end-to-end slice that puts a real Codex payload through the real shared decision library and turns CI green. |
| 2 | Harden the edit gate | 1 | The traps above, plus the escapes (`FR_BASE_OK`, `.fr-isolation-allow`) and parser posture. |
| 3 | Bash guard | 1 | git/gh mutations, and an apply_patch smuggled through a shell call — which would otherwise pass both hooks. |
| 4 | `sync-codex.py` + mirrors + tripwires | 1, 3 | Needs the hook scripts to exist before the hooks snippet can name them. |
| 5 | `fr codex install/uninstall/doctor` + installer | 3, 4 | Consumes the generated snippets and the hook tree. |
| 6 | Docs, version bump, acceptance flips | 2, 4, 5 | Everything it documents must already exist. |

## Decisions carried in from the spec

Recorded in the spec journal (`fr journal render --scope spec --slug
2026-09-16-codex-harness-adapter`), the load-bearing ones here:

- **d2** — skills install to `$CODEX_HOME/skills/<name>`. Empirically scanned
  despite the docs page omitting it, matches OpenAI's own `skill-installer`
  default, and is where the operator's broken links already live — so install
  repairs in place instead of creating a second competing location.
- **d3 / r1** — the `~/.codex/AGENTS.md` block is a **pointer**, not rule
  bodies. Measured: full inline is 13,129 bytes; with super-fr's own 16,365-byte
  AGENTS.md that is 90% of the 32 KiB `project_doc_max_bytes` cap, and discovery
  *stops* at the cap, silently truncating the consuming repo's own instructions.
  Full bodies install as files; the block is test-enforced at ≤ 2 KiB.
- **d5** — hooks register at user level with absolute paths. A project-level
  `.codex/hooks.json` would need a command-path base this session could not
  verify, and it only loads when the project is `trust_level = "trusted"`.
- **d4** — the merged-PR push guard and the SessionStart acceptance nag are
  deferred with reasons, not half-built.

## What this plan does NOT prove

Skill **discovery** is empirically verified: `codex debug prompt-input` renders
the model-visible prompt offline, and the `fr-*` skills appear in it — including
ones that exist only under `~/.codex/skills`. Hook **firing** is not: it needs
a live Codex session plus a one-time `/hooks` trust grant, and trust is recorded
against the hook's hash — so a super-fr upgrade that edits a hook re-arms the
review and the gate is inert until re-trusted. That is a real limitation of the
Codex track, documented in the README rather than glossed, and exercised by the
spec's post-merge Test Plan.
