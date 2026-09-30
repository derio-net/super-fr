# The spec is the contract — implementation plan

Spec: `docs/superpowers/specs/2026-09-29-spec-is-the-contract-design.md`. Built by hand in the
`feat/spec-is-the-contract` fr-isolation workspace, not by an fr-goal run: today's fr-goal would push
this change's own spec through the gates it removes.

## Shape

Two agentic phases, one per reviewable ask:

1. **Engine** (tier `hard`, walking skeleton). The four derived gates leave the workflows and
   `run_cmd.py`; `requirements.py` becomes a plain-list parser that also reads the old table;
   briefs and `journal handoff` stop carrying operator input; `delegated` and `unconfirmed` go, with
   the record kind moving 6 -> 7 through a frozen `RecordV6`; the PR body loses its input sections.
   It advances `spec-contract-no-input-gates`, `spec-contract-plain-requirements` and
   `spec-contract-record-v7`.
2. **Prose, agents, matrix and delivery** (tier `standard`). Skills and agents return to their
   4.28.0 wording at the input boundary; `fr-phase-reviewer` is deleted with everything that exists
   only for it; `AGENTS.md` gains the one-sentence principle; mirrors and the explainer are
   regenerated; about 17 input-layer matrix rows are deleted by hand and the rest reworded; then the
   full gate, an independent review and a draft PR.

## Reference points

- **Stable wording:** `git show v4.28.0:<path>` for every prose section being restored.
- **Keep:** phase sizing (#792, #834), the light path (#820), UI evidence (#789), close-out
  (#790, #836), services (#794), tier criteria (#834), question rounds (#767, #784), `Row.verify`.
- **Order:** #828 (`deliver-handoff`) merges first; this branch rebases onto it before the PR.

## Post-merge

Test Plan item 7, the dry run of super-fr-3's feature C on 5.0.0, is owed to the operator
(`spec-contract-dry-run`, `verify: post-merge`). Closing the issues this makes moot, and re-scoping
#823, happen with the operator afterwards.
