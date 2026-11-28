from __future__ import annotations

import pytest
from fr.debt.model import SourceStatus
from fr.debt.render import source_category


def test_oversize_bodies_and_payloads_yield_no_figures() -> None:
    import base64
    import json

    from fr.debt.render import FIGURES_PREFIX, parse_figures

    def block(raw: bytes) -> str:
        return f"{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->"

    ok = block(json.dumps({"owed": 1, "acceptance": {"ci": 2}}).encode())
    assert parse_figures(ok) == {"owed": 1, "acceptance": {"ci": 2}}
    assert parse_figures(ok + " " * 70000) is None  # body past 64 KiB
    assert (
        parse_figures(block(json.dumps({"x": "y" * 9000}).encode())) is None
    )  # payload past 8 KiB
    for hostile in ({"a": [1]}, {"a": {"b": {"c": 1}}}, {"a": "z" * 500}, [1], {"a": {"b": [1]}}):
        assert parse_figures(block(json.dumps(hostile).encode())) is None


# ── an unsupported forge operation is named, not a "forge error" (2026-11-28 R7) ──


def _forge_why(exc: Exception) -> SourceStatus:
    """Built exactly as `fr.debt.engine.compute` builds it."""
    return SourceStatus(state="unavailable", why=f"{type(exc).__name__}: {exc}")


def test_an_unsupported_operation_names_the_backend_and_the_tracking_issue() -> None:
    from fr.ghclient import UnsupportedForgeOperation

    st = _forge_why(UnsupportedForgeOperation("list_issues", "gitea"))
    assert source_category("forge", st) == "not supported on gitea (gh#611)"
    st = _forge_why(UnsupportedForgeOperation("list_issues", "gitea", "derio-net/super-fr#611"))
    assert source_category("forge", st) == "not supported on gitea (derio-net/super-fr#611)"


@pytest.mark.parametrize(
    ("backend", "tracked_by"),
    [
        ("Gitea Prod!", "gh#611"),
        ("gitea", "see https://x.invalid"),
        ("gitea\n", "gh#611"),  # review p1-r2: a trailing newline is not fixed-shape
        ("gitea", "gh#611\n"),
    ],
)
def test_a_token_that_is_not_fixed_shape_never_reaches_the_category(
    backend: str, tracked_by: str
) -> None:
    from fr.ghclient import UnsupportedForgeOperation

    st = _forge_why(UnsupportedForgeOperation("list_issues", backend, tracked_by))
    assert source_category("forge", st) == "not supported by this forge"


def test_any_other_forge_failure_stays_a_forge_error() -> None:
    assert source_category("forge", SourceStatus(state="unavailable", why="GhError: boom")) == (
        "forge error"
    )
