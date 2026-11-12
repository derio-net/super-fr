"""R10 (spec 2026-11-04-repo-feature-settings): under `forge.pr_body: minimal` the live PR
carries a plain summary and no fr marker, the full render is kept durable at
`docs/superpowers/runs/<run-id>.pr-body.md` and committed with the deliver resolve, and
`deliver` still refuses a shared closing keyword and any fr marker in the live body.

End to end, through `fr run resolve --step deliver` on a real run: the policy is landed
on the origin's default branch, where R2 reads it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_deliver_pr_body import RUN, _at_deliver, _body, _deliver, live

__all__ = ["live"]  # the fixture, re-exported so pytest finds it here

PLAIN = "## Summary\n\nShips the widget. Refs #3\n"


def _durable(root: Path) -> Path:
    return root / "docs" / "superpowers" / "runs" / f"{RUN}.pr-body.md"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _land_policy(root: Path, text: str) -> None:
    """Commit `.fr/settings.yaml` on the base clone's `main` and push it: the default
    ref's revision is the policy source, never the feature branch (R2)."""
    base = root.parent / "base"
    (base / ".fr").mkdir(exist_ok=True)
    (base / ".fr" / "settings.yaml").write_text(text)
    _git(base, "add", "-A")
    _git(base, "commit", "-qm", "settings")
    _git(base, "push", "-q", "origin", "main")


@pytest.fixture
def minimal(tmp_path: Path) -> Path:
    root = _at_deliver(tmp_path)
    _land_policy(root, "forge:\n  pr_body: minimal\n")
    return root


def test_minimal_a_plain_live_body_delivers_and_keeps_the_render_durable(
    minimal: Path, live: dict[str, str]
) -> None:
    live["body"] = PLAIN

    rec, out = _deliver(minimal)

    assert out.exit_code == 0, out.output
    assert load_run_state(minimal, RUN).steps["deliver"].state == "done"
    durable = _durable(minimal)
    assert durable.is_file()
    rel = durable.relative_to(minimal).as_posix()
    assert ".records/" not in rel
    for heading in ("## Findings", "## Out-of-scope findings", "## Proportionality"):
        assert heading in durable.read_text(), heading
    # committed with the deliver resolve, nothing left dirty
    assert rel in _git(minimal, "ls-files").splitlines()
    assert _git(minimal, "status", "--porcelain", "--", rel) == ""
    assert not _body(minimal).exists() and not rec.exists()
    assert rel in out.output and "review" in out.output.lower()


@pytest.mark.parametrize(
    "marker",
    [
        "<!-- fr-technical-debt -->",
        "<!-- fr:gate-pass tester -->",
        "<!-- rendered by fr for run r1",
    ],
)
def test_minimal_refuses_any_fr_marker_in_the_live_body(
    minimal: Path, live: dict[str, str], marker: str
) -> None:
    live["body"] = f"{PLAIN}\n{marker}\n"

    _rec, out = _deliver(minimal)

    assert out.exit_code == 2, out.output
    assert "marker" in out.output and "pr_body: minimal" in out.output
    assert load_run_state(minimal, RUN).steps["deliver"].state == "running"
    assert _durable(minimal).is_file()  # the render is there to review either way


def test_minimal_still_refuses_a_shared_closing_keyword(
    minimal: Path, live: dict[str, str]
) -> None:
    live["body"] = "## Summary\n\nCloses #1 and #2\n"

    _rec, out = _deliver(minimal)

    assert out.exit_code == 2, out.output
    assert "closing keyword" in out.output
    assert load_run_state(minimal, RUN).steps["deliver"].state == "running"


def test_full_is_unchanged_a_plain_body_is_refused_and_no_durable_render_is_kept(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    _land_policy(root, "forge:\n  pr_body: full\n")
    live["body"] = PLAIN

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "lacks required section" in out.output
    assert _body(root).is_file() and not _durable(root).exists()
    live["body"] = _body(root).read_text()

    rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert not rec.exists() and not _body(root).exists() and not _durable(root).exists()
