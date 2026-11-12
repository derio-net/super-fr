"""R9 (amended), p3-r2: a command acting on a repo it has no checkout of reads that repo's
`.fr/settings.yaml` at its default branch through the forge's contents API. Absent means
the defaults; any other read failure refuses the write (`SettingsError`). The file is
parsed by the same closed, strict model the checkout reader uses."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.gh import GhError
from fr.settings import SettingsError
from fr.settings.remote import (
    PolicyReader,
    RepoPolicy,
    clear_client_cache,
    client_policy,
    remote_policy,
)

from tests.unit.settings_repo import land_on_main, make_repo


class _Client:
    """A forge client whose only read is the contents API (`read_file`)."""

    def __init__(self, files: dict[tuple[str, str], str] | None = None, *, error: str = "") -> None:
        self.files = files or {}
        self.error = error
        self.reads: list[tuple[str, str]] = []

    def read_file(self, repo: str, path: str) -> str:
        self.reads.append((repo, path))
        if self.error:
            raise GhError(self.error, stderr=self.error)
        try:
            return self.files[(repo, path)]
        except KeyError:
            raise GhError("gh: Not Found (HTTP 404)", stderr="gh: Not Found (HTTP 404)") from None


def test_an_absent_file_is_the_defaults() -> None:
    client = _Client()
    policy = remote_policy(client, "o/r")
    assert client.reads == [("o/r", ".fr/settings.yaml")]
    for kind in ("labels", "comments", "issues"):
        assert policy.block(kind) is None
        assert policy.allows(kind)


def test_a_file_turning_a_kind_off_blocks_that_kind_only() -> None:
    client = _Client({("o/r", ".fr/settings.yaml"): "forge:\n  labels: 'off'\n"})
    policy = remote_policy(client, "o/r")
    assert "forge.labels: off" in (policy.block("labels") or "")
    assert "forge.labels: off" in (policy.ledger_block("labels") or "")
    assert policy.block("comments") is None
    assert policy.block("issues") is None


@pytest.mark.parametrize("error", ["gh: Bad credentials (HTTP 401)", "HTTP 500", "timed out"])
def test_any_other_read_failure_refuses(error: str) -> None:
    with pytest.raises(SettingsError, match=r"o/r.*\.fr/settings\.yaml"):
        remote_policy(_Client(error=error), "o/r")


def test_the_remote_file_is_parsed_strictly() -> None:
    client = _Client({("o/r", ".fr/settings.yaml"): "forge:\n  labels: sometimes\n"})
    with pytest.raises(SettingsError, match=r"forge\.labels"):
        remote_policy(client, "o/r")
    unknown = _Client({("o/r", ".fr/settings.yaml"): "forge:\n  colour: blue\n"})
    with pytest.raises(SettingsError):
        remote_policy(unknown, "o/r")
    yaml = _Client({("o/r", ".fr/settings.yaml"): "forge: [\n"})
    with pytest.raises(SettingsError, match="not valid YAML"):
        remote_policy(yaml, "o/r")


def test_a_checkout_is_read_locally_and_honours_tracking_none(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  comments: 'off'\n")
    client = _Client()
    reader = PolicyReader(lambda repo: client, lambda repo: root if repo == "o/r" else None)
    policy = reader.policy("o/r")
    assert client.reads == []  # the checkout answered
    assert "forge.comments: off" in (policy.block("comments") or "")
    other = reader.policy("o/elsewhere")
    assert client.reads == [("o/elsewhere", ".fr/settings.yaml")]
    assert other.block("comments") is None
    reader.policy("o/elsewhere")
    assert len(client.reads) == 1  # one read per repo per reader


def test_tracking_none_blocks_tracker_writes_but_not_the_ledger() -> None:
    from fr.settings.model import parse_settings

    policy = RepoPolicy(parse_settings({}, source="t").forge, tracking_none=True)
    assert "tracking: none" in (policy.block("labels") or "")
    assert policy.ledger_block("labels") is None
    assert policy.ledger_block("comments") is None


def test_client_policy_reads_once_per_client_and_repo() -> None:
    clear_client_cache()
    client = _Client({("o/r", ".fr/settings.yaml"): "forge:\n  issues: 'off'\n"})
    assert client_policy(client, "o/r").block("issues") is not None
    assert client_policy(client, "O/R").block("issues") is not None
    assert client.reads == [("o/r", ".fr/settings.yaml")]
    fresh = _Client()
    assert client_policy(fresh, "o/r").block("issues") is None  # another client reads anew
