# ci_budget fixtures — captured, never constructed

Captured live on **2026-09-26** against `derio-net/super-fr` with exactly these
commands (REST shape — snake_case `started_at`/`completed_at` — because
`scripts/ci_budget.py` calls `gh api`, not `gh run view --json jobs`, which
returns camelCase instead):

```bash
gh api repos/derio-net/super-fr/actions/runs/<id>
gh api repos/derio-net/super-fr/actions/runs/<id>/jobs
```

Two runs, four files:

- `run_pre_sharding.json` / `jobs_pre_sharding.json` — run **36242091779**, a
  pre-sharding `CI` push run on `main` (single `test` job, ~7 minutes): the
  "over budget" case.
- `run_sharded.json` / `jobs_sharded.json` — run **36247922786**, this branch's
  own sharded `CI` push run (4 `test (k)` shards + `coverage`), 155s wall
  clock. This run also carries the skipped-job case: `change-fragment` is
  `skipped` (a push, not a PR) but GitHub still stamps it —
  `started_at: 2026-09-26T14:16:03Z`, `completed_at: 2026-09-26T14:16:02Z`
  (completed *before* it started, since the timestamps are the workflow's
  overall skip window, not real work). `wall_clock` must exclude it by
  `conclusion == "skipped"`, not by null timestamps: including it would pull
  the window's start back 2 seconds, from 155s to 157s (verified against these
  exact fixtures at capture time).

**Trimmed, never composed.** Each run file keeps only the fields the script
reads: `id`, `name`, `path`, `event`, `head_branch`, `head_sha`, `conclusion`,
`html_url`. Each jobs file keeps only `jobs[].name` / `started_at` /
`completed_at` / `conclusion`. No value was altered; only fields were dropped,
and the JSON was re-serialised with two-space indentation (whitespace only).

derio-net data (this repo's own CI runs) — no third-party redaction applies
(`.claude/rules/third-party-privacy.md`).
