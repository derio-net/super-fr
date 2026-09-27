# Container git ownership — plan

One agentic phase (a single bug, tightly coupled). Debugging-first: task 1
reproduces the dubious-ownership refusal from a linked worktree, and from a
subdirectory, before any fix. Task 2 adds `fr.git.safe_directory_args` (walk up
to the enclosing repo, realpath) and applies it to every git call on the
record-commit path. Task 3 makes new containers correct from the start
(`POST_CREATE` trusts `$PWD`) and regenerates both committed profiles.
Task 4 closes the acceptance rows and the change fragment. Spec:
`docs/superpowers/specs/2026-09-26-container-git-ownership-design.md`.
No phase names a member issue as `tracking_issue`.
