# Simplified Technical English output tone — plan

Spec: `docs/superpowers/specs/2026-09-14-ste-output-tone-design.md`.

## Goal

Make agent replies and skill-prescribed text use Simplified Technical English
(ASD-STE100 principles, no dictionary). Two carriers deliver one shared text:
a forced plugin output style (Claude Code main thread) and a shipped rule
(subagents, OpenCode, Hermes).

## Phases

1. **Walking skeleton.** Create the output style file with its frontmatter and
   the `ste-shared` markers, and one test that pins them. Proves that the new
   `plugins/super-fr/output-styles/` directory passes every existing gate.
2. **Shared text.** Write the full STE text (spec §5.A) inside the markers.
   Tests pin the section headings, the Insight-block override, and the
   filler-word self-check.
3. **Rule carrier and wiring.** Create `rules/ste-output-tone.md` with an
   identical marked block. Wire it into `install.sh` (install and uninstall),
   the OpenCode mirror, the Hermes block, and `AGENTS.md`. A test pins the
   identity of the two blocks.
4. **Phase executor, release, acceptance.** Add the STE line to
   `fr-phase-executor.md`, bump the minor version, move the acceptance rows,
   and run the full CI gate.

No manual phase: the only operator work is the post-merge Test Plan (spec §7),
which goes in the PR body.

## Revision 2026-09-15 — chattiness first (spec d6–d10)

Phases 1–4 shipped a forced style and a global rule. Review showed that this
reached every session and stayed non-deterministic. The spec now starts from
the chattiness problem. Phases 5–8 change the plan in the same branch:

5. **Repurpose.** Make the STE style opt-in. Remove the rule, its wiring and
   the phase-executor line.
6. **Prose lint module.** `fr.prose_lint`: long sentences and filler words,
   with the filler list pinned to the style text.
7. **Wire the lint.** `fr journal add` and `fr plan self-review` print
   warnings. No exit code changes.
8. **Skill audit and acceptance.** The fr-goal and fr-debugging reporting
   contract, row tables in fr-brainstorming and fr-acceptance, the acceptance
   rows, and the gate.

## Conventions for every phase

- Run all commands in the workspace with `fr isolation exec --repo
  /Users/derio/Docs/projects/DERIO_NET/super-fr --branch feat/ste-output-tone -- <cmd>`,
  or from the worktree cwd.
- The shared text must itself follow STE: sentences of 25 words or fewer,
  active voice, no filler.
- Do not copy ASD-STE100 rule text or dictionary entries (licence, spec d5).
