"""fr.isolation.secrets — InfisicalProvider + InfisicalAuth (UniversalAuth).

No live Infisical, no network: the token mint goes through an injected
`TokenMinter` seam. The headline invariant is that no secret material (the UA
client-secret or the minted token) ever lands on a command-line argv.

The host token directory FOLLOWS THE MOUNT the profile's devcontainer.json
declares (review I2) and is per-workspace (review I1): every test writes the
profile's devcontainer.json under the ctx worktree, and `_dir(worktree)` is
where that mount resolves.
"""

from __future__ import annotations

import json
import shlex
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from fr.isolation import secrets as secrets_mod
from fr.isolation.secrets import (
    CONTAINER_TOKEN_DIR,
    ExecWrap,
    InfisicalProvider,
    KubernetesAuth,
    ProfileContext,
    UniversalAuth,
    canonical_token_dir,
    remove_token_dir,
    resolve_token_dir,
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

# The mount `fr init scaffold --secret-provider infisical` writes: host dir is
# per (repo, profile, workspace basename), container dir is fixed.
MOUNT = (
    "type=bind,source=${localEnv:HOME}/.cache/fr/run-tokens/myrepo/admin/"
    f"${{localWorkspaceFolderBasename}},target={CONTAINER_TOKEN_DIR}"
)


def _write_profile(worktree: Path, mount: str | None = MOUNT, profile: str = "admin") -> Path:
    d = worktree / ".devcontainer" / profile
    d.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"image": "x"}
    if mount is not None:
        cfg["runArgs"] = ["--mount", mount]
    p = d / "devcontainer.json"
    p.write_text(json.dumps(cfg) + "\n")
    return p


def _ctx(
    worktree: Path, config: Mapping = INFISICAL_CFG, mount: str | None = MOUNT
) -> ProfileContext:
    _write_profile(worktree, mount=mount)
    return ProfileContext(
        repo="myrepo", profile="admin", keys=("DEPLOY_KEY",), config=config, worktree=worktree
    )


def _dir(worktree: Path) -> Path:
    """Where MOUNT resolves for this worktree — the canonical scaffold layout."""
    return canonical_token_dir("myrepo", "admin", worktree)


class _FakeMinter:
    """Records the (argv, env) it is called with; returns a canned token."""

    def __init__(self, token: str = "tok-abc") -> None:
        self.token = token
        self.calls: list[tuple[tuple[str, ...], Mapping[str, str]]] = []

    def __call__(self, argv: Sequence[str], env: Mapping[str, str]) -> str:
        self.calls.append((tuple(argv), dict(env)))
        return self.token


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_CID", "client-id-xyz")
    monkeypatch.setenv("FR_CSEC", "super-secret-value")
    return tmp_path / "home"


# ---- UniversalAuth (host-side mint) ----


def test_universal_auth_mints_from_env(home: Path, tmp_path: Path) -> None:
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


def test_universal_auth_missing_env_raises(home: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FR_CSEC", raising=False)
    with pytest.raises(IsolationError) as ei:
        UniversalAuth(minter=_FakeMinter()).mint_token(_ctx(tmp_path))
    assert "FR_CSEC" in str(ei.value)


def test_kubernetes_auth_returns_none(tmp_path: Path) -> None:
    assert KubernetesAuth().mint_token(_ctx(tmp_path)) is None


# ---- _subprocess_mint hardening (review m4) ----


def test_subprocess_mint_missing_binary_is_isolation_error(monkeypatch) -> None:
    def _run(*a, **kw):
        raise FileNotFoundError("infisical")

    monkeypatch.setattr(secrets_mod.subprocess, "run", _run)
    with pytest.raises(IsolationError, match="infisical"):
        secrets_mod._subprocess_mint(["infisical", "login"], {})


def test_subprocess_mint_timeout_is_isolation_error(monkeypatch) -> None:
    def _run(argv, **kw):
        assert kw.get("timeout")  # a timeout is always passed
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    monkeypatch.setattr(secrets_mod.subprocess, "run", _run)
    with pytest.raises(IsolationError, match="timed out"):
        secrets_mod._subprocess_mint(["infisical", "login"], {})


def test_subprocess_mint_empty_stdout_is_isolation_error(monkeypatch) -> None:
    monkeypatch.setattr(
        secrets_mod.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout="  \n", stderr=""),
    )
    with pytest.raises(IsolationError, match="no token"):
        secrets_mod._subprocess_mint(["infisical", "login"], {})


# ---- token dir resolution (review I1 / I2) ----


@pytest.mark.parametrize("form", ["separate", "equals"])
def test_resolve_token_dir_follows_mount_and_substitutes_variables(
    home: Path, tmp_path: Path, form: str
) -> None:
    # The mount names a DIFFERENT repo dir than the runtime target would compute
    # (scaffolded from a clone called `other-clone`): the mount wins.
    mount = (
        "type=bind,source=${localEnv:HOME}/.cache/fr/run-tokens/other-clone/admin/"
        f"${{localWorkspaceFolderBasename}},target={CONTAINER_TOKEN_DIR}"
    )
    wt = tmp_path / "feat__x"
    d = wt / ".devcontainer" / "admin"
    d.mkdir(parents=True)
    run_args = ["--mount", mount] if form == "separate" else [f"--mount={mount}"]
    cfg = d / "devcontainer.json"
    cfg.write_text(json.dumps({"image": "x", "runArgs": run_args}))

    assert resolve_token_dir(cfg, wt) == home / ".cache/fr/run-tokens/other-clone/admin/feat__x"


def test_resolve_token_dir_missing_mount_is_actionable(home: Path, tmp_path: Path) -> None:
    cfg = _write_profile(tmp_path, mount=None)
    with pytest.raises(IsolationError) as ei:
        resolve_token_dir(cfg, tmp_path)
    msg = str(ei.value)
    assert CONTAINER_TOKEN_DIR in msg and "fr init scaffold" in msg


def test_exec_wrap_missing_mount_raises_before_mint(home: Path, tmp_path: Path) -> None:
    minter = _FakeMinter()
    with pytest.raises(IsolationError, match=CONTAINER_TOKEN_DIR):
        InfisicalProvider(auth=UniversalAuth(minter=minter)).exec_wrap(
            _ctx(tmp_path, mount=None), want_secrets=True
        )
    assert minter.calls == []  # nothing minted → nothing to leak


def test_up_prepare_missing_mount_raises(home: Path, tmp_path: Path) -> None:
    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()), validate=lambda c: None)
    with pytest.raises(IsolationError, match=CONTAINER_TOKEN_DIR):
        prov.up_prepare(_ctx(tmp_path, mount=None))


def test_cleanup_falls_back_to_canonical_dir_when_mount_unreadable(
    home: Path, tmp_path: Path
) -> None:
    d = _dir(tmp_path)
    d.mkdir(parents=True)
    (d / "left.token").write_text("tok")
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).cleanup(_ctx(tmp_path, mount=None))
    assert not d.exists()


# ---- containment of the resolved dir (verification V1 / V7) ----


def _cfg_with_source(worktree: Path, source: str) -> Path:
    return _write_profile(worktree, mount=f"type=bind,source={source},target={CONTAINER_TOKEN_DIR}")


@pytest.mark.parametrize(
    "source",
    [
        "${localEnv:HOME}",  # $HOME itself — `down` would empty every dotfile
        "${localEnv:HOME}/.cache/fr/run-tokens/../../..",  # `..` escape from the root
        "${localEnv:HOME}/.cache/fr/run-tokens/repo/admin",  # wrong depth (the old shared layout)
        "${localEnv:HOME}/.cache/fr/run-tokens/r/p/w/deeper",  # too deep
        "${localEnv:FR_TEST_UNSET}/.cache/fr/run-tokens/r/p/w",  # unset var → resolves under /
        "${localEnv:HOME}/.config/fr/secrets/myrepo",  # the operator's env files
        "${bogus}/x",  # an unknown variable must never pass through as a literal
    ],
)
def test_resolve_token_dir_refuses_uncontained_sources(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    monkeypatch.delenv("FR_TEST_UNSET", raising=False)
    cfg = _cfg_with_source(tmp_path, source)
    with pytest.raises(IsolationError) as ei:
        resolve_token_dir(cfg, tmp_path)
    msg = str(ei.value)
    assert source in msg  # names the offending source …
    assert "run-tokens/<repo>/<profile>/<workspace>" in msg  # … and the required layout


def test_uncontained_source_fails_closed_at_up_exec_and_cleanup(home: Path, tmp_path: Path) -> None:
    """The HOME-as-source case end to end: nothing minted, nothing created, and
    cleanup (which must not raise) falls back to the contained canonical dir —
    the sentinel dotfile in the fake HOME survives every call."""
    _cfg_with_source(tmp_path, "${localEnv:HOME}")
    home.mkdir(parents=True, exist_ok=True)
    (home / ".bashrc").write_text("sentinel")
    ctx = ProfileContext(
        repo="myrepo",
        profile="admin",
        keys=("DEPLOY_KEY",),
        config=INFISICAL_CFG,
        worktree=tmp_path,
    )
    minter = _FakeMinter()
    prov = InfisicalProvider(auth=UniversalAuth(minter=minter), validate=lambda c: None)
    with pytest.raises(IsolationError):
        prov.up_prepare(ctx)
    with pytest.raises(IsolationError):
        prov.exec_wrap(ctx, want_secrets=True)
    assert minter.calls == []
    prov.cleanup(ctx)  # best-effort: no raise, no damage
    assert (home / ".bashrc").read_text() == "sentinel"
    assert sorted(p.name for p in home.iterdir()) == [".bashrc"] or (home / ".cache").exists()


def test_symlinked_token_dir_is_refused_and_its_target_untouched(
    home: Path, tmp_path: Path
) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "precious").write_text("keep")
    d = _dir(tmp_path)
    d.parent.mkdir(parents=True)
    d.symlink_to(target)
    cfg = _write_profile(tmp_path)  # the legit MOUNT — but its dir is a symlink on disk

    with pytest.raises(IsolationError, match="symlink"):
        resolve_token_dir(cfg, tmp_path)
    remove_token_dir(d)  # defence in depth: refuses, no raise

    assert d.is_symlink() and (target / "precious").read_text() == "keep"


def test_remove_token_dir_refuses_paths_outside_the_root(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_text("x")
    remove_token_dir(outside)
    assert (outside / "f").read_text() == "x" and outside.is_dir()
    assert "refus" in capsys.readouterr().err


def test_remove_token_dir_never_truncates_through_symlinked_children(
    home: Path, tmp_path: Path
) -> None:
    d = _dir(tmp_path)
    d.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    (d / "link.token").symlink_to(victim)
    (d / "real.token").write_text("tok")
    remove_token_dir(d)
    assert victim.read_text() == "keep"
    assert not d.exists()


def test_resolve_token_dir_supports_localenv_default_values(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `${localEnv:VAR:default}` is devcontainer-CLI syntax; host-side resolution
    # must agree with the CLI on both branches (verification V7).
    monkeypatch.delenv("FR_TEST_UNSET", raising=False)
    cfg = _cfg_with_source(
        tmp_path,
        "${localEnv:HOME}/.cache/fr/run-tokens/${localEnv:FR_TEST_UNSET:fallback-repo}/admin/"
        "${localWorkspaceFolderBasename}",
    )
    root = home / ".cache" / "fr" / "run-tokens"
    assert resolve_token_dir(cfg, tmp_path) == root / "fallback-repo" / "admin" / tmp_path.name
    monkeypatch.setenv("FR_TEST_UNSET", "set-repo")
    assert resolve_token_dir(cfg, tmp_path) == root / "set-repo" / "admin" / tmp_path.name


def test_canonical_token_dir_is_contained_too(home: Path, tmp_path: Path) -> None:
    with pytest.raises(IsolationError):
        canonical_token_dir("..", "admin", tmp_path)
    with pytest.raises(IsolationError):
        canonical_token_dir("myrepo", "admin", Path("/"))  # empty basename


# ---- kubernetes-auth up (verification V4) / partial write (V5) ----

K8S_CFG = {
    **INFISICAL_CFG,
    "infisical": {**INFISICAL_CFG["infisical"], "auth": {"method": "kubernetes-auth"}},
}


def test_up_prepare_creates_the_mount_dir_for_kubernetes_auth_too(
    home: Path, tmp_path: Path
) -> None:
    # The scaffold always writes the mount, so docker needs the source to exist
    # whatever the auth method — otherwise `devcontainer up` fails.
    prov = InfisicalProvider(auth=KubernetesAuth(), validate=lambda c: None)
    prov.up_prepare(_ctx(tmp_path, config=K8S_CFG))
    assert _dir(tmp_path).is_dir()
    assert stat.S_IMODE(_dir(tmp_path).stat().st_mode) == 0o700


def test_up_prepare_kubernetes_auth_without_a_mount_is_fine(home: Path, tmp_path: Path) -> None:
    prov = InfisicalProvider(auth=KubernetesAuth(), validate=lambda c: None)
    prov.up_prepare(_ctx(tmp_path, config=K8S_CFG, mount=None))  # no host token → no mount needed
    assert not _dir(tmp_path).exists()


def test_partially_written_token_is_removed_by_post_exec(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FailingWriter:
        def __init__(self, fd: int) -> None:
            self.fd = fd

        def __enter__(self) -> _FailingWriter:
            return self

        def __exit__(self, *exc: object) -> None:
            secrets_mod.os.close(self.fd)

        def write(self, s: str) -> int:
            raise OSError("disk full")

    monkeypatch.setattr(secrets_mod.os, "fdopen", lambda fd, *a, **k: _FailingWriter(fd))
    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()))
    ctx = _ctx(tmp_path)
    with pytest.raises(OSError):
        prov.exec_wrap(ctx, want_secrets=True)
    assert prov._token_path is not None  # remembered BEFORE the write, so …
    prov.post_exec(ctx)
    assert list(_dir(tmp_path).iterdir()) == []  # … the partial file is gone


# ---- config validation BEFORE mint (review I3) ----


def _without(cfg: Mapping, *path: str) -> dict:
    out: dict = json.loads(json.dumps(cfg))
    node = out
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return out


@pytest.mark.parametrize(
    ("cfg", "needle"),
    [
        (_without(INFISICAL_CFG, "infisical", "path"), "path"),
        (_without(INFISICAL_CFG, "infisical"), "infisical"),
        (_without(INFISICAL_CFG, "infisical", "auth", "client_secret_env"), "client_secret_env"),
        (
            {**INFISICAL_CFG, "infisical": {**INFISICAL_CFG["infisical"], "auth": {"method": "x"}}},
            "x",
        ),
    ],
)
def test_exec_wrap_validates_config_before_mint(
    home: Path, tmp_path: Path, cfg: Mapping, needle: str
) -> None:
    minter = _FakeMinter()
    with pytest.raises(IsolationError) as ei:
        InfisicalProvider(auth=UniversalAuth(minter=minter)).exec_wrap(
            _ctx(tmp_path, config=cfg), want_secrets=True
        )
    assert needle in str(ei.value)
    assert minter.calls == []  # validated BEFORE the mint — no token ever existed
    assert not _dir(tmp_path).exists() or list(_dir(tmp_path).iterdir()) == []


# ---- InfisicalProvider ----


def test_infisical_exec_wrap_shape(home: Path, tmp_path: Path) -> None:
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
    # The token WAS minted and written to ONE 0600 file in the 0700 host dir the
    # mount resolves to, and the script reads exactly that file under the mount.
    d = _dir(tmp_path)
    (tf,) = list(d.iterdir())
    assert tf.read_text() == "tok-abc"
    assert stat.S_IMODE(tf.stat().st_mode) == 0o600
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert f"{CONTAINER_TOKEN_DIR}/{tf.name}" in flat


def test_exec_wrap_unsets_token_for_the_user_command(home: Path, tmp_path: Path) -> None:
    # `infisical run` hands its env to the child, INFISICAL_TOKEN included — the
    # user command must not be able to reuse the token for its TTL (review m5).
    wrap = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).exec_wrap(
        _ctx(tmp_path), want_secrets=True
    )
    script = wrap.argv_prefix[2]
    # `--` ends env's own operand parsing so a user command starting with
    # NAME=VALUE or -x is not eaten as an env assignment/option (verification V6).
    assert script.endswith('-- env -u INFISICAL_TOKEN -- "$@"')
    assert wrap.argv_prefix[:2] == ("sh", "-lc") and wrap.argv_prefix[3] == "fr-secret-wrap"


def test_kubernetes_auth_wrap_has_no_token_file_and_no_assignment(
    home: Path, tmp_path: Path
) -> None:
    # In-pod auth: no host mint, so the script must NOT cat a never-written file
    # and must NOT set INFISICAL_TOKEN="" (that would shadow the pod's auth).
    cfg = {
        **INFISICAL_CFG,
        "infisical": {**INFISICAL_CFG["infisical"], "auth": {"method": "kubernetes-auth"}},
    }
    prov = InfisicalProvider(auth=KubernetesAuth())
    wrap = prov.exec_wrap(
        _ctx(tmp_path, config=cfg, mount=None), want_secrets=True
    )  # no mount needed
    script = wrap.argv_prefix[2]
    assert "cat " not in script and "INFISICAL_TOKEN=" not in script
    assert "infisical run" in script and script.endswith('-- env -u INFISICAL_TOKEN -- "$@"')
    assert prov._token_path is None
    assert not _dir(tmp_path).exists()


def test_two_wraps_write_two_distinct_token_files(home: Path, tmp_path: Path) -> None:
    # Two concurrent `--secret` execs must never share a file (the race the
    # original branch left as a NOTE). One provider per exec is the Target's
    # contract; assert it with two instances.
    ctx = _ctx(tmp_path)
    a = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-a")))
    b = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-b")))

    wrap_a = a.exec_wrap(ctx, want_secrets=True)
    wrap_b = b.exec_wrap(ctx, want_secrets=True)

    files = sorted(_dir(tmp_path).iterdir())
    assert len(files) == 2
    assert {f.read_text() for f in files} == {"tok-a", "tok-b"}
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in files)
    # Each wrap reads its OWN file — the two scripts differ only by file name.
    assert wrap_a.argv_prefix != wrap_b.argv_prefix
    for wrap, tok in ((wrap_a, "tok-a"), (wrap_b, "tok-b")):
        assert not any(tok in a for a in wrap.argv_prefix)


def test_post_exec_unlinks_only_its_own_file(home: Path, tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    a = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-a")))
    b = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("tok-b")))
    a.exec_wrap(ctx, want_secrets=True)
    b.exec_wrap(ctx, want_secrets=True)
    d = _dir(tmp_path)

    a.post_exec(ctx)

    (survivor,) = list(d.iterdir())
    assert survivor.read_text() == "tok-b"  # b's exec is still running
    b.post_exec(ctx)
    assert list(d.iterdir()) == []
    a.post_exec(ctx)  # idempotent — a second call is a no-op, never raises


def test_post_exec_without_wrap_is_a_noop(home: Path, tmp_path: Path) -> None:
    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()))
    prov.post_exec(_ctx(tmp_path))  # no exec happened — nothing to unlink


def test_infisical_exec_wrap_no_secrets_does_not_mint(home: Path, tmp_path: Path) -> None:
    minter = _FakeMinter()
    prov = InfisicalProvider(auth=UniversalAuth(minter=minter))
    assert prov.exec_wrap(_ctx(tmp_path), want_secrets=False) == ExecWrap()
    assert minter.calls == []  # no mint when no secrets requested


def test_infisical_up_prepare_creates_empty_0700_token_dir(home: Path, tmp_path: Path) -> None:
    prov = InfisicalProvider(
        auth=UniversalAuth(minter=_FakeMinter()),
        validate=lambda ctx: None,  # touchpoint checks injected as no-op here
    )
    prov.up_prepare(_ctx(tmp_path))
    d = _dir(tmp_path)
    assert d.is_dir()
    assert list(d.iterdir()) == []  # mount source exists; NO secret at up
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_infisical_up_prepare_fails_when_touchpoint_missing(home: Path, tmp_path: Path) -> None:
    def _boom(ctx: ProfileContext) -> None:
        raise IsolationError("infisical CLI not found in image")

    prov = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter()), validate=_boom)
    with pytest.raises(IsolationError) as ei:
        prov.up_prepare(_ctx(tmp_path))
    assert "infisical CLI" in str(ei.value)


def test_infisical_cleanup_removes_every_leftover_file(home: Path, tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    # Two execs whose post_exec never ran (a crash mid-exec) + a stray file.
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("t1"))).exec_wrap(ctx, True)
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter("t2"))).exec_wrap(ctx, True)
    d = _dir(tmp_path)
    (d / "stray").write_text("x")
    assert len(list(d.iterdir())) == 3

    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).cleanup(ctx)

    assert not d.exists()
    InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).cleanup(ctx)  # idempotent


def test_infisical_exec_wrap_quotes_config_values(home: Path, tmp_path: Path) -> None:
    # A malicious `path` must NOT inject into the in-container shell — shlex.quote
    # neutralizes it (the value comes from PR/branch-reachable fr-profiles.yaml).
    evil = "/fr/x; touch /tmp/pwned"
    cfg = {**INFISICAL_CFG, "infisical": {**INFISICAL_CFG["infisical"], "path": evil}}
    wrap = InfisicalProvider(auth=UniversalAuth(minter=_FakeMinter())).exec_wrap(
        _ctx(tmp_path, config=cfg), want_secrets=True
    )
    script = wrap.argv_prefix[2]  # the `sh -lc` script
    assert shlex.quote(evil) in script  # quoted → the `;` is inert
    assert "--path /fr/x; touch" not in script  # never the raw, injectable form
    # The per-exec container path is quoted too (defensive; the name is ours).
    (tf,) = list(_dir(tmp_path).iterdir())
    assert shlex.quote(f"{CONTAINER_TOKEN_DIR}/{tf.name}") in script
