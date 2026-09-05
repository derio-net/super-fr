"""Tracker seam — protocol defined, no adapter built (spec §4.G, Phase 10).

`fr.tracker.model` — the `Tracker` Protocol, the `<tracker> -> <instance> ->
    <ItemState> -> mapping|null` config loader, and repo>user resolution
    (mirrors `fr.models`).
`fr.tracker.github` — `GithubTracker`, built from today's label behavior
    (`fr.item_state`), the one concrete implementation this phase ships.

No Jira adapter exists yet. Per-project workflows rule out a per-tracker-
*type* mapping (two Jira projects on the same server can expose different
transitions), so the mapping is per tracker *instance* — a GitHub repo, a
Jira project — resolved repo-over-user like `fr models`.
"""

from __future__ import annotations
