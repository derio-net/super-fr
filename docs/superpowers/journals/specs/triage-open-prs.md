# Journal: triage-open-prs

<!-- fr:journal kind=decision scope=spec id=d324bbedbfbe created=2026-09-22T14:58:26 -->
### d324bbedbfbe · decision · Anchor fetch only on file match

Q&A 1 (yes, yes): fetch anchor body at head ref only when PR files contain a spec/journal path; cap 2000 chars; forge error -> unanchored.

<!-- fr:journal kind=decision scope=spec id=466f375d15a2 created=2026-09-22T14:58:26 -->
### 466f375d15a2 · decision · PRs section holds issue-less PRs only

Q&A 2 (sure): Facts.prs = open PRs closing no in-scope issue; linked PRs stay as tags only.

<!-- fr:journal kind=decision scope=spec id=9d62407d5ac5 created=2026-09-22T14:58:27 -->
### 9d62407d5ac5 · decision · Reuse issues map with delivery field

Q&A 3 (yes): Judgement gains optional delivery delivers|partial|drift|unanchored + reason; tier from anchor.

<!-- fr:journal kind=decision scope=spec id=a81cf99b1181 created=2026-09-22T14:58:27 -->
### a81cf99b1181 · decision · Badges, UNKNOWN verbatim, PRs first

Q&A 4 (yes): badges check/merge + collected_at, UNKNOWN shown unknown, PRs section first with unranked, chips for red CI/conflicts, check gains unranked PRs, minor bump.

<!-- fr:journal kind=review scope=spec id=edd47bbe9bdc created=2026-09-22T14:59:21 -->
### edd47bbe9bdc · review · spec-review: Q&A encoded, paths verified

Reviewed spec vs Q&A (all 4 yes encoded: fetch-only-on-match, Facts.prs issue-less only, delivery on Judgement, badges+UNKNOWN+PRs-first) and codebase: fr.gh.list_prs fixed PR_LIST_FIELDS (needs new open-PR call), plan _meta.yaml spec ref verified, journals/specs and journals/debug dirs exist. Acceptance rows triage-open-prs + triage-pr-judgement presented below. No findings; no spec edit needed.
