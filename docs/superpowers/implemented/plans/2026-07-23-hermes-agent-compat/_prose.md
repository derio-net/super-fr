# Hermes Agent compatibility — implementation plan

Spec: `docs/superpowers/specs/2026-07-23-hermes-agent-compat-design.md`

Make super-fr a first-class citizen of a **third agent harness** — Hermes Agent
by Nous Research — parallel to Claude Code and OpenCode. This plan ports super-fr's
three delivery channels (skills, rules, enforcement) plus autonomous `fr-goal`
execution into Hermes, following the existing OpenCode track as its template.

## Why this shape

Hermes's extension model maps cleanly onto what super-fr already ships:

- **Skills** are plain `SKILL.md` under `~/.hermes/skills/<category>/<name>/` with
  `name`/`description` frontmatter — the *same* format super-fr already writes, so
  delivery is a byte-copy under a `fr` category (P1), exactly like OpenCode.
- **Rules** have no `instructions`-array analog; the only always-on global surface
  is `~/.hermes/SOUL.md`. The three *shipped* plugin rules go into a delimited,
  reversible managed block (P2 assembles it; P5 installs it). The repo-local
  `acceptance-matrix` rule is maintainer-only and is deliberately **excluded** from
  the consumer block.
- **Enforcement** is the load-bearing win. Hermes's shell-hooks bridge speaks the
  Claude `{"decision":"block"}` protocol *and* fires on bash-equivalents
  (`terminal`/`execute_code`), so we **reuse the existing shell scripts** via a
  per-harness I/O adapter — no new package — and close the bash gap OpenCode leaves
  open (P3 edits, P4 bash/push). A shared decision core (P3) DRYs the two shell
  implementations and makes the guard logic unit-tested code, not prose.

## Key design decisions (from the spec journal)

- **Invasive install mutations live in a tested `fr hermes` subcommand** (P5), not
  bash: install.sh is jq-only and cannot merge YAML into the shared `cli-config.yaml`.
  The subcommand (reusing fr's `yaml` dep) does the idempotent, reversible hooks
  merge, allowlist edit, and SOUL.md block — install.sh just copies skills and calls it.
- **`fr-goal` runs autonomously inside Hermes** (P7) via `delegate_task`, whose
  "subagents know nothing" contract already matches fr-goal's journal-fed handoff.
  The `fr-goal` SKILL.md is at its 120-line cap, so the Hermes branch must be added
  by compressing existing prose — if it cannot fit, stop and record a finding.

## Phase map

1. **Skills mirror** — `scripts/sync-hermes.py` byte-copies skills to
   `.hermes/skills/fr/`; tripwire guards drift.
2. **Rules block** — same generator assembles the 3 shipped rules into
   `.hermes/SOUL.d/super-fr-rules.md` between managed markers.
3. **Edit enforcement** — extract a shared `lib/fr-isolation-decision.sh` (Claude
   behavior unchanged), add the Hermes `pre_tool_call` edit entrypoint.
4. **Bash/push enforcement** — port `fr-isolation-guard` + `fr-merged-pr-push-guard`
   to Hermes `terminal`/`execute_code` hooks.
5. **Config + `fr hermes` subcommand** — `cli-config.snippet.yaml` (hooks-sync
   tripwire) and the tested install/uninstall subcommand doing all invasive mutations.
6. **install.sh + model defaults** — opt-in Hermes install block calling
   `fr hermes install`; ship `hermes:` fr-models tier defaults with a resolve test.
7. **fr-goal delegation** — harness-aware phase dispatch (`delegate_task`), staying
   at the SKILL.md line cap, re-synced.
8. **[manual] post-merge verification** — install into a real Hermes Agent and walk
   the spec Test Plan (skills load, edit+bash gate, session nag, autonomous run,
   clean uninstall). Back-loaded; no dependent agentic phase — the operator pushes
   results to the PR.

## Testing posture

Every agentic phase is red→green TDD. Sync channels get import-the-generator
tripwires (CI + `--check` can't disagree). Enforcement gets subprocess-driven unit
tests over recorded Hermes stdin payloads, asserting allow/deny **and** the correct
per-harness deny JSON. The `fr hermes` subcommand gets temp-`HERMES_HOME` tests for
idempotence and reversibility. No new CI job (no TS package) — everything rides the
existing `test` job.
