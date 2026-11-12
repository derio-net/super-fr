"""The retired `vk` command's compatibility paths are gone (spec 2026-11-12-remove-vk-compat)."""

from __future__ import annotations

import importlib.util


def test_smoke() -> None:
    assert True


def test_init_has_no_migrate_command() -> None:
    from fr.commands.init_cmd import init_app

    names = {c.name or (c.callback.__name__ if c.callback else "") for c in init_app.registered_commands}
    assert "migrate" not in names


def test_isolation_migrate_module_is_gone() -> None:
    assert importlib.util.find_spec("fr.isolation.migrate") is None


# --- Task 2: `fr isolation up` requires --branch ---------------------------------

import re  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_up_without_branch_is_a_usage_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fr.commands import isolation_cmd

    calls: list[object] = []

    def boom(*a: object, **k: object) -> object:
        calls.append(a)
        raise AssertionError("runner must not be called")

    monkeypatch.setattr(isolation_cmd, "_runner", boom)
    result = CliRunner().invoke(isolation_cmd.isolation_app, ["up", "--repo", str(tmp_path)])
    assert result.exit_code == 2
    assert "--branch" in (result.output + (result.stderr if result.stderr_bytes else ""))
    assert calls == []


def test_isolation_cmd_has_no_default_branch() -> None:
    from fr.commands import isolation_cmd

    assert not hasattr(isolation_cmd, "DEFAULT_BRANCH")


REMEDY_FILES = [
    "packages/fr/src/fr/commands/isolation_cmd.py",
    "packages/fr/src/fr/isolation/sessions.py",
    "packages/fr/src/fr/isolation/local.py",
    "plugins/super-fr/hooks/hermes/fr-isolation-guard.sh",
    "plugins/super-fr/hooks/hermes/fr-isolation-required.sh",
    "packages/fr-opencode-plugin/src/index.ts",
]


@pytest.mark.parametrize("rel", REMEDY_FILES)
def test_no_bare_isolation_up_remedy(rel: str) -> None:
    text = (REPO / rel).read_text()
    bare = [m.group(0) for m in re.finditer(r"fr isolation up(?=[`'\")]|$)", text, re.M)]
    assert bare == []


# --- Task 3: FR_REPO_ROOT, FR_INSTALL_SKIP_PREFLIGHT -------------------------------


def test_fr_repo_root_is_honoured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fr.commands.common import resolve_repo_root

    monkeypatch.delenv("VK_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_REPO_ROOT", str(tmp_path))
    assert resolve_repo_root() == tmp_path.resolve()


def test_vk_repo_root_is_not_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fr.commands.common import resolve_repo_root

    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    assert resolve_repo_root() != tmp_path.resolve()


def test_empty_fr_repo_root_falls_through_to_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fr.commands.common import resolve_repo_root

    monkeypatch.setenv("FR_REPO_ROOT", "")
    assert resolve_repo_root(REPO) == REPO.resolve()


def test_no_vk_env_names_remain() -> None:
    this = Path(__file__).resolve()
    hits: list[str] = []
    for top in ("packages", "plugins", "scripts", "tests"):
        for path in (REPO / top).rglob("*"):
            if not path.is_file() or path.resolve() == this or "node_modules" in path.parts:
                continue
            if "fixtures/github_rest" in path.as_posix():  # captures are never rewritten
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if "VK_REPO_ROOT" in text or "VK_INSTALL_SKIP_PREFLIGHT" in text:
                hits.append(str(path.relative_to(REPO)))
    assert hits == []
