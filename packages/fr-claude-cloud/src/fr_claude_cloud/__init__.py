"""claude-cloud adapter — an `fr_dispatch.protocols.Runner` for run-unit work in a
Claude cloud session (spec 2026-10-07-cloud-triage §F, R14, R15).

fr cannot create, message or archive a cloud session itself: only the driver
session's AGENT can, with its session tools. So this runner is a mailbox: every
session action is a request with a stable id, kept pending in the scope's state
(`requests.yaml`) until the agent records its result, and the sessions it recorded
live beside it (`sessions.yaml`). The package registers under `fr.runners` as
`claude-cloud`; `fr` reaches it only through the registry and the structural
`fr.triage.driver.Mailbox` protocol, never by import.
"""

from fr_claude_cloud.runner import ClaudeCloudRunner

__all__ = ["ClaudeCloudRunner"]
