"""A sandboxed install test for OpenCode agents with model resolution.

The installation test demonstrates that install.sh delivers four OpenCode
agents to the global ~/.config/opencode/agent/ directory with `model:` resolved
from the operator's own `fr models` bindings. It follows the precedent of
tests/integration/test_install_marketplace_namespace.py for sandboxing,
using HOME and XDG_CONFIG_HOME to isolate the test from the operator's real
config.

Verified:
1. The four agent files land in <config>/opencode/agent/
2. A resolved binding appears as `model:` on each TIER file and NOT on the
   base file, immediately after the `mode: subagent` anchor — and an unbound
   tier carries no `model:` key at all
3. `--uninstall` removes exactly those files while leaving an unrelated,
   operator-owned agent file in the same directory untouched

Point 2 is covered by the r-p3-f1 block at the foot of this file. It was
claimed here before anything asserted it; see that block for why that
mattered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_install_sh import (  # noqa: F401  (fake_home is a fixture)
    REPO_ROOT,
    _run_install,
    fake_home,
)


@pytest.fixture()
def home_with_opencode_config(fake_home: Path) -> Path:  # noqa: F811
    """fake_home with XDG_CONFIG_HOME pointing to a temp dir, and an
    existing ~/.config/opencode to trigger agent delivery."""
    config_home = fake_home / ".config"
    config_home.mkdir(parents=True)
    (config_home / "opencode").mkdir()
    return fake_home


def test_install_delivers_four_agents_to_opencode_dir(
    home_with_opencode_config: Path,
) -> None:
    """Install places all four agents (base + three tiers) in ~/.config/opencode/agent/."""
    _run_install(home_with_opencode_config)

    agent_dir = home_with_opencode_config / ".config" / "opencode" / "agent"
    assert agent_dir.exists(), f"Agent directory {agent_dir} was not created"

    agent_files = sorted(agent_dir.glob("*.md"))
    # Alphabetical order: '-' (ASCII 45) comes before '.' (ASCII 46), so tiered
    # agents sort before the base agent
    expected_agents = [
        "fr-phase-executor-hard.md",
        "fr-phase-executor-mechanical.md",
        "fr-phase-executor-standard.md",
        "fr-phase-executor.md",
    ]
    actual_names = sorted(f.name for f in agent_files)
    assert actual_names == expected_agents, f"Expected agents {expected_agents}, got {actual_names}"


def test_no_model_is_pinned_when_fr_is_not_on_path_at_all(
    home_with_opencode_config: Path,
) -> None:
    """With no `fr` on PATH, resolution yields nothing and every agent — tiered
    or not — is delivered without a `model:` key, inheriting the session model.

    This is the DEGRADATION path only. It was once the sole model-related test
    here, described as "expected behavior for stubbed tests", which read as
    coverage while asserting that the feature does nothing. The positive path
    lives in the r-p3-f1 block below."""
    _run_install(home_with_opencode_config)

    agent_dir = home_with_opencode_config / ".config" / "opencode" / "agent"

    # All agents (including tiered ones) should lack 'model:' keys when fr is
    # not available for resolving them.
    for agent_file in agent_dir.glob("*.md"):
        content = agent_file.read_text()
        assert not any(line.strip().startswith("model:") for line in content.split("\n")), (
            f"{agent_file.name} should not have a model: line "
            "when fr is not available for resolution"
        )


def test_agent_frontmatter_has_mode_subagent_on_own_line(
    home_with_opencode_config: Path,
) -> None:
    """Agent frontmatter must have `mode: subagent` on its own line,
    so that install.sh can anchor model: insertion after it."""
    _run_install(home_with_opencode_config)

    agent_dir = home_with_opencode_config / ".config" / "opencode" / "agent"

    # Check all installed agents have the required structure
    for agent_file in agent_dir.glob("*.md"):
        content = agent_file.read_text()
        lines = content.split("\n")

        # Find 'mode: subagent' line
        mode_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "mode: subagent":
                mode_idx = i
                break

        assert mode_idx is not None, f"{agent_file.name}: mode: subagent line not found"
        # Check that mode: subagent is on its own line (required for install.sh anchor)
        assert lines[mode_idx].strip() == "mode: subagent", (
            f"{agent_file.name}: mode: subagent must be on its own line"
        )


def test_uninstall_removes_only_super_fr_agents(
    home_with_opencode_config: Path,
) -> None:
    """install.sh --uninstall removes the four agent files super-fr ships
    but leaves unrelated operator-owned agent files untouched."""
    config_home = home_with_opencode_config / ".config"
    agent_dir = config_home / "opencode" / "agent"

    # Pre-seed with an operator-owned agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    operator_agent = agent_dir / "my-custom-agent.md"
    operator_agent.write_text("---\nmode: subagent\n---\nOperator's own agent")

    _run_install(home_with_opencode_config, xdg_config_home=config_home)

    # Verify agents were installed
    assert (agent_dir / "fr-phase-executor.md").exists()
    assert (agent_dir / "fr-phase-executor-standard.md").exists()

    # Now uninstall using _run_install with --uninstall flag
    _run_install(home_with_opencode_config, "--uninstall", xdg_config_home=config_home)

    # All super-fr agents should be removed
    assert not (agent_dir / "fr-phase-executor.md").exists()
    assert not (agent_dir / "fr-phase-executor-mechanical.md").exists()
    assert not (agent_dir / "fr-phase-executor-standard.md").exists()
    assert not (agent_dir / "fr-phase-executor-hard.md").exists()

    # Operator's agent should still be there
    assert operator_agent.exists()
    assert operator_agent.read_text() == "---\nmode: subagent\n---\nOperator's own agent"


# ── review r-p3-f1: the positive path had no test at all ─────────────────
#
# This module's docstring claimed "a seeded ~/.config/fr/models.yaml binding
# appears as `model:` on each TIER file and NOT on the base file". Nothing
# asserted it. The only model-related test asserted the OPPOSITE — no model
# anywhere — and explained that away as "expected behavior for stubbed
# tests", which turned a coverage hole into a documented feature. So
# install.sh's awk rewrite, the entire point of the phase, had never once
# been executed with a non-empty model, and could have been broken outright
# with every test still green.
#
# `fr models resolve`'s own correctness is unit-tested in fr. What install.sh
# owes is narrower and is what these tests pin: that it CALLS it, once per
# tier with the right arguments, and inserts what comes back in the one place
# the generator promises the anchor will be.


def _stub_fr(home: Path, models: dict[str, str]) -> Path:
    """Put an `fr` on PATH that answers `models resolve --harness opencode
    --tier <t>`, and logs every argv it was called with.

    The parameter is `home`, not `fake_home`: that name is an imported
    fixture in this module and shadowing it here would make the helper look
    like a second fixture definition (ruff F811).
    """
    log = home / "fr-calls.log"
    cases = "\n".join(f'    {tier}) echo "{model}" ;;' for tier, model in sorted(models.items()))
    stub = home / "bin" / "fr"
    stub.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> "{log}"\n'
        'if [ "$1" = "models" ] && [ "$2" = "resolve" ]; then\n'
        '  tier=""\n'
        "  while [ $# -gt 0 ]; do\n"
        '    [ "$1" = "--tier" ] && tier="$2"\n'
        "    shift\n"
        "  done\n"
        '  case "$tier" in\n'
        f"{cases}\n"
        "    *) : ;;\n"  # unbound tier: print nothing, exit 0 — fr's real contract
        "  esac\n"
        "fi\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    return log


def test_a_resolved_binding_lands_as_model_on_each_tier_file_only(
    home_with_opencode_config: Path,
) -> None:
    models = {
        "mechanical": "provider/small-model",
        "standard": "provider/mid-model",
        "hard": "provider/big-model",
    }
    _stub_fr(home_with_opencode_config, models)

    _run_install(home_with_opencode_config)

    agent_dir = home_with_opencode_config / ".config" / "opencode" / "agent"

    for tier, model in models.items():
        lines = (agent_dir / f"fr-phase-executor-{tier}.md").read_text().splitlines()
        assert f"model: {model}" in lines, f"{tier}: resolved model never reached the file"
        # The layout contract: `model:` sits immediately after `mode: subagent`,
        # because that is the anchor install.sh rewrites against (spec §3.C).
        anchor = lines.index("mode: subagent")
        assert lines[anchor + 1] == f"model: {model}", (
            f"{tier}: model: must follow `mode: subagent` directly, got {lines[anchor + 1]!r}"
        )
        assert sum(1 for line in lines if line.startswith("model:")) == 1, (
            f"{tier}: exactly one model: line expected"
        )

    base = (agent_dir / "fr-phase-executor.md").read_text()
    assert not any(line.startswith("model:") for line in base.splitlines()), (
        "the untiered base agent must inherit the session model, never pin one"
    )


def test_install_asks_fr_for_every_tier_and_only_for_tiers(
    home_with_opencode_config: Path,
) -> None:
    log = _stub_fr(home_with_opencode_config, {"standard": "provider/mid-model"})

    _run_install(home_with_opencode_config)

    resolves = [line for line in log.read_text().splitlines() if line.startswith("models resolve")]
    tiers_asked = sorted(line.split("--tier ")[1].split()[0] for line in resolves)
    assert tiers_asked == ["hard", "mechanical", "standard"], (
        f"expected one resolve per tier and none for the base agent, got {tiers_asked}"
    )
    for line in resolves:
        assert "--harness opencode" in line, f"wrong harness in: {line}"


def test_an_unbound_tier_inherits_rather_than_pinning_an_empty_model(
    home_with_opencode_config: Path,
) -> None:
    """`fr models resolve` prints nothing and exits 0 when unbound. Empty means
    inherit — the key is omitted, never written empty for OpenCode to fail on."""
    _stub_fr(home_with_opencode_config, {"hard": "provider/big-model"})

    _run_install(home_with_opencode_config)

    agent_dir = home_with_opencode_config / ".config" / "opencode" / "agent"
    assert "model: provider/big-model" in (agent_dir / "fr-phase-executor-hard.md").read_text()
    for unbound in ("mechanical", "standard"):
        lines = (agent_dir / f"fr-phase-executor-{unbound}.md").read_text().splitlines()
        assert not any(line.startswith("model:") for line in lines), (
            f"{unbound} is unbound — it must carry no model: key at all"
        )
