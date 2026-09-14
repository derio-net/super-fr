"""fr.isolation.secrets — InfisicalProvider + InfisicalAuth (UniversalAuth).

No live Infisical, no network: the token mint goes through an injected
`TokenMinter` seam. The headline invariant is that no secret material (the UA
client-secret or the minted token) ever lands on a command-line argv.
"""

from __future__ import annotations

import shlex
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from fr.isolation.secrets import (
    CONTAINER_TOKEN_DIR,
    ExecWrap,
    InfisicalProvider,
    KubernetesAuth,
    ProfileContext,
    UniversalAuth,
    host_token_dir,
)
from fr.isolation.types import IsolationError

INFISICAL_CFG = {
    "secret_provider": "infisical",
    "infisical": {
        "project_id": "proj-123",
        "env": "prod",
        "path": "/fr/myrepo/admin",
        "auth": {
            "method": "universal-auth",
            "client_id_env": "FR_CID",
            "client_secret_env": "FR_CSEC",
        },
    },
}


def _ctx(worktree: Path) -> ProfileContext:
    return ProfileContext(
        repo="myrepo",
        profile="admin",
        keys=("DEPLOY_KEY",),
        config=INFISICAL_CFG,
        worktree=worktree,
    )


class _FakeMinter:
    """Records the (argv, env) it is called with; returns a canned token."""

    def __init__(self, token: str = "tok-abc") -> None:
        self.token = token
        self.calls: list[tuple[tuple[str, ...], Mapping[str, str]]] = []

    def __call__(self, argv: Sequence[str], env: Mapping[str, str]) -> str:
        self.calls.append((tuple(argv), dict(env)))
        return self.token


# ---- UniversalAuth (host-side mint) ----


def test_universal_auth_mints_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FR_CID", "client-id-xyz")
    monkeypatch.setenv("FR_CSEC", "super-secret-value")
    minter = _FakeMinter()
    token = UniversalAuth(minter=minter).mint_token(_ctx(tmp_path))
    assert token == "tok-abc"
    ((argv, env),) = minter.calls
    # No secret material on argv — neither the client-secret nor (defensively)
    # the client-id appear as command-line arguments.
    assert "super-secret-value" not in argv
    assert not any("super-secret-value" in a for a in argv)
    # The client-secret reaches the CLI via the env mapping, not argv.
    assert "super-secret-value" in env.values()


def test_universal_auth_missing_env_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FR_CID", "client-id-xyz")
    monkeypatch.delenv("FR_CSEC", raising=False)
    with pytest.raises(IsolationError) as ei:
        UniversalAuth(minter=_FakeMinter()).mint_token(_ctx(tmp_path))
    assert "FR_CSEC" in str(ei.value)


def test_kubernetes_auth_returns_none(tmp_path: Path) -> None:
    assert KubernetesAuth().mint_token(_ctx(tmp_path)) is None


# ---- InfisicalProvider ----


def test_infisical_exec_wrap_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "client-id-xyz")
    monkeypatch.setenv("FR_CSEC", "super-secret-value")
    minter = _FakeMinter(token="tok-abc")
    prov = InfisicalProvider(auth=UniversalAuth(minter=minter))
    ctx = _ctx(tmp_path)

    wrap = prov.exec_wrap(ctx, want_secrets=True)

    flat = " ".join(wrap.argv_prefix)
    assert "infisical" in flat and "run" in flat
    assert "--projectId proj-123" in flat
    assert "--env prod" in flat
    assert "--path /fr/myrepo/admin" in flat
    # The token is read from the mounted per-exec token-file at runtime — never
    # on argv and not handed through exec_env either.
    assert "tok-abc" not in flat
    assert "tok-abc" not in " ".join(wrap.exec_env.values())
    # The token WAS minted and written to ONE 0600 file in the 0700 host dir,
    # and the script reads exactly that file under the container mount.
    d = host_token_dir("myrepo", "admin")
    (tf,) = list(d.iterdir())
    assert tf.read_text() == "tok-abc"
    assert stat.S_IMODE(tf.stat().st_mode) == 0o600
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert f"{CONTAINER_TOKEN_DIR}/{tf.name}" in flat


def test_two_wraps_write_two_distinct_token_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Two concurrent `--secret` execs must never share a file (the race the
    # original branch left as a NOTE). One provider per exec is the Target's
    # contract; assert it with two instances.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "sec")
    ctx = _ctx(tmp_path)
    a = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-a")))
    b = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-b")))

    wrap_a = a.exec_wrap(ctx, want_secrets=True)
    wrap_b = b.exec_wrap(ctx, want_secrets=True)

    files = sorted(host_token_dir("myrepo", "admin").iterdir())
    assert len(files) == 2
    assert {f.read_text() for f in files} == {"tok-a", "tok-b"}
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in files)
    # Each wrap reads its OWN file — the two scripts differ only by file name.
    assert wrap_a.argv_prefix != wrap_b.argv_prefix
    for wrap, tok in ((wrap_a, "tok-a"), (wrap_b, "tok-b")):
        assert not any(tok in a for a in wrap.argv_prefix)


def test_post_exec_unlinks_only_its_own_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "sec")
    ctx = _ctx(tmp_path)
    a = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-a")))
    b = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-b")))
    a.exec_wrap(ctx, want_secrets=True)
    b.exec_wrap(ctx, want_secrets=True)
    d = host_token_dir("myrepo", "admin")

    a.post_exec(ctx)

    (survivor,) = list(d.iterdir())
    assert survivor.read_text() == "tok-b"  # b's exec is still running
    b.post_exec(ctx)
    assert list(d.iterdir()) == []
    a.post_exec(ctx)  # idempotent — a second call is a no-op, never raises


def test_post_exec_without_wrap_is_a_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()))
    prov.post_exec(_ctx(tmp_path))  # no exec happened — nothing to unlink


def test_infisical_exec_wrap_no_secrets_does_not_mint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    minter = _FakeMinter()
    prov = InfisicalProvider(auth=UniversalAuth(minter=minter))
    assert prov.exec_wrap(_ctx(tmp_path), want_secrets=False) == ExecWrap()
    assert minter.calls == []  # no mint when no secrets requested


def test_infisical_up_prepare_creates_empty_0700_token_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    prov = InfisicalProvider(
        auth=UniversalAuth(minter=_FakeMinter()),
        validate=lambda ctx: None,  # touchpoint checks injected as no-op here
    )
    prov.up_prepare(_ctx(tmp_path))
    d = host_token_dir("myrepo", "admin")
    assert d.is_dir()
    assert list(d.iterdir()) == []  # mount source exists; NO secret at up
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_infisical_up_prepare_fails_when_touchpoint_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def _boom(ctx: ProfileContext) -> None:
        raise IsolationError("infisical CLI not found in image")

    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()), validate=_boom)
    with pytest.raises(IsolationError) as ei:
        prov.up_prepare(_ctx(tmp_path))
    assert "infisical CLI" in str(ei.value)


def test_infisical_cleanup_removes_every_leftover_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "sec")
    ctx = _ctx(tmp_path)
    # Two execs whose post_exec never ran (a crash mid-exec) + a stray file.
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("t1"))).exec_wrap(ctx, True)
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("t2"))).exec_wrap(ctx, True)
    d = host_token_dir("myrepo", "admin")
    (d / "stray").write_text("x")
    assert len(list(d.iterdir())) == 3

    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).cleanup(ctx)

    assert not d.exists()
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).cleanup(ctx)  # idempotent


def test_infisical_exec_wrap_quotes_config_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A malicious `path` must NOT inject into the in-container shell — shlex.quote
    # neutralizes it (the value comes from PR/branch-reachable fr-profiles.yaml).
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "sec")
    evil = "/fr/x; touch /tmp/pwned"
    cfg = {**INFISICAL_CFG, "infisical": {**INFISICAL_CFG["infisical"], "path": evil}}
    ctx = ProfileContext(
        repo="myrepo", profile="admin", keys=("DEPLOY_KEY",), config=cfg, worktree=tmp_path
    )
    wrap = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).exec_wrap(
        ctx, want_secrets=True
    )
    script = wrap.argv_prefix[2]  # the `sh -lc` script
    assert shlex.quote(evil) in script  # quoted → the `;` is inert
    assert "--path /fr/x; touch" not in script  # never the raw, injectable form
    # The per-exec container path is quoted too (defensive; the name is ours).
    (tf,) = list(host_token_dir("myrepo", "admin").iterdir())
    assert shlex.quote(f"{CONTAINER_TOKEN_DIR}/{tf.name}") in script
