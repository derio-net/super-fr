"""In-memory fake GhClient for unit tests.

Records each successful mutation as a `("method", kwargs_dict)` tuple
in `.calls`. Failed mutations are NOT recorded — they're tracked
separately on `.attempted_mutations` so tests asserting on `.calls`
see only what actually happened.

Errors can be configured to fire on the Nth attempted mutation
(0-indexed) via `fail_on_mutation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeIssue:
    number: int
    state: str = "OPEN"
    labels: set[str] = field(default_factory=set)
    assignees: tuple[str, ...] = ()
    body: str = ""
    linked_prs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FakeGhError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class FakeGhClient:
    """Test double for `GhClient`."""

    def __init__(self) -> None:
        self.issues: dict[tuple[str, int], FakeIssue] = {}
        self.repo_labels: dict[str, set[str]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.attempted_mutations: int = 0
        self._next_issue_number: dict[str, int] = {}
        # Fail on Nth attempted mutation (0-indexed). The mutation is NOT
        # recorded in .calls when it fails.
        self.fail_on_mutation: int | None = None

    # ---- preload helpers (test setup) ----

    def add_issue(
        self,
        repo: str,
        number: int,
        *,
        state: str = "OPEN",
        labels: set[str] | None = None,
        assignees: tuple[str, ...] = (),
        body: str = "",
        linked_prs: list[dict[str, Any]] | None = None,
    ) -> FakeIssue:
        issue = FakeIssue(
            number=number,
            state=state,
            labels=set(labels or set()),
            assignees=assignees,
            body=body,
            linked_prs=list(linked_prs or []),
        )
        self.issues[(repo, number)] = issue
        return issue

    # ---- read methods ----

    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        i = self.issues[(repo, number)]
        return {
            "state": i.state,
            "labels": sorted(i.labels),
            "assignees": list(i.assignees),
            "body": i.body,
        }

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        i = self.issues.get((repo, issue_number))
        if i is None:
            return []
        return list(i.linked_prs)

    # ---- mutation methods ----

    def _gate(self) -> None:
        """Increment the attempt counter; raise if this attempt is configured to fail."""
        idx = self.attempted_mutations
        self.attempted_mutations += 1
        if self.fail_on_mutation is not None and idx == self.fail_on_mutation:
            raise FakeGhError(f"configured failure on mutation {idx}")

    def edit_issue_labels(
        self,
        repo: str,
        number: int,
        *,
        add: frozenset[str],
        remove: frozenset[str],
    ) -> None:
        self._gate()
        unknown = set(add or set()) - self.repo_labels.get(repo, set())
        if unknown:
            raise FakeGhError(f"label not found on {repo}: {sorted(unknown)}")
        self.calls.append(
            ("edit_issue_labels", {"repo": repo, "number": number, "add": add, "remove": remove})
        )
        i = self.issues[(repo, number)]
        i.labels = (i.labels | set(add)) - set(remove)

    def edit_issue_state(
        self,
        repo: str,
        number: int,
        *,
        state: str,
        reason: str | None = None,
    ) -> None:
        self._gate()
        self.calls.append(
            ("edit_issue_state", {"repo": repo, "number": number, "state": state, "reason": reason})
        )
        self.issues[(repo, number)].state = state

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        self._gate()
        self.calls.append(("edit_issue_body", {"repo": repo, "number": number, "body": body}))
        self.issues[(repo, number)].body = body

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        self._gate()
        unknown = set(labels or set()) - self.repo_labels.get(repo, set())
        if unknown:
            raise FakeGhError(f"label not found on {repo}: {sorted(unknown)}")
        self.calls.append(
            ("create_issue", {"repo": repo, "title": title, "body": body, "labels": labels})
        )
        n = self._next_issue_number.get(repo, 1)
        self._next_issue_number[repo] = n + 1
        self.issues[(repo, n)] = FakeIssue(number=n, body=body, labels=set(labels))
        return f"https://github.com/{repo}/issues/{n}"

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        self._gate()
        self.calls.append(("ensure_labels", {"repo": repo, "labels": list(labels)}))
        bag = self.repo_labels.setdefault(repo, set())
        for lbl in labels:
            name = lbl if isinstance(lbl, str) else lbl.name
            bag.add(name)


class FakeMcpClient:
    """In-memory fake of `vk._mcp_client.VkMcpClient` for unit tests.

    Records every call as a `("method", kwargs_dict)` tuple in `.calls`
    so tests can assert on call sequence and payload shape. Failure
    injection mirrors `FakeGhClient.fail_on_mutation`: pass
    `fail_on_call=N` to make the (0-indexed) Nth call raise.

    The surface deliberately matches the calling convention
    `vk.bridge.dispatch.dispatch_phase` uses against the real client —
    keyword-only on the methods where the wire payload is structured.
    """

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail_on = fail_on_call
        self._next_card_id = 0
        self._next_ws_id = 0
        self.issues: dict[str, dict[str, Any]] = {}
        self.workspaces: dict[str, dict[str, Any]] = {}

    def _record(self, name: str, args: dict[str, Any]) -> None:
        # 0-indexed counter to match FakeGhClient.fail_on_mutation.
        idx = len(self.calls)
        self.calls.append((name, args))
        if self._fail_on is not None and idx == self._fail_on:
            raise Exception("injected MCP failure")

    def create_issue(self, *, title: str, description: str = "", **kw: Any) -> dict[str, Any]:
        self._record("create_issue", {"title": title, "description": description, **kw})
        self._next_card_id += 1
        cid = f"card-{self._next_card_id}"
        self.issues[cid] = {"id": cid, "title": title, "description": description, "status": "Todo"}
        return self.issues[cid]

    def update_issue(self, card_id: str, **changes: Any) -> dict[str, Any]:
        self._record("update_issue", {"card_id": card_id, **changes})
        self.issues.setdefault(card_id, {"id": card_id}).update(changes)
        return self.issues[card_id]

    def get_issue(self, card_id: str) -> dict[str, Any] | None:
        self._record("get_issue", {"card_id": card_id})
        return self.issues.get(card_id)

    def list_issues(self, **kw: Any) -> list[dict[str, Any]]:
        self._record("list_issues", {**kw})
        return list(self.issues.values())

    def start_workspace(
        self,
        *,
        name: str,
        repo: str,
        executor: str,
        branch: str,
        **kw: Any,
    ) -> dict[str, Any]:
        self._record(
            "start_workspace",
            {"name": name, "repo": repo, "executor": executor, "branch": branch, **kw},
        )
        self._next_ws_id += 1
        wid = f"ws-{self._next_ws_id}"
        self.workspaces[wid] = {
            "id": wid,
            "name": name,
            "repo": repo,
            "executor": executor,
            "branch": branch,
            "archived": False,
            "linked_issue": None,
        }
        return self.workspaces[wid]

    def update_workspace(self, ws_id: str, **changes: Any) -> dict[str, Any]:
        self._record("update_workspace", {"ws_id": ws_id, **changes})
        self.workspaces.setdefault(ws_id, {"id": ws_id}).update(changes)
        return self.workspaces[ws_id]

    def list_workspaces(self, **kw: Any) -> list[dict[str, Any]]:
        self._record("list_workspaces", {**kw})
        return list(self.workspaces.values())

    def list_repos(self) -> list[dict[str, str]]:
        self._record("list_repos", {})
        return [
            {"name": "derio-net/frank"},
            {"name": "derio-net/willikins"},
            {"name": "derio-net/superpowers-for-vk"},
        ]

    def link_workspace_issue(self, ws_id: str, card_id: str) -> None:
        self._record("link_workspace_issue", {"ws_id": ws_id, "card_id": card_id})
        if ws_id in self.workspaces:
            self.workspaces[ws_id]["linked_issue"] = card_id

    def close(self) -> None:
        self._record("close", {})
