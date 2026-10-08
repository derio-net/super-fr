"""A fake `gh` for the `github-rest` tests, answering from captured fixtures.

`tests/fixtures/github_rest/index.json` maps each captured request (the `gh api`
route, prefixed by its `-H` header) to the file holding gh's stdout. The fake
answers a GET for a captured request with that file, raises `GhError` for a
captured failure, and records every argv it is handed so a test can assert the
spelling. Writes are answered by the *writes* map a test passes, or refused.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fr.gh import GhError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "github_rest"
REPO = "derio-net/super-fr"
R = f"repos/{REPO}"
FORBIDDEN_403 = (FIXTURES / "refused" / "pr-list.stderr").read_text()
"""The proxy's real GraphQL refusal (captured), reused as "any 403" in tests."""


def index() -> dict[str, dict[str, Any]]:
    return dict(json.loads((FIXTURES / "index.json").read_text()))


def load(route: str) -> Any:
    """The captured JSON for *route* (a GET)."""
    return json.loads((FIXTURES / index()[route]["file"]).read_text())


def parse_api(argv: list[str]) -> tuple[str, str | None, str, list[str]]:
    """`(method, header, route, field args)` of a `gh api` argv (no leading gh)."""
    assert argv[0] == "api", argv
    rest = argv[1:]
    method, header = "GET", None
    while rest and rest[0] in {"-X", "-H"}:
        if rest[0] == "-X":
            method = rest[1]
        else:
            header = rest[1]
        rest = rest[2:]
    route, fields = rest[0], rest[1:]
    if fields and method == "GET":
        method = "POST"  # what gh does with fields and no -X
    return method, header, route, fields


class FixtureGh:
    """Callable as `RealGhRestClient(run=...)`: argv without `gh` → stdout."""

    def __init__(
        self,
        *,
        writes: dict[tuple[str, str], str] | None = None,
        fail: Callable[[list[str]], GhError | None] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._index = index()
        self._writes = writes or {}
        self._fail = fail

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(list(argv))
        if self._fail is not None and (exc := self._fail(argv)) is not None:
            raise exc
        method, header, route, _fields = parse_api(argv)
        if method != "GET":
            if (method, route) in self._writes:
                return self._writes[(method, route)]
            raise AssertionError(f"unexpected write {method} {route}")
        key = f"{header} {route}" if header else route
        entry = self._index.get(key)
        if entry is None:
            raise AssertionError(f"no captured fixture for {key!r}")
        body = (FIXTURES / entry["file"]).read_text()
        if entry.get("error"):
            err = json.loads(body)
            raise GhError(
                err["stderr"].strip(),
                stderr=err["stderr"],
                returncode=err["exit"],
                stdout=err["stdout"],
            )
        return body.strip()

    def routes(self) -> list[str]:
        return [parse_api(a)[2] for a in self.calls]


def forbidden(argv: list[str]) -> GhError:
    """The captured proxy refusal as gh raises it, for any argv."""
    return GhError(FORBIDDEN_403.strip(), stderr=FORBIDDEN_403, returncode=1)
