"""`drive` asks for no checkout of a departed repo (2026-11-27-closeout-state R5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.commands import triage_batch_cmd
from fr.triage.model import Facts, Scope, Truncation
from typer import Exit

SCOPE = Scope(kind="org", target="example-org")
JUDGEMENTS = """\
schema: 3
tiers: [{n: 1, title: Now}]
issues:
  'gone#1': {tier: 1}
  'kept#1': {tier: 1}
batches:
  - {id: a, title: A, ids: ['gone#1'], wave: 1}
  - {id: b, title: B, ids: ['kept#1'], wave: 1}
"""


def _state(
    tmp_path: Path, repos: list[str], *, facts: bool = True, truncated: bool = False
) -> Path:
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, "utf-8")
    if facts:
        doc = Facts(
            viewer="op",
            scope="example-org",
            kind="org",
            collected_at="2026-10-02T12:00:00+00:00",
            repos=repos,
            issues=[],
            warnings=(
                [Truncation(source="repos", target="example-org", limit=100)] if truncated else []
            ),
        )
        (tmp_path / "facts.json").write_text(json.dumps(doc.to_json()), "utf-8")
    return tmp_path


def _build(target: Path, checkout: list[str]) -> triage_batch_cmd._Driver:
    return triage_batch_cmd.build_driver(
        SCOPE, target, batch_ids=None, checkout=checkout, max_inflight=2, yes=False
    )


def test_a_departed_repo_needs_no_checkout(tmp_path: Path) -> None:
    target = _state(tmp_path, ["example-org/kept"])
    driver = _build(target, ["example-org/kept=/tmp/kept"])
    assert set(driver.checkout_paths) == {"example-org/kept"}


def test_a_present_repo_with_no_clone_still_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _state(tmp_path, ["example-org/kept", "example-org/gone"])
    with pytest.raises(Exit):
        _build(target, ["example-org/kept=/tmp/kept"])
    assert "give --checkout REPO=PATH for example-org/gone" in capsys.readouterr().err.replace(
        "\n", ""
    )


def test_without_facts_every_repo_still_needs_a_clone(tmp_path: Path) -> None:
    target = _state(tmp_path, [], facts=False)
    with pytest.raises(Exit):
        _build(target, ["example-org/kept=/tmp/kept"])


@pytest.mark.parametrize(
    "text", ['{"schema": 1}', "not json", ""], ids=["old-schema", "corrupt", "empty"]
)
def test_unusable_facts_count_as_absent(tmp_path: Path, text: str) -> None:
    """p2-r2: drive never refuses to start over a facts file collect would re-read anyway."""
    target = _state(tmp_path, [], facts=False)
    (target / "facts.json").write_text(text, "utf-8")
    driver = _build(target, ["example-org/kept=/tmp/kept", "example-org/gone=/tmp/gone"])
    assert set(driver.checkout_paths) == {"example-org/kept", "example-org/gone"}


def test_a_truncated_repo_list_does_not_hide_a_missing_clone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The repo list may merely be cut short: a repo missing from it is not departed."""
    target = _state(tmp_path, ["example-org/kept"], truncated=True)
    with pytest.raises(Exit):
        _build(target, ["example-org/kept=/tmp/kept"])
    assert "give --checkout REPO=PATH for example-org/gone" in capsys.readouterr().err.replace(
        "\n", ""
    )
