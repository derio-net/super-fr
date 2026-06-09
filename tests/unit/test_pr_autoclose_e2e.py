"""End-to-end regression guard for #290.

The whole point of the fix: a dispatch PR that merges WITHOUT a `Closes #N`
keyword must STILL close its tracking GH Issue — via the bridge's observer →
pr_state sweep, not GitHub's native closing-reference. This test wires the
real `observe_pr_status` to the real `pr_state.tick` (only the gh boundary —
PR-status fetch + issue-close — is faked) and asserts the Issue closes.

If this passes while the dispatched PR body contains no closing keyword, the
auto-close no longer depends on the keyword.
"""

from __future__ import annotations

from fr_vk.pr_observe import observe_pr_status
from fr_vk.pr_state import tick

from tests.unit.fakes import FakeMcpClient


def test_merged_pr_without_closes_keyword_still_closes_issue():
    mcp = FakeMcpClient()
    # A dispatched card whose PR merged. The PR body has NO `Closes #N` — but
    # that never enters this flow; the merge is observed via the card's
    # latest_pr_url and the Issue number via the card title (`gh#7`).
    mcp.issues["card-1"] = {
        "id": "card-1",
        "simple_id": "7",
        "status": "In review",
        "title": "gh#7: [derio-net/runs-fr]",
        "latest_pr_url": "https://github.com/derio-net/runs-fr/pull/14",
    }
    mcp.workspaces["ws-1"] = {"id": "ws-1", "name": "7 -> gh#7", "pinned": False, "archived": False}

    # Fake only the gh boundary: PR #14 is merged.
    pr_status = {"https://github.com/derio-net/runs-fr/pull/14": "merged"}
    closed: list[tuple[str, str]] = []

    # 1. observe → real observer builds the {card: status} map.
    observations = observe_pr_status(mcp, pr_status_fetch=lambda url: pr_status.get(url))
    assert observations == {"card-1": "merged"}

    # 2. tick → real sweep transitions the card AND closes the Issue.
    count = tick(mcp, observations, close_gh_issue=lambda repo, n: closed.append((repo, n)))

    assert count == 1
    update_issues = [c for c in mcp.calls if c[0] == "update_issue"]
    assert update_issues[0][1]["status"] == "Done"
    # The Issue was closed by the bridge — not by a PR closing-keyword.
    assert closed == [("derio-net/runs-fr", "7")]
    # Workspace archived in the cascade.
    update_ws = [c for c in mcp.calls if c[0] == "update_workspace"]
    assert update_ws and update_ws[0][1]["archived"] is True
