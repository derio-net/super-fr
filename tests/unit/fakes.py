"""In-memory fake GhClient for unit tests.

Records every mutation as a list of `("method", kwargs_dict)` tuples
(via `.calls`). Initial Issue/PR state can be pre-loaded via the
constructor. Errors can be configured to fire on the Nth mutation
to test failure-accumulation behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeIssue:
    number: int
    state: str = "OPEN"
    labels: set[str] = field(default_factory=set)
    assignees: tuple[str, ...] = ()
    body: str = ""
    linked_prs: list[dict] = field(default_factory=list)


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
        self.calls: list[tuple[str, dict]] = []
        self._next_issue_number: dict[str, int] = {}
        # Fail on Nth mutation: index of mutation to fail at (0-based)
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
        linked_prs: list[dict] | None = None,
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

    def view_issue(self, repo: str, number: int) -> dict:
        i = self.issues[(repo, number)]
        return {
            "state": i.state,
            "labels": sorted(i.labels),
            "assignees": list(i.assignees),
            "body": i.body,
        }

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict]:
        i = self.issues.get((repo, issue_number))
        if i is None:
            return []
        return list(i.linked_prs)

    def view_pr(self, repo: str, number: int) -> dict:
        # Look across all issues for a linked_pr matching the PR number
        for issue in self.issues.values():
            for pr in issue.linked_prs:
                if pr.get("number") == number:
                    return dict(pr)
        raise FakeGhError(f"PR {repo}#{number} not found")

    # ---- mutation methods ----

    def _mutate_or_fail(self) -> None:
        n = len(self.calls) - 1  # this call is already appended
        if self.fail_on_mutation is not None and n == self.fail_on_mutation:
            raise FakeGhError(f"configured failure on mutation {n}")

    def edit_issue_labels(
        self,
        repo: str,
        number: int,
        *,
        add: frozenset[str],
        remove: frozenset[str],
    ) -> None:
        self.calls.append(
            ("edit_issue_labels", {"repo": repo, "number": number, "add": add, "remove": remove})
        )
        self._mutate_or_fail()
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
        self.calls.append(
            ("edit_issue_state", {"repo": repo, "number": number, "state": state, "reason": reason})
        )
        self._mutate_or_fail()
        self.issues[(repo, number)].state = state

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        self.calls.append(("edit_issue_body", {"repo": repo, "number": number, "body": body}))
        self._mutate_or_fail()
        self.issues[(repo, number)].body = body

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        self.calls.append(
            ("create_issue", {"repo": repo, "title": title, "body": body, "labels": labels})
        )
        self._mutate_or_fail()
        n = self._next_issue_number.get(repo, 1)
        self._next_issue_number[repo] = n + 1
        self.issues[(repo, n)] = FakeIssue(number=n, body=body, labels=set(labels))
        return f"https://github.com/{repo}/issues/{n}"

    def ensure_labels(self, repo: str, labels: list) -> None:
        self.calls.append(("ensure_labels", {"repo": repo, "labels": list(labels)}))
        self._mutate_or_fail()
        bag = self.repo_labels.setdefault(repo, set())
        for lbl in labels:
            name = lbl if isinstance(lbl, str) else lbl.name
            bag.add(name)
