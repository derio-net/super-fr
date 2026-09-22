# Triage fixtures — captured, never constructed

Captured live on **2026-09-21** from the worktree, against `derio-net/super-fr`,
with exactly these two commands:

```bash
gh issue list --repo derio-net/super-fr --state open --limit 1000 \
  --json number,title,labels,createdAt,updatedAt,url,body
gh pr list --repo derio-net/super-fr --state all --limit 200 \
  --json number,title,state,isDraft,mergedAt,url,headRefName,closingIssuesReferences
gh pr list --repo derio-net/super-fr --state open --limit 1 \
  --json number,title,state,isDraft,mergedAt,url,headRefName,closingIssuesReferences,files,statusCheckRollup,mergeable,mergeStateStatus,reviewDecision
```

- `super-fr-issues.json` — output of the first command (38 open issues at capture).
- `super-fr-prs.json` — output of the second command (200 PRs at capture).
- `super-fr-open-prs.json` — output of the third command, captured live on
  **2026-09-22** (one open PR, whole record): the open-PR call's extra fields
  (`files`, `statusCheckRollup`, `mergeable`, `mergeStateStatus`,
  `reviewDecision`). The captured PR reads `mergeable: CONFLICTING`,
  `mergeStateStatus: DIRTY` — a real conflict, not constructed — and an empty
  `reviewDecision` (no review). The earlier `UNKNOWN` case (GitHub computes
  these lazily after a push) is covered by unit inline fixtures instead.

**Subset, never edited.** Each file keeps a subset of the captured records to stay
small — whole records only, in the order `gh` returned them. No field inside any
record was changed. The files were re-serialised with two-space indentation, which
changes whitespace only. The subset keeps, at least:

- open, draft, closed and merged PRs;
- PRs whose `closingIssuesReferences` is non-empty, including several naming the
  same issues (the issue -> PRs inversion's many-to-many case);
- every open issue those PRs reference, plus every labelled open issue.

**Privacy.** `derio-net/super-fr` is public and owned by the `derio-net` org, so
nothing here is third-party under `.claude/rules/third-party-privacy.md`, and
nothing was redacted.

To refresh: re-run the commands, subset whole records again, and update the
date above. Never hand-edit a record to fit a test.
