"""An origin that names no forge (spec 2026-11-23-pr-readiness-wait R11, amended): a local
path or a `file://` URL is `unsupported`, recorded, never refused, with no forge client."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.settle import read

from tests.unit.settings_repo import git, make_repo

REAL_ORIGIN_URL = read.origin_url
"""Captured at import: tests/conftest.py serves a GitHub origin to every other test."""


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("/srv/git/origin.git", True),
        ("../origin.git", True),
        ("origin.git", True),
        ("file:///srv/git/origin.git", True),
        ("https://github.com/derio-net/super-fr.git", False),
        ("git@github.com:derio-net/super-fr.git", False),
        ("ssh://git@gitlab.example.com/g/p.git", False),
        (None, False),
    ],
)
def test_which_origins_name_no_forge(url: str | None, local: bool) -> None:
    assert read.names_no_forge(url) is local


def test_the_origin_url_is_read_from_git(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)  # its origin is a local bare repository

    assert REAL_ORIGIN_URL(repo) == str(tmp_path / "origin.git")
    git(repo, "remote", "set-url", "origin", "file:///x/origin.git")
    assert REAL_ORIGIN_URL(repo) == "file:///x/origin.git"
