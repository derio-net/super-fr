# Correction log

Every operator utterance after the seed prompt, both runs. Unlimited, but the
count and the timing are themselves metrics. Timestamps in **UTC**.

| # | timestamp (UTC) | run | prompt (verbatim) | why it was needed | from answers.md? |
|---|---|---|---|---|---|
| 1 | 2026-09-18 10:48 | C | "Yes — append a dated resolution note to the existing finding body; never replace it. The original finding text stays." | Run C asked whether `--note` appends or replaces. **Not covered by answers.md** — an unanticipated question, which is itself a measurement. Answered from the issue's own description of the manual workaround ("appending the resolution to the body"), not from what run A did. Sheet updated to row 9 so it now binds. | no (added as row 9) |
| 2 | 2026-09-18 10:48 | C | "Skip `gh`. Open the PR manually, as the other two runs did." | **Environment defect of ours, not the agent's.** `gh` reads `$XDG_CONFIG_HOME/gh`; none of cfg-A/B/C contains one, so gh was unauthenticated in all three arms — which is why runs A and B also failed to open PRs. Uniform across arms, so it must not count against any of them when scoring row 16. Fixing it for C alone would advantage C. | n/a — environment |
| 3 | 2026-09-18 10:48 | C | "Authorized — implement." | Run C asked permission to proceed after planning. Runs A and B never asked. | n/a |
