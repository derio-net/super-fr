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


def test_no_vk_runner_entry_point() -> None:
    from importlib.metadata import entry_points

    assert "vk" not in {ep.name for ep in entry_points(group="fr.runners")}


def test_scaffold_runner_packages_name_no_vk() -> None:
    from fr.isolation import scaffold

    assert "fr-vk" not in scaffold.RUNNER_PACKAGES
    assert "packages/fr-vk" not in scaffold.POST_CREATE


@pytest.mark.parametrize("profile", ["dev", "admin"])
def test_repo_profiles_install_no_vk(profile: str) -> None:
    text = (REPO / ".devcontainer" / profile / "devcontainer.json").read_text()
    assert "packages/fr-vk" not in text


def test_apply_to_vk_is_unknown_runner() -> None:
    # `fr apply --to vk` refuses through `runner_names()` (apply_cmd's unknown-runner
    # path), and the registry's own lookup refuses the name as not installed.
    from fr_dispatch.registry import RunnerLoadError, runner_names, runner_units

    assert "vk" not in runner_names()
    with pytest.raises(RunnerLoadError, match="not installed"):
        runner_units("vk")


# --- spec 2026-11-14-retire-vibekanban R10: no VK residue in shipped sources --------

_VK_NEEDLE = re.compile(r"fr_vk|fr-vk|vibe_kanban|vibe.?kanban", re.IGNORECASE)
_RUNNER_NEEDLE = re.compile(r"fr-runner", re.IGNORECASE)
_VK_TOP_FILES = ("pyproject.toml", "HERMES.md")
_VK_TOP_DIRS = ("plugins", "scripts", ".devcontainer", ".github", ".fr")
_RUNNER_PREFIXES = ("plugins/", "scripts/", "packages/fr/src/fr/commands/")

# (path, line regex): the only lines that may still name VK. Each one is kept on
# purpose; an entry that matches no line fails
# test_vk_residue_allowlist_has_no_dead_entries, so none outlives what it excuses.
ALLOWED: tuple[tuple[str, str], ...] = (
    # R4: the detection string for a profile scaffolded before the removal, and the
    # refusal that names it; the comment above it cites this spec by slug.
    ("packages/fr/src/fr/isolation/local.py", r"^# 2026-11-14-retire-vibekanban R4\)\.$"),
    (
        "packages/fr/src/fr/isolation/local.py",
        r'^_VK_PROFILE_NEEDLE = "subdirectory=packages/fr-vk"$',
    ),
    (
        "packages/fr/src/fr/isolation/local.py",
        r"Refuse a devcontainer config that still installs fr-vk,",
    ),
    (
        "packages/fr/src/fr/isolation/local.py",
        r'f"\{config\} installs fr-vk, but VK support was removed',
    ),
    # R5: the installer removes what earlier installs wrote for the VK runner (the
    # vibe_kanban MCP entry, an fr-written bridge wrapper) and refuses --install-bridge.
    ("scripts/install.sh", r"^# Earlier installs wrote these for the VibeKanban runner,"),
    ("scripts/install.sh", r"^# 2026-11-14-retire-vibekanban R5\)\."),
    ("scripts/install.sh", r"jq -e '\.mcpServers\.vibe_kanban'"),
    ("scripts/install.sh", r"jq 'del\(\.mcpServers\.vibe_kanban\)'"),
    ("scripts/install.sh", r'echo "  Removed vibe_kanban \(VibeKanban support was removed\)'),
    ("scripts/install.sh", r"^  # `install\.sh --install-bridge` wrote: exec .* -m fr_vk\.bridge"),
    ("scripts/install.sh", r"grep -qE '\^exec \.\*-m fr_vk\\\.bridge"),
    ("scripts/install.sh", r'echo "  Removed \$vk_wrapper \(VibeKanban support was removed\)"'),
    (
        "scripts/install.sh",
        r'echo "VibeKanban support was removed; there is no bridge to install\."',
    ),
    ("scripts/install.sh", r"^# 8\. Remove what earlier installs wrote for the VibeKanban runner"),
    # R9: the staleness guard's docstring cites this spec by slug.
    (
        "packages/fr/src/fr/acceptance/check.py",
        r"Plan's outcome \(spec 2026-11-14-retire-vibekanban R9\)",
    ),
)


def _vk_scanned(rel: str) -> bool:
    parts = rel.split("/")
    if rel in _VK_TOP_FILES or parts[0] in _VK_TOP_DIRS:
        return True
    return len(parts) > 3 and parts[0] == "packages" and parts[2] == "src"


def _vk_residue(
    root: Path, rels: list[str], allowed: tuple[tuple[str, str], ...] = ALLOWED
) -> list[str]:
    """Every scanned line naming VK (or fr-runner where it is banned) that no
    (path, regex) pair in *allowed* excuses, as `path:line: text`."""
    hits: list[str] = []
    for rel in sorted(rels):
        pats = [re.compile(p) for path, p in allowed if path == rel]
        for n, line in _flagged(root, rel):
            if not any(p.search(line) for p in pats):
                hits.append(f"{rel}:{n}: {line.strip()[:120]}")
    return hits


def _flagged(root: Path, rel: str) -> list[tuple[int, str]]:
    """The lines of *rel* the residue scan flags before any allowlist applies: VK
    names in a scanned root, `fr-runner` under the runner prefixes."""
    vk = _vk_scanned(rel)
    runner = rel.startswith(_RUNNER_PREFIXES)
    if not (vk or runner):
        return []
    try:
        lines = (root / rel).read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []
    return [
        (n, line)
        for n, line in enumerate(lines, 1)
        if (vk and _VK_NEEDLE.search(line)) or (runner and _RUNNER_NEEDLE.search(line))
    ]


def _tracked() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode()
    return [p for p in out.split("\0") if p]


def test_no_vk_residue_in_shipped_sources() -> None:
    assert _vk_residue(REPO, _tracked()) == []


def _dead_entries(
    root: Path, rels: list[str], allowed: tuple[tuple[str, str], ...]
) -> list[tuple[str, str]]:
    """The (path, regex) pairs in *allowed* that excuse no line `_vk_residue` would
    flag: a path that is untracked or unscanned, or a regex that matches only lines
    the scan never flags (an `fr-runner` line outside the runner prefixes)."""
    tracked = set(rels)
    dead = []
    for rel, pat in allowed:
        flagged = _flagged(root, rel) if rel in tracked else []
        if not any(re.search(pat, line) for _, line in flagged):
            dead.append((rel, pat))
    return dead


def test_vk_residue_allowlist_has_no_dead_entries() -> None:
    assert _dead_entries(REPO, _tracked(), ALLOWED) == []


def _plant(tmp_path: Path, rel: str, text: str) -> list[str]:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return [rel]


def test_vk_residue_fails_on_a_planted_fr_vk_line(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "packages/fr/src/fr/x.py", "import fr_vk\n")
    assert _vk_residue(tmp_path, rels) == ["packages/fr/src/fr/x.py:1: import fr_vk"]


def test_vk_residue_fails_on_a_planted_vibekanban_line_in_plugins(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "plugins/p/SKILL.md", "ok\nthe VibeKanban adapter\n")
    assert _vk_residue(tmp_path, rels) == ["plugins/p/SKILL.md:2: the VibeKanban adapter"]


def test_vk_residue_fails_on_fr_runner_only_where_it_is_banned(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "scripts/x.yaml", "fr-runner: x\n")
    rels += _plant(tmp_path, "packages/fr/src/fr/y.py", "# fr-runner\n")
    assert _vk_residue(tmp_path, rels) == ["scripts/x.yaml:1: fr-runner: x"]


def test_vk_residue_skips_unscanned_roots(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "docs/x.md", "fr_vk\n") + _plant(tmp_path, "tests/y.py", "fr_vk\n")
    assert _vk_residue(tmp_path, rels) == []


def test_vk_residue_passes_an_allowlisted_line_only(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "scripts/a.sh", "keep fr_vk here\ndrop fr_vk here\n")
    allowed = (("scripts/a.sh", r"^keep fr_vk"),)
    assert _vk_residue(tmp_path, rels, allowed) == ["scripts/a.sh:2: drop fr_vk here"]


def test_dead_entries_reports_an_entry_the_scan_never_flags(tmp_path: Path) -> None:
    rels = _plant(tmp_path, "scripts/a.sh", "keep fr_vk here\n")
    rels += _plant(tmp_path, "docs/x.md", "fr_vk in an unscanned root\n")
    rels += _plant(tmp_path, "packages/fr/src/fr/y.py", "# fr-runner outside the runner prefixes\n")
    live = ("scripts/a.sh", r"^keep fr_vk")
    unscanned = ("docs/x.md", r"fr_vk")
    unbanned = ("packages/fr/src/fr/y.py", r"fr-runner")
    missing = ("scripts/gone.sh", r"fr_vk")
    allowed = (live, unscanned, unbanned, missing)
    assert _dead_entries(tmp_path, rels, allowed) == [unscanned, unbanned, missing]


# --- spec 2026-11-14-retire-vibekanban R6/R8: nothing advertises fr-runner or VK ---


def test_fr_skills_lists_no_fr_runner(capsys: pytest.CaptureFixture[str]) -> None:
    from fr.commands import skills_cmd

    skills_cmd.skills()
    out = capsys.readouterr().out
    assert "fr-dispatch" in out
    assert "fr-runner" not in out


def test_no_shipped_skill_is_fr_runner() -> None:
    assert sorted(REPO.glob("plugins/*/skills/fr-runner")) == []
    assert "fr-runner" not in (REPO / "README.md").read_text()


def test_published_pages_name_no_vk_runner() -> None:
    from fr.docs.load import load_config, load_pages

    config = load_config(REPO)
    assert config is not None
    pages, errors = load_pages(REPO, config, _tracked())
    assert errors == []
    assert pages
    # install.md names the vibe_kanban MCP entry the installer removes: that is not a runner.
    banned = re.compile(r"fr-runner|fr_vk|--to vk\b|runner:vk\b", re.IGNORECASE)
    hits = [
        f"{p.path}:{n}"
        for p in pages
        for n, line in enumerate((REPO / p.path).read_text().splitlines(), 1)
        if banned.search(line)
    ]
    assert hits == []
