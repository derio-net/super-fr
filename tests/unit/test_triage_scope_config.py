"""Scope identity and the scope config (spec 2026-10-06-triage-claims §3.A, R1, R15)."""

from __future__ import annotations

import os
import re
import socket
import stat
from pathlib import Path

import pytest
from fr.triage import scope_config
from fr.triage.errors import TriageError
from fr.triage.model import Scope
from fr.triage.scope_config import (
    ScopeConfig,
    default_board_name,
    host_id,
    load_scope_config,
    scope_id,
)
from fr.triage.state_sync import DURABLE_FILES, export_state

REPO = Scope(kind="repo", target="derio-net/super-fr")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FR_HOST_ID", raising=False)
    return tmp_path


def _id_file(home: Path) -> Path:
    return home / ".config" / "fr" / "host-id"


def test_fr_host_id_overrides_the_file(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_HOST_ID", "pod-identity")
    assert host_id() == "pod-identity"
    assert not _id_file(home).exists()


def test_first_use_creates_a_private_sixteen_hex_id_and_keeps_it(home: Path) -> None:
    first = host_id()
    assert re.fullmatch(r"[0-9a-f]{16}", first)
    path = _id_file(home)
    assert path.read_text(encoding="utf-8").strip() == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert host_id() == first
    # no temp file left beside it
    assert sorted(p.name for p in path.parent.iterdir()) == ["host-id"]


def test_the_loser_of_a_concurrent_first_use_returns_the_winners_id(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_link = os.link

    def racing_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        # Another process wins between our check and our link.
        Path(dst).write_text("0123456789abcdef\n", encoding="utf-8")
        raise FileExistsError(dst)

    monkeypatch.setattr(scope_config.os, "link", racing_link)
    assert host_id() == "0123456789abcdef"
    monkeypatch.setattr(scope_config.os, "link", real_link)
    assert host_id() == "0123456789abcdef"
    assert sorted(p.name for p in _id_file(home).parent.iterdir()) == ["host-id"]


def test_a_malformed_host_id_file_is_refused_naming_its_path(home: Path) -> None:
    path = _id_file(home)
    path.parent.mkdir(parents=True)
    path.write_text("not an id\n", encoding="utf-8")
    with pytest.raises(TriageError, match=re.escape(str(path))):
        host_id()
    assert path.read_text(encoding="utf-8") == "not an id\n"


def test_scope_ids_are_stable_host_qualified_and_anonymous(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_HOST_ID", "aaaaaaaaaaaaaaaa")
    sid = scope_id(REPO)
    assert re.fullmatch(r"s-[0-9a-f]{8}", sid)
    assert scope_id(REPO) == sid
    assert scope_id(Scope(kind="org", target="derio-net")) != sid
    monkeypatch.setenv("FR_HOST_ID", "bbbbbbbbbbbbbbbb")
    assert scope_id(REPO) != sid
    host = socket.gethostname().lower()
    assert host not in sid
    assert "super-fr" not in sid


def test_scope_config_defaults_when_the_file_is_missing(tmp_path: Path) -> None:
    cfg = load_scope_config(tmp_path)
    assert (cfg.claim_expiry_hours, cfg.board_name, cfg.publish) == (24, None, [])
    assert ScopeConfig() == cfg


def test_scope_config_reads_its_keys(tmp_path: Path) -> None:
    (tmp_path / "scope.yaml").write_text(
        "claim_expiry_hours: 6\nboard_name: My board\npublish: [echo, '{board}']\n",
        encoding="utf-8",
    )
    cfg = load_scope_config(tmp_path)
    assert (cfg.claim_expiry_hours, cfg.board_name, cfg.publish) == (6, "My board", ["echo", "{board}"])


@pytest.mark.parametrize(
    "body", ["claim_expiry_hours: 0\n", "claim_expiry: 6\n", "publish: echo hi\n", "- a\n"]
)
def test_an_invalid_scope_config_is_refused_naming_the_file(tmp_path: Path, body: str) -> None:
    path = tmp_path / "scope.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(TriageError, match=re.escape(str(path))):
        load_scope_config(tmp_path)


def test_default_board_names_per_scope_kind() -> None:
    assert default_board_name(REPO) == "super-fr batches"
    assert default_board_name(Scope(kind="org", target="derio-net")) == "derio-net batches"
    group = Scope.group(["derio-net/super-fr", "derio-net/frank"])
    assert default_board_name(group) == f"{group.name} batches"


def test_scope_yaml_is_not_durable_state(tmp_path: Path) -> None:
    assert "scope.yaml" not in DURABLE_FILES
    state = tmp_path / "state"
    state.mkdir()
    (state / "judgements.yaml").write_text("schema: 6\n", encoding="utf-8")
    (state / "scope.yaml").write_text("publish: [echo]\n", encoding="utf-8")
    dest = tmp_path / "repo" / "docs" / "triage" / "x"
    report = export_state(state, dest.parent, dest.name)
    assert "scope.yaml" not in report.copied
    assert not (dest / "scope.yaml").exists()
