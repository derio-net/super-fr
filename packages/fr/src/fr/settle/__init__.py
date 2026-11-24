"""Draft PRs that settle: wait for mergeability and CI (spec 2026-11-23-pr-readiness-wait).

`fr pr settle` reads a delivered PR's conflict state and CI state, polls the concerns
whose `git.settle` mode is `report` or `fix`, and exits by the `fix` ones. The engine is
pure (`evaluate`), the poll is bounded (`poll`), and a PR the wave driver manages is
exempt (`managed`).
"""
