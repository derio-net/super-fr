# Fix #505: distinguish absent OpenCode agents from idempotent apply

`materialize_agents` now reports the number of supported-tier OpenCode agent files it considered, separately from changed files. `fr models apply --harness opencode` says no files were found only when none match; otherwise it reports `<n> agent files already up to date`. Includes regressions for both branches and patch bump 4.22.0 → 4.22.1.

- Issue: https://github.com/derio-net/super-fr/issues/505
- Spec: `docs/superpowers/specs/2026-09-26-models-opencode-noop-report-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-models-opencode-noop-report`

## Operator decisions

- Count only discovered OpenCode agent files with a supported tier suffix; exclude unrelated files.
- Focused models command/tests are sufficient post-merge verification.

## Operator gates

- Brainstorm Q&A answered by operator. OpenCode cannot verify answer provenance from a session transcript.

## Manual phases

None.

## Test Plan

Post-merge, run the focused models command/tests against the merged branch.

## Acceptance debt

- `fr acceptance status --brief`: 205 ci, 23 skipped, 9 not-implemented, 1 scheduled (unchanged repo-wide debt).
- `fr acceptance check --added-since origin/main`: no acceptance rows added.

## Ready checklist

- [ ] CI green
- [ ] Explicit review approved
- [ ] No commits since review approval

<!-- rendered by fr for run 2026-09-26-fix-models-opencode-noop-505; edit above this line only -->

## Findings

- `review-cli-count-fixture` (plan, phase 1) — CLI no-op test must seed existing agent files — **fixed**

## Out-of-scope findings

None.

## Proportionality

```text
proportionality: merge-base 6a7da3568f8c79b44a294f74a9e98ccf4db80155

## Unreferenced new files

none.

## Out-of-plan touches

- .claude-plugin/marketplace.json

## Size

202 lines changed (+160 -42; fr artifacts excluded) against an estimate of 220 (0.9×).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | — | — |
| spec-review | — | — |
| plan | — | — |
| plan-review | — | — |
| implement | — | — |
| journal-check | — | — |
| deliver | — | — |
| **total** | | — |

Sessions: 0 read, 0 unavailable.

_Read from this host's transcripts; the usage file is written by this resolve._
