# Subagent dispatch on OpenCode — the agent, the prose that forbade it, and the row that agreed

- **Issue:** [#494](https://github.com/derio-net/super-fr/issues/494) (build) — diagnosis in [#493](https://github.com/derio-net/super-fr/issues/493)
- **Date:** 2026-09-19
- **Status:** designed

## 1. Problem

`subagent-dispatch` is declared `absent` on OpenCode in `parity.yaml`, and `fr-goal`
§5 tells an OpenCode reader that phases run inline because the harness has "no dispatch
primitive of its own." Both statements are false, and they have been agreeing with each
other — plus a stale upstream issue — long enough that nobody re-derived either.

Three claims, none of which survives contact with the binary:

**1. "OpenCode has no dispatch primitive."** It has two, `@mention` and the task tool.
This repo's own recorded experiment measured thirteen dispatches through it: arm A,
harness `opencode --auto`, 13 child sessions each with `parent_id` set. So `fr-goal` on
OpenCode *already dispatched*, while the skill told the model not to.

Two caveats on that evidence, both found in spec-review (`r1`, `r2`):

- **The CSV is not on `main`.** `docs/presentation/version-1/experiment/run-metrics.csv`
  lives on the unmerged branch `feat/presentation-showdown`, so a reader on `origin/HEAD`
  cannot open the path #494 cites. Re-derived from the file at that ref and quoted here
  so the numbers stand on their own: 14 arm-A rows, one root plus **13 children**, costs
  summing to **$7.5906**; root wall-clock **56.2 min** against **77.6** (arm B) and
  **105.2** (arm C).
- **Arm A dispatched to the built-in `general` agent**, not to a named custom one — its
  titles all read `(@general subagent)`. So arm A proves the *primitive*; it does not
  prove that a **named, tool-restricted** custom agent is invocable. That second half is
  proved separately, live, in §3.A.

**2. "The blocker is the lack of an isolation-argument dispatch primitive"**
(`parity.yaml`'s `scope_note`). Self-refuting twice over. Hermes has no isolation
argument either — `fr-isolation-required.md` names Hermes and OpenCode together as
lacking one — and Hermes is declared `enforced`. And the `fr-phase-executor` carve-out
*forbids* an isolation argument for this agent: fr-goal §6 runs executors serially
inside the workspace that already exists, and `fr-phase-executor-guard.sh` refuses the
combination outright. The stated discriminator does not discriminate, and the absence
it blames is a requirement of the surface.

**3. "Custom named subagents are not reliably invocable"** (upstream
`anomalyco/opencode#29616`). Filed 2026-05-27, fixed by the version in use. Verified
live — see §3.A.

### 1.1 The prose is the actual gate

This is the step most likely to be missed, because the agent file looks like the whole
feature. Define every agent you like: `plugins/super-fr/skills/fr-goal/SKILL.md:91`
still instructs the model to run phases inline, and both sync scripts copy that prose
byte-for-byte into `.opencode/skills/`. A shipped agent nothing is told to dispatch to
is a file, not a capability.

### 1.2 What is genuinely missing

Nothing about the harness — only artifacts we never shipped.
`plugins/super-fr/agents/` contains one file, `fr-phase-executor.md`, in Claude Code's
format; this repo's `opencode.json` has no `agent` key; and `scripts/sync-opencode.py`
mirrors skills, commands and instructions but knows nothing about agents.

## 2. Goal

Ship `fr-phase-executor` as a real OpenCode subagent — mirrored, tier-aware, installed,
dispatched by the skill, declared in the matrix, and proved by a live child session —
so that subagent execution stops being a Claude-Code-only feature of super-fr.

### Non-goals

- **Hermes.** Already `enforced` via `delegate_task`; untouched.
- **`fr-phase-executor-guard.sh` on OpenCode.** It stays Claude-only: there is no
  isolation argument to refuse, and per the carve-out this agent must not have one.
- **Generalising `fr.harness.observe` to interaction rows.** Decision `d3` — see §3.E.
- **Porting the OpenCode plugin's bash gap.** Unrelated surface, still `partial`.
- **A second canonical agent.** `fr-phase-executor` is the only one today; the
  machinery is built to hold more, but none is invented here.

## 3. Design

### A. What the binary actually does — established before anything was designed

Verified against the installed `opencode` **1.18.31**, recorded as journal discovery
`x1`. These four facts are load-bearing for everything below:

| Fact | Consequence |
|---|---|
| `.opencode/agent/<name>.md` with `mode: subagent` registers as `<name> (subagent)`; the **filename** is the agent name | OpenCode has no `name:` field — the frontmatter translation must drop it |
| `permission: {edit: allow, bash: allow, webfetch: deny}` round-trips verbatim into the agent's fully-resolved permission array | the `tools:` → `permission:` mapping is confirmed, not inferred from a table |
| a global `$XDG_CONFIG_HOME/opencode/agent/<name>.md` is discovered with no project config present, and `XDG_CONFIG_HOME` is honoured | `install.sh` has a real target dir, and its test can sandbox it |
| task-tool input is `{prompt, description, subagent_type, command}`; the agent is resolved **by name** afterwards | **a dispatch call cannot carry a model** — this is what forces §3.C |

All three documented definition forms work (`opencode.json`'s `agent` key,
`.opencode/agents/`, `.opencode/agent/`). We pin **`.opencode/agent/` — singular** —
and say so in the generator, so nobody re-litigates it.

### B. A fourth category in `scripts/sync-opencode.py`

The script has three categories, each with the same four functions:
`canonical_X()` / `mirror_X()` / `find_X_drift()` / `sync_X()`. Agents become the
fourth, in that shape — not a new pattern.

The important difference is *which* of the three existing categories it resembles.
Skills and instructions are **byte-copied** mirrors (`dest.write_text(src.read_text())`);
commands are **generated** — `canonical_commands()` returns `dict[name, str]` of
expected *content*, derived from a source, and drift is a content comparison. Agents
are generated, because the two frontmatter dialects differ. So:

```
canonical_agents() -> dict[str, str]    # filename stem -> expected mirror content
mirror_agents()    -> dict[str, Path]
find_agents_drift()-> list[str]
sync_agents()      -> None
```

Canonical source: `plugins/super-fr/agents/*.md` (Claude Code format, unchanged — it is
still what Claude Code reads). Mirror: `.opencode/agent/*.md`.

#### Frontmatter translation

| Claude Code | OpenCode | Note |
|---|---|---|
| `name:` | the filename | dropped from frontmatter |
| `description:` | `description:` | required in both; carried verbatim |
| — | `mode: subagent` | **required**; omitted, it is not a subagent |
| `tools:` containing `Edit` / `Write` | `permission: {edit: allow}` | verified §3.A |
| `tools:` containing `Bash` | `permission: {bash: allow}` | verified §3.A |
| `tools:` containing `Read` / `Grep` / `Glob` | implicit | no separate permission keys |
| phase `tier` → model (`fr models`) | `model:` | §3.C |

The body is carried through unchanged. The mirror carries a generated-file banner, the
way the commands mirror carries its shape — never hand-edit it.

**The mapping is closed, not additive** (spec-review `r3`). Claude Code's `tools:` is an
*allowlist* — every tool it omits is denied. OpenCode's permission defaults are
permissive, so translating only the allowed keys would ship a mirror strictly more
powerful than its canonical source. The generator therefore also emits explicit denies
for the capability classes the canonical `tools:` line withholds:

```yaml
permission:
  edit: allow      # tools: Edit, Write
  bash: allow      # tools: Bash
  task: deny       # canonical tools: has no Agent/Task — see below
  webfetch: deny   # canonical tools: has no WebFetch
```

`task: deny` is the load-bearing one. A phase executor that can dispatch further
subagents breaks the contract its own body states — "phases run serially on one shared
branch; the worktree has exactly one writer." Verified live that both denies round-trip
into the resolved permission array.

### C. Tier → model, given that the call cannot carry one

Because the task tool resolves the agent by name and takes no model, tiering has exactly
one available channel: **one agent per tier**, each carrying its own `model:`. Decision
`d2`. `fr.types.PhaseHeader.tier` is a closed set, so the generated set is closed too:

```
fr-phase-executor.md              # untiered base, no model: -> inherits the session model
fr-phase-executor-mechanical.md
fr-phase-executor-standard.md
fr-phase-executor-hard.md
```

`fr-goal` §5 dispatches `subagent_type: fr-phase-executor-<tier>`, falling back to the
base agent when a phase declares no tier.

**Who writes `model:` is split, along the same repo > user order `fr models` already
resolves in** (and that Claude Code dispatch already uses):

- **`sync-opencode.py`** bakes `model:` from the repo's `docs/superpowers/models.yaml`
  when that file exists. It is committed, so the mirror stays deterministic across
  machines and in CI. super-fr has no such file, so **its own mirror ships model-free**
  and the agents inherit the session model.
- **`install.sh`** writes the global `~/.config/opencode/agent/` copies with
  `fr models resolve --harness opencode --tier <t>`, so a consumer's user-level
  bindings apply to the installed copies. Consequence, called out in `d2`: the OpenCode
  delivery block must move **after** install.sh's step 10 (the `fr` CLI install), since
  it now needs `fr` on PATH. A repo-level binding still wins, because `fr models
  resolve` is what does the resolving.

A missing binding is not an error: no `model:` key is written and the agent inherits.
Silent inheritance is the correct degradation here — the alternative is a dispatch that
fails on an unresolvable model id.

**How install rewrites it** (spec-review `r4`). "install.sh fills `model:`" is a bash
edit inside YAML frontmatter, which is fragile against an arbitrary layout — so the
generator does not produce an arbitrary layout. It emits a fixed frontmatter order with
`description:` as a **single-line double-quoted scalar** (never a folded `>` block, which
is what the canonical Claude Code file uses) and `mode: subagent` on its own line
immediately after:

```yaml
---
description: "…"
mode: subagent
model: …          # present iff resolved
permission:
  …
---
```

install.sh's rewrite is then one deterministic operation anchored on that known line:
drop any existing top-level `model:` line, and insert the resolved one after
`mode: subagent`. No YAML parser in the installer, and no dependence on where a
hand-edit might have put the key — because nothing hand-edits these files.

### D. `fr-goal` §5 — the clause that has to change

The `**Harness — dispatch:**` clause is the scoped-clause shape
`test_tripwire_skill_tool_neutrality.py` requires; it already names all three supported
harnesses, so it stays valid. Its OpenCode arm is replaced:

> ~~OpenCode has no dispatch primitive of its own — phases run inline, which is correct
> behaviour, not a gap.~~

becomes an instruction to dispatch `subagent_type: fr-phase-executor-<tier>` via the
task tool, **with the cost stated as a policy, not hidden**: roughly 7× an inline run
(measured $7.59 vs ~$1), in exchange for the fastest measured wall clock (56.2 min vs
77.6 / 105.2) and real per-phase context isolation. Decision `d1`.

Naming OpenCode's task tool in prose means adding it to
`TOOL_VOCABULARY["opencode"]`, which currently holds only `tool.execute.before`. The
registered name is the two-word prose form **`task tool`**, not the bare id.

> **Correction (phase 4, finding `r-p4-f1`).** This section previously justified
> registering the bare `task` with "no bare `task` token exists in any of the three skill
> trees today". **That was false, and was false on `origin/main`.** There are twelve
> occurrences — four canonical sites mirrored into three trees — and in every one, `task`
> is *fr's own plan noun*: "end every task red → green → refactor" (`fr-execute`),
> "phase number, task number, step", "(task id) in the plan journal", "a separate
> `REFACTOR + quality gate` **task**" (`fr-plan`). The original claim came from an ad-hoc
> regex run through this machine's `grep` (which is `ugrep`) that silently matched
> nothing; re-running `scan_prose`'s own pattern against `origin/main` returns all twelve.
> A load-bearing premise was checked with a substitute for the real predicate — the same
> defect shape as testing a feature without exercising it.

So the bare id is unusable: it collides head-on with the repo's core domain vocabulary and
would fire on every future sentence about a plan task. The two literal alternatives were
both worse — reword fr's domain language to dodge a regex, or weaken `scan_prose` to
backticked mentions only, which would blunt #436's class-B closer for every harness.

`task tool` matches the shape a real leak takes ("call the task tool with
`subagent_type` …"), and `_word_pattern` handles a multi-word name (matching is per line,
so the clause keeps the phrase on one line). **The trade, stated rather than hidden:** a
leak written as a bare `` `task` `` outside a scoped clause is *not* caught. It is
recorded in the vocabulary's own comment and in the test.

`TOOL_VOCABULARY` forbids one name under two harnesses, and `scan_prose` is
**case-sensitive** (`re.escape` with no `IGNORECASE`), so this cannot collide with Claude
Code's `Agent` nor with a capitalised `Task` in unrelated prose (spec-review `r5`).

Regenerating the mirrors (`scripts/sync-opencode.py`, `scripts/sync-hermes.py`) and
committing them is part of the change; the sync tripwires fail on drift.

### E. The parity row

```yaml
  - id: subagent-dispatch
    harnesses:
      opencode:
        state: enforced
```

The old `scope_note` goes entirely — it blamed a discriminator that does not
discriminate (§1). `enforced` rather than `partial` because both halves of the surface
work and both now ship: the agent is defined and installed, and the skill dispatches to
it. The per-phase model tiering that OpenCode *cannot* express through the call is
expressed through the agent set instead (§3.C), so there is nothing left for a
`scope_note` to honestly name as missing. The row's summary gains the cost policy, so a
reader learns the default and its price in the same place.

**`fr harness parity --check` is unchanged, and that is deliberate** (decision `d3`).
`check.py` skips every `kind != "hook"` surface and `observe.py` is keyed by shipped
hook *script filename* on purpose — an observer that knew surface ids would have to read
the matrix, and then the two could no longer disagree. `subagent-dispatch` is
declaration-only today, as every interaction row is; re-declaring it makes the check no
less honest than it already is. The mechanical guard this PR adds instead is the
agent-mirror sync tripwire (§3.F), which pins that the artifact exists and matches
canonical. Generalising observation to interaction rows is its own spec.

### F. Tripwires and install wiring

Matching what the three existing categories already have:

- `tests/unit/test_tripwire_opencode_agents_sync.py` — imports
  `find_agents_drift()` from the sync script directly, so the CI gate and `--check`
  cannot disagree about what "in sync" means. Mirrors
  `test_tripwire_opencode_commands_sync.py`.
- `tests/unit/test_install_copies_opencode_agents.py` — mirrors
  `test_install_copies_opencode_{skills,commands}.py`: the agent dir is defined, gated
  on the *same* `OPENCODE_SKILLS_INSTALL` / existing-`~/.config/opencode` opt-in rather
  than a second gate, and removed by `--uninstall`.
- `scripts/install.sh` delivers the agents to `~/.config/opencode/agent/`, after the
  `fr` CLI step, resolving `model:` per §3.C.

### G. Version bump

Touches `plugins/*/skills/**` and `scripts/install.sh`, so a bump is mandatory.
**Minor** — a user-visible workflow addition on a harness that did not have it. Via
`scripts/bump-version.py`; never hand-edit the manifests.

## 4. Risks

- **A shipped agent nobody dispatches to.** The failure this spec exists to prevent, and
  the reason §3.D is not optional polish. Mitigated by the live proof (§5) being a
  *dispatch*, not a registration.
- **Cost surprise.** 7× is a real bill. Mitigated by stating it in the skill and the row
  rather than burying it, so the next person re-opens the decision as a decision.
- **Install ordering.** Moving the OpenCode block after the `fr` CLI install is a real
  behaviour change in a 700-line installer. Mitigated by the install test asserting
  ordering, not just presence.
- **The tier agents multiply.** Four files generated from one canonical source. Mitigated
  by the tier set being closed (`PhaseHeader.tier`) and generated, never authored.

## 5. Test Plan

Live proof, per the #486 precedent: a mocked test cannot show that a subagent was really
spawned, which is the whole claim. Decision `d4` splits it.

**In this PR (automated + one cheap live run):**

1. `opencode agent list`, run against a sandboxed `XDG_CONFIG_HOME` seeded by
   `install.sh`, shows `fr-phase-executor (subagent)` and the three tier agents from the
   shipped mirror.
2. One real `opencode run` against a free model dispatching to the shipped agent,
   evidenced by a row in `opencode.db`'s `session` table with `parent_id` set **and**
   `agent = fr-phase-executor*`. Transcript in the PR body.
3. `fr harness parity --check` passes with the re-declared row.
4. `uv run scripts/sync-opencode.py --check` clean; both sync tripwires green.

**Post-merge, operator-driven (back-loaded `[manual]` phase):**

5. A full `/fr-goal` run on OpenCode against a paid model dispatches at least one phase
   to `fr-phase-executor-<tier>`, with the `opencode.db` row and the child's own token
   counts showing the orchestrator's context did not carry the phase's file reads.
6. `scripts/install.sh` on a machine with `~/.config/opencode` present delivers all four
   agents with `model:` resolved from that operator's own bindings.

## 6. Evidence hygiene

Per `.claude/rules/third-party-privacy.md`: the live-verification transcripts quoted in
this spec, the journal and the PR body carry session ids, token counts and model ids
only. No absolute home paths from `opencode agent list` output (it dumps
`external_directory` permission patterns under the operator's home), and no third-party
hostnames.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-19-opencode-subagent-dispatch | `derio-net/super-fr` | `2026-09-19-opencode-subagent-dispatch` | — |
