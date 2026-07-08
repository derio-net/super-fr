"""Tripwire: install.sh must attempt to provision the devcontainer CLI (#328
adjacent follow-up). `fr isolation up` shells out to `devcontainer`
unconditionally; without this step an operator who installs the plugin
still hits a bare "command not found" the first time they run `fr isolation
up`, instead of getting it set up (or a clear warning) during install.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_provisions_devcontainer_cli() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert "devcontainer" in install, (
        "install.sh has no devcontainer-CLI provisioning/warning step — "
        "fr isolation up depends on it and will fail with a cryptic "
        "'command not found' otherwise"
    )
    assert "@devcontainers/cli" in install, (
        "install.sh should install the devcontainer CLI via "
        "'npm install -g @devcontainers/cli' when npm is available"
    )
