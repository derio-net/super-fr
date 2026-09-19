# Acceptance checklist — NOT shown to either run

Showing this would hand run B a specification for free. It is the operator's
scoring sheet, written before either run, and both runs are marked against it
identically, from the delivered PR alone.

Score each row pass / fail / partial, for run A and run B.

## Does it do the job

1. `fr journal update --id <id> --state fixed` flips an existing finding
2. …and rewrites **both** the marker and the `[open]` heading tag
3. `fr journal check --scope plan` stops reporting a resolved finding as open
4. `fr journal add --id <existing>` no longer succeeds silently (updates or errors)
5. `fr acceptance set-status --id <id> --status ci` moves an existing row
6. `fr acceptance add-level --id <id> --level unit=…` appends a level
7. Both acceptance verbs regenerate the three committed reports, or fail loudly
8. A down-transition or `failing` without `--note` is refused
9. An unknown `--id` errors clearly instead of creating a row

## Does it hold up

10. Tests cover each verb, including the refusals
11. `uv run pytest -q`, `ruff check`, `mypy` clean
12. Acceptance matrix rows added for the new capability, statuses justified
13. Version bumped; `scripts/bump-version.py --check` passes
14. Skill/rule docs updated **and** mirrors regenerated (sync tripwires green)
15. `fr validate artifacts` and `fr acceptance check` pass
16. PR body explains why, links the issue, closes #429 and #431
17. CI green on the PR

## Artifacts left behind (presence only — this is the comparison, not a pass bar)

18. Spec ·  19. Plan folder ·  20. Run cursor ·  21. Journal (decisions + findings) ·  22. Review findings recorded with state
