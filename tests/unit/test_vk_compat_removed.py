"""The retired `vk` command's compatibility paths are gone (spec 2026-11-12-remove-vk-compat)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


def test_init_has_no_migrate_command() -> None:
    from fr.commands.init_cmd import init_app

    names = {
        c.name or (c.callback.__name__ if c.callback else "") for c in init_app.registered_commands
    }
    assert "migrate" not in names


def test_isolation_migrate_module_is_gone() -> None:
    assert importlib.util.find_spec("fr.isolation.migrate") is None


# --- Task 2: `fr isolation up` requires --branch ---------------------------------

REPO = Path(__file__).resolve().parents[2]


def test_up_without_branch_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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


# The hooks' comments describe `fr isolation up` in passing; only the text a hook
# EMITS is a remedy, so these are read line by line with comments left out.
EMITTING_HOOKS = [
    "plugins/super-fr/hooks/fr-isolation-required.sh",
    "plugins/super-fr/hooks/fr-isolation-guard.sh",
    "plugins/super-fr/hooks/fr-phase-executor-guard.sh",
    "packages/fr-opencode-plugin/src/guard.ts",
]
_UP = re.compile(r"fr isolation up(?!( --repo \S+)? --branch)")


def _bare_ups(text: str) -> list[str]:
    return [text[m.start() : m.start() + 60] for m in _UP.finditer(text)]


@pytest.mark.parametrize("rel", EMITTING_HOOKS)
def test_no_hook_emits_a_bare_isolation_up(rel: str) -> None:
    code = [
        line
        for line in (REPO / rel).read_text().splitlines()
        if not line.lstrip().startswith(("#", "//", "*", "/*"))
    ]
    assert _bare_ups("\n".join(code)) == []


def test_no_captured_guard_reason_names_a_bare_isolation_up() -> None:
    rows = yaml.safe_load((REPO / "tests/fixtures/hooks/guard-verdicts.yaml").read_text())
    reasons = [r["reason"] for r in rows["rows"] if r.get("reason")]
    assert reasons
    assert [b for reason in reasons for b in _bare_ups(reason)] == []


@pytest.mark.parametrize(
    "rel",
    ["plugins/super-fr/rules/fr-isolation-required.md", ".claude/rules/fr-isolation-required.md"],
)
def test_the_rule_gives_no_isolation_up_command_that_would_refuse(rel: str) -> None:
    text = " ".join((REPO / rel).read_text().split())
    assert "fr isolation up --repo <path> --branch <branch>" in text
    assert "fr isolation up --repo <path>`" not in text


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


# --- Task 4: installer, validator wrapper, bump-version -----------------------------

INSTALL_RETIRED = (
    "vk-plan",
    "vk-dispatch",
    "vk-execute",
    "vk-progress",
    "vk-plan-override",
    "superpowers-for-vk",
    "RETIRED_CLAUDE_RULES",
    "SKILL_NAMES",
)


@pytest.mark.parametrize("needle", INSTALL_RETIRED)
def test_install_sh_names_no_retired_vk_thing(needle: str) -> None:
    assert needle not in (REPO / "scripts/install.sh").read_text()


def test_bump_version_probes_fr_only() -> None:
    text = (REPO / "scripts/bump-version.py").read_text()
    assert '"vk"' not in text
    assert "rebrand" not in text


DELEGATE = 'exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh"\n'


def test_wrapper_needs_super_fr_in_its_text(tmp_path: Path) -> None:
    from fr.plan_validator_wrapper import is_super_fr_validator_wrapper

    old = tmp_path / "a.sh"
    old.write_text("# superpowers-for-vk\n" + DELEGATE)
    assert not is_super_fr_validator_wrapper(old)
    kept = tmp_path / "b.sh"
    kept.write_text("# super-fr\n" + DELEGATE)
    assert is_super_fr_validator_wrapper(kept)


# --- spec 2026-11-14-retire-vibekanban: the fr-vk package is gone ------------------


@pytest.mark.xfail(strict=True, reason="fr-vk still present (P1.T2)")
def test_no_vk_runner_entry_point() -> None:
    from importlib.metadata import entry_points

    assert "vk" not in {ep.name for ep in entry_points(group="fr.runners")}
