"""scripts/install-validator-wrapper.sh repair-path behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_VALIDATOR_WRAPPER = REPO_ROOT / "scripts" / "install-validator-wrapper.sh"


def test_install_validator_wrapper_refuses_custom_validator_that_mentions_super_fr(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    target = repo / "scripts" / "validate-plans.sh"
    target.parent.mkdir()
    target.write_text("#!/usr/bin/env bash\n# custom super-fr validator\nexit 0\n")

    result = subprocess.run(
        ["bash", str(INSTALL_VALIDATOR_WRAPPER)],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not a super-fr wrapper" in result.stderr
    assert target.read_text() == "#!/usr/bin/env bash\n# custom super-fr validator\nexit 0\n"


def test_install_validator_wrapper_refreshes_current_wrapper(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    target = repo / "scripts" / "validate-plans.sh"
    target.parent.mkdir()
    target.write_text(
        "#!/usr/bin/env bash\n"
        "# Thin wrapper — delegates to the canonical validator from the\n"
        "# super-fr plugin installed at the user level.\n"
        'exec "$HOME/.claude/plugins/marketplaces/derio-net--super-fr'
        '/scripts/validate-plans.sh" "$@"\n'
    )

    result = subprocess.run(
        ["bash", str(INSTALL_VALIDATOR_WRAPPER)],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Installed wrapper" in result.stdout
    assert target.stat().st_mode & 0o111


def test_install_validator_wrapper_refreshes_legacy_wrapper(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    target = repo / "scripts" / "validate-plans.sh"
    target.parent.mkdir()
    target.write_text(
        "#!/usr/bin/env bash\n"
        "# superpowers-for-vk wrapper\n"
        'exec "$HOME/.claude/plugins/marketplaces/derio-net--super-fr'
        '/scripts/validate-plans.sh" "$@"\n'
    )

    result = subprocess.run(
        ["bash", str(INSTALL_VALIDATOR_WRAPPER)],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "super-fr plugin" in target.read_text()
