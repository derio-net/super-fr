"""CLI tests for `fr repos sync` — instrument checked-out repos in place.

Drives the real `fr.cli.app` via CliRunner. Checkouts are faked as dirs with a
`.git` marker under a monkeypatched `$FR_REPOS_DIR`; the manifest path is
redirected via `$FR_REPOS_MANIFEST`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _checkout(repos_dir: Path, name: str) -> Path:
    root = repos_dir / name
    (root / ".git").mkdir(parents=True)
    return root


@pytest.fixture
def env(tmp_path, monkeypatch):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    manifest = tmp_path / "repos.yaml"
    monkeypatch.setenv("FR_REPOS_DIR", str(repos_dir))
    monkeypatch.setenv("FR_REPOS_MANIFEST", str(manifest))
    return repos_dir, manifest


def _cfg(root: Path) -> Path:
    return root / "docs" / "superpowers" / "plan-config.yaml"


def test_dry_run_is_default_and_writes_nothing(env):
    repos_dir, manifest = env
    root = _checkout(repos_dir, "super-fr")
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr"])
    assert res.exit_code == 0, res.output
    assert "DRY-RUN" in res.output
    assert not _cfg(root).exists()
    # Dry-run must NOT append the arg to the manifest (side-effect gated on --yes).
    assert not manifest.exists()


def test_malformed_arg_warns_and_is_not_persisted(env):
    _, manifest = env
    res = runner.invoke(app, ["repos", "sync", "not-a-repo-ref", "--yes"])
    assert res.exit_code == 0, res.output
    assert "WARN (malformed)" in res.output
    # A malformed ref is never written to the durable manifest.
    assert not manifest.exists()


def test_yes_writes_template(env):
    repos_dir, _ = env
    root = _checkout(repos_dir, "super-fr")
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes"])
    assert res.exit_code == 0, res.output
    assert "WROTE" in res.output
    text = _cfg(root).read_text()
    assert "YYYY-MM-DD-{name}.md" in text
    # Live profile only — no dead keys generated.
    assert "dispatch" not in text
    assert "save_to" not in text


def test_missing_checkout_warns_and_exits_zero(env):
    res = runner.invoke(app, ["repos", "sync", "owner/absent", "--yes"])
    assert res.exit_code == 0, res.output
    assert "WARN" in res.output
    assert "absent" in res.output


def test_existing_config_is_skipped(env):
    repos_dir, _ = env
    root = _checkout(repos_dir, "super-fr")
    cfg = _cfg(root)
    cfg.parent.mkdir(parents=True)
    cfg.write_text("plan:\n  filename: custom\n")
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes"])
    assert res.exit_code == 0, res.output
    assert "SKIP" in res.output
    assert cfg.read_text() == "plan:\n  filename: custom\n"  # untouched


def test_force_overwrites_existing(env):
    repos_dir, _ = env
    root = _checkout(repos_dir, "super-fr")
    cfg = _cfg(root)
    cfg.parent.mkdir(parents=True)
    cfg.write_text("old\n")
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes", "--force"])
    assert res.exit_code == 0, res.output
    assert "WROTE" in res.output
    assert "YYYY-MM-DD-{name}.md" in cfg.read_text()


def test_collection_is_union_of_manifest_and_args(env):
    repos_dir, manifest = env
    a = _checkout(repos_dir, "alpha")
    b = _checkout(repos_dir, "beta")
    manifest.write_text("repos:\n  - owner/alpha\n")
    res = runner.invoke(app, ["repos", "sync", "owner/beta", "--yes"])
    assert res.exit_code == 0, res.output
    assert _cfg(a).exists()
    assert _cfg(b).exists()


def test_union_dedupes_repo_named_in_both(env):
    repos_dir, manifest = env
    _checkout(repos_dir, "alpha")
    manifest.write_text("repos:\n  - owner/alpha\n")
    res = runner.invoke(app, ["repos", "sync", "owner/alpha", "--yes"])
    assert res.exit_code == 0, res.output
    # alpha appears once in the per-repo summary.
    assert res.output.count("owner/alpha") == 1


def test_arg_is_appended_to_manifest(env):
    repos_dir, manifest = env
    _checkout(repos_dir, "alpha")
    res = runner.invoke(app, ["repos", "sync", "owner/alpha", "--yes"])
    assert res.exit_code == 0, res.output
    from fr.repos import load_manifest

    assert "owner/alpha" in [e.repo for e in load_manifest(manifest)]


def test_no_save_suppresses_manifest_append(env):
    repos_dir, manifest = env
    _checkout(repos_dir, "alpha")
    res = runner.invoke(app, ["repos", "sync", "owner/alpha", "--yes", "--no-save"])
    assert res.exit_code == 0, res.output
    assert not manifest.exists()


def test_no_repos_resolved_is_usage_error(env):
    res = runner.invoke(app, ["repos", "sync"])
    assert res.exit_code == 2, res.output
