# Acceptance checklist — NOT shown to either run

Scored by the operator from the delivered PR alone, identically for both arms.

## Does it do the job
1. A framework-class file the consumer modified is **not silently replaced** by `/update`
2. The run reports which files diverged, by path
3. One mechanism works end to end on a real consumer-shaped fixture
4. A divergence that would have been erased makes the command exit non-zero
5. Running `/update` twice in a row is stable (no oscillation, no repeated conflict)
6. Detection reuses the existing `blog_craft_version` base rather than inventing a second one

## Does it hold up
7. Existing update/ownership tests still pass (5 test files)
8. New tests cover the new state, including the erase-would-have-happened case
9. `tests/run-unit.sh` and the update smoke test pass
10. Docs/manifest updated where ownership classes are documented
11. Version bumped per blog-craft's convention
12. PR body explains the model and links #88
13. CI green

## Artifacts left behind (presence only — this is the comparison, not a pass bar)
14. Spec · 15. Plan · 16. Run cursor · 17. Journal (decisions + findings) · 18. Review findings with state
