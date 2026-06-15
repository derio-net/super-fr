"""fr.isolation.secrets — the SecretProvider seam + EnvFileProvider (default).

Pure unit tests: no Docker, no network. EnvFileProvider preserves today's
mount-following env-file ensure (factored out of local._ensure_mounted_env_file),
so back-compat is the headline assertion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.isolation.secrets import (
    EnvFileProvider,
    ExecWrap,
    ProfileContext,
    provider_for,
)
from fr.isolation.types import IsolationError, secrets_env_file


def _ctx(
    worktree: Path,
    *,
    repo: str = "myrepo",
    profile: str = "dev",
    keys: tuple[str, ...] = (),
    config: dict | None = None,
) -> ProfileContext:
    return ProfileContext(
        repo=repo, profile=profile, keys=keys, config=config or {}, worktree=worktree
    )


def _profile_with_env_file(worktree: Path, profile: str, env_file_value: str) -> None:
    d = worktree / ".devcontainer" / profile
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text(
        json.dumps({"image": "x", "runArgs": ["--env-file", env_file_value]}) + "\n"
    )


def test_profile_context_fields(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, keys=("A", "B"), config={"secret_provider": "env-file"})
    assert ctx.repo == "myrepo"
    assert ctx.profile == "dev"
    assert ctx.keys == ("A", "B")
    assert ctx.config["secret_provider"] == "env-file"
    assert ctx.worktree == tmp_path


def test_provider_for_defaults_to_env_file(tmp_path: Path) -> None:
    # No secret_provider key ⇒ env-file (back-compat default).
    assert isinstance(provider_for(_ctx(tmp_path)), EnvFileProvider)


def test_provider_for_unknown_raises(tmp_path: Path) -> None:
    with pytest.raises(IsolationError) as ei:
        provider_for(_ctx(tmp_path, config={"secret_provider": "bogus"}))
    assert "bogus" in str(ei.value)


def test_env_file_exec_wrap_is_ambient(tmp_path: Path) -> None:
    # env-file keys are ambient via the --env-file mount: no wrap, no env.
    wrap = EnvFileProvider().exec_wrap(_ctx(tmp_path), want_secrets=True)
    assert wrap == ExecWrap(argv_prefix=(), exec_env={})


def test_env_file_up_prepare_ensures_mounted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    worktree = tmp_path / "wt"
    canonical = "${localEnv:HOME}/.config/fr/secrets/myrepo/dev.env"
    _profile_with_env_file(worktree, "dev", canonical)

    EnvFileProvider().up_prepare(_ctx(worktree))

    env_file = secrets_env_file("myrepo", "dev")
    assert env_file.is_file()
    assert env_file.read_text() == "# fr isolation secrets — myrepo\n"


def test_env_file_up_prepare_leaves_existing_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    worktree = tmp_path / "wt"
    _profile_with_env_file(worktree, "dev", "${localEnv:HOME}/.config/fr/secrets/myrepo/dev.env")
    env_file = secrets_env_file("myrepo", "dev")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("API_KEY=already-set\n")

    EnvFileProvider().up_prepare(_ctx(worktree))

    assert env_file.read_text() == "API_KEY=already-set\n"
