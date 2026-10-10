"""Shared OS-lock infrastructure fails closed on unenforced filesystems."""

import subprocess

import pytest
from fr import file_lock


def test_exclusive_file_lock_refuses_nested_owner_and_releases(native_herdr_cache):
    path = native_herdr_cache / "shared.lock"
    with file_lock.exclusive_file_lock(path):
        with pytest.raises(file_lock.FileLockError, match="locked"):
            with file_lock.exclusive_file_lock(path):
                pytest.fail("loser admitted")
    with file_lock.exclusive_file_lock(path):
        pass


def test_acknowledged_but_unenforced_lock_never_yields(native_herdr_cache, monkeypatch):
    monkeypatch.setattr(
        file_lock.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    with pytest.raises(file_lock.FileLockError, match="does not enforce"):
        with file_lock.exclusive_file_lock(native_herdr_cache / "shared.lock"):
            pytest.fail("unverified ownership yielded")
