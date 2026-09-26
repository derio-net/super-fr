<!-- rendered by fr for run 2026-09-26-feat-batch-tests-window; edit above this line only -->

## Findings

- `s1` (spec) — Record shapes unpinned; ack/notification content shapes under-specified — **fixed**
- `s3` (spec) — attribute_dispatches keying reference is wrong — **fixed**
- `s4` (spec) — §3.B edge cases missing from Test Plan — **fixed**
- `s5` (spec) — §2 'captured' shapes were hand-built, not captured (Opus re-review) — **fixed**
- `s6` (spec) — Timeout-moved foreground Bash replies with different ack text (Opus) — **fixed**
- `s7` (spec) — Notification timestamp is when recorded, not when finished; wait/retry undocumented (Opus) — **fixed**
- `s8` (spec) — §3.B assignment grammar differs from the implemented one (Opus) — **fixed**
- `r1` (plan, phase 1) — No end-to-end test through _verify_tests_log for the background case — **fixed**
- `r2` (plan, phase 1) — Vacuous variable case '/y/$L' expected False for the wrong reason — **fixed**
- `r3` (plan, phase 1) — Refusal variants covered only for string content; is_error ack untested — **fixed**
- `r4` (plan, phase 1) — Exit-code regex scanned the whole notification, spec says the summary — **fixed**
- `o1` (plan, phase 1) — F1 queued-attachment task-notification shape never seen (Opus code review) — **fixed**
- `o2` (plan, phase 1) — F2 timeout-moved foreground command not recognised as background (Opus) — **fixed**
- `o3` (plan, phase 1) — F3 assignment scan resolves variables the shell would not (Opus) — **fixed**
- `o4` (plan, phase 1) — F4 quadratic _NOTIFIED_STATUS regex (Opus) — **fixed**
- `o5` (plan, phase 1) — F5 exit code taken from model-written summary text (Opus) — **fixed**
- `o6` (plan, phase 1) — F7 test gaps, weak assertion, fixtures not captured (Opus) — **fixed**
- `o7` (plan, phase 1) — F8/F9 stale docstring; a background window can span the whole run (Opus) — **fixed**

## Out-of-scope findings

- `s2` (spec) — OpenCode & detach has the same zero-length-window bug; spec said unchanged — **out-of-scope**
- `r5` (plan, phase 1) — _ASSIGNMENT is purely syntactic (echo L=..., env-prefix, subshell can resolve) — **out-of-scope**
- `r6` (plan, phase 1) — OpenCode & detach still has a zero-length window — **out-of-scope**
- `o8` (plan, phase 1) — F10 OpenCode & detach zero-length window (Opus) — **out-of-scope**

## Proportionality

```text
proportionality: merge-base 89aec6f18e76c7511a818b2393cfbc6d52aa81a3

## Unreferenced new files

- .changes/feat-batch-tests-window.yaml

## Out-of-plan touches

- tests/fixtures/transcripts/claude-code-background.jsonl
- tests/fixtures/transcripts/claude-code-session.NOTE.md

## Size

602 lines changed (+598 -4; fr artifacts excluded) against an estimate of 350 (1.7×).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 15 | — |
| spec-review | — | — |
| plan | — | — |
| plan-review | — | — |
| implement | — | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 2 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.
