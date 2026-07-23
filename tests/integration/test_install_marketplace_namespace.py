"""install.sh must own the `derio-net` marketplace namespace defensively.

Root cause (docs/superpowers/journals/debug/2026-07-23-marketplace-config-clobber.md):
a Claude Code marketplace name is a 1:1 namespace over ONE source repo — its
manifest at `plugins/marketplaces/<name>/.claude-plugin/marketplace.json` is a
single file listing every plugin of that marketplace.  super-fr and the sibling
`blog-craft` repo both claimed `derio-net` and both populated the shared
directory with `rsync -a --delete <own repo root>/`, so whichever installer ran
last evicted the other's plugins from the manifest while their `enabledPlugins`
and `installed_plugins.json` entries survived as dangling references.

blog-craft moves to its own `blog-craft` marketplace (the name its own manifest
already declares).  super-fr keeps `derio-net` — it is the self-consistent
owner — and gains the three guards pinned here:

1. it writes its own registry keys unconditionally, so a wrong `source.repo`
   left behind by another repo is corrected rather than preserved;
2. it warns before reclaiming a directory a foreign manifest occupies, instead
   of silently `--delete`-ing it;
3. it reports `*@derio-net` plugin entries that its own marketplace manifest
   does not list — without deleting them, since they belong to another repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.test_install_sh import (  # noqa: F401  (fake_home is a fixture)
    REPO_ROOT,
    _run_install,
    fake_home,
)

MARKETPLACE_NAME = "derio-net"


def _marketplace_manifest() -> dict:
    return json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())


@pytest.fixture()
def home_with_plugin_state(fake_home: Path) -> Path:  # noqa: F811
    """fake_home plus the plugin JSON files install.sh reads and rewrites."""
    plugins = fake_home / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {}, "version": 2}))
    (plugins / "known_marketplaces.json").write_text(json.dumps({}))
    (fake_home / ".claude" / "settings.json").write_text(json.dumps({}))
    return fake_home


def _known_marketplaces(home: Path) -> dict:
    return json.loads((home / ".claude" / "plugins" / "known_marketplaces.json").read_text())


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def _installed(home: Path) -> dict:
    return json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())


def _squat_registry(home: Path) -> None:
    """Pre-seed the registry as if blog-craft's installer had run first."""
    plugins = home / ".claude" / "plugins"
    (plugins / "known_marketplaces.json").write_text(
        json.dumps(
            {
                MARKETPLACE_NAME: {
                    "source": {"source": "github", "repo": "derio-net/blog-craft"},
                    "installLocation": str(plugins / "marketplaces" / MARKETPLACE_NAME),
                }
            }
        )
    )
    (home / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "extraKnownMarketplaces": {
                    MARKETPLACE_NAME: {
                        "source": {"source": "github", "repo": "derio-net/blog-craft"}
                    }
                },
                "enabledPlugins": {"blog-craft@derio-net": True},
            }
        )
    )


# ── Guard 1: own the registry pointer, don't defer to a squatter ──────


class TestRegistrySourceAuthority:
    """`if ! jq -e ...` (skip-if-present) let the FIRST repo to register
    `derio-net` own `source.repo` forever.  A later
    `/plugin marketplace update derio-net` then re-fetches that repo and evicts
    super-fr with no installer run at all.  install.sh must (re)assert its own
    source every time."""

    def test_corrects_wrong_source_in_known_marketplaces(
        self, home_with_plugin_state: Path
    ) -> None:
        _squat_registry(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        entry = _known_marketplaces(home_with_plugin_state)[MARKETPLACE_NAME]
        assert entry["source"]["repo"] == "derio-net/super-fr", (
            "install.sh must reclaim derio-net -> derio-net/super-fr, "
            f"got {entry['source']['repo']}"
        )
        assert entry["installLocation"].endswith(f"/marketplaces/{MARKETPLACE_NAME}")

    def test_corrects_wrong_source_in_extra_known_marketplaces(
        self, home_with_plugin_state: Path
    ) -> None:
        _squat_registry(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        source = _settings(home_with_plugin_state)["extraKnownMarketplaces"][MARKETPLACE_NAME][
            "source"
        ]
        assert source["repo"] == "derio-net/super-fr", (
            f"settings.json must point derio-net at super-fr, got {source['repo']}"
        )

    def test_leaves_other_marketplaces_untouched(self, home_with_plugin_state: Path) -> None:
        """Reasserting our own key must not disturb anyone else's."""
        plugins = home_with_plugin_state / ".claude" / "plugins"
        (plugins / "known_marketplaces.json").write_text(
            json.dumps(
                {
                    "blog-craft": {
                        "source": {"source": "github", "repo": "derio-net/blog-craft"},
                        "installLocation": "/somewhere/blog-craft",
                    }
                }
            )
        )

        _run_install(home_with_plugin_state)

        km = _known_marketplaces(home_with_plugin_state)
        assert km["blog-craft"]["source"]["repo"] == "derio-net/blog-craft"
        assert km["blog-craft"]["installLocation"] == "/somewhere/blog-craft"
        assert km[MARKETPLACE_NAME]["source"]["repo"] == "derio-net/super-fr"


# ── Guard 2: warn before reclaiming a squatted directory ──────────────


class TestForeignOccupantWarning:
    """`rsync --delete` into the shared marketplace dir is what actually evicts
    the other repo.  We still reclaim (super-fr owns the name), but the operator
    must be told, by name, whose plugins just stopped resolving."""

    def _plant_foreign_manifest(self, home: Path, name: str = "blog-craft") -> Path:
        manifest = (
            home
            / ".claude"
            / "plugins"
            / "marketplaces"
            / MARKETPLACE_NAME
            / ".claude-plugin"
            / "marketplace.json"
        )
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps(
                {
                    "name": name,
                    "description": "squatter",
                    "owner": {"name": "someone"},
                    "plugins": [{"name": name, "version": "0.1.0", "source": "./"}],
                }
            )
        )
        return manifest

    def test_warns_when_foreign_manifest_occupies_marketplace_dir(
        self, home_with_plugin_state: Path
    ) -> None:
        self._plant_foreign_manifest(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        combined = result.stdout + result.stderr
        assert "WARNING" in combined
        assert "blog-craft" in combined, (
            f"the squatting marketplace must be named in the warning:\n{combined}"
        )
        assert MARKETPLACE_NAME in combined

    def test_reclaims_the_directory_despite_the_warning(self, home_with_plugin_state: Path) -> None:
        """The warning is advisory — super-fr owns `derio-net` and must still
        install, or a squat would permanently break super-fr installs."""
        manifest = self._plant_foreign_manifest(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        assert json.loads(manifest.read_text())["name"] == MARKETPLACE_NAME
        listed = {p["name"] for p in json.loads(manifest.read_text())["plugins"]}
        assert listed == {"super-fr", "super-fr-dispatch"}

    def test_no_warning_on_a_clean_or_self_owned_directory(
        self, home_with_plugin_state: Path
    ) -> None:
        """Reinstalling over our own manifest must stay quiet — a warning that
        fires every run is a warning nobody reads."""
        _run_install(home_with_plugin_state)
        result = _run_install(home_with_plugin_state)

        combined = result.stdout + result.stderr
        assert "foreign" not in combined.lower()
        assert "squat" not in combined.lower()


# ── Guard 3: report (never delete) orphaned @derio-net entries ─────────


class TestOrphanedPluginEntryReport:
    """After we reclaim the manifest, any `X@derio-net` still registered whose
    name our manifest does not list can never resolve.  Report it; deleting it
    would be super-fr reaching into another repo's install state."""

    def _register_orphan(self, home: Path) -> None:
        plugins = home / ".claude" / "plugins"
        (plugins / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "blog-craft@derio-net": [
                            {
                                "scope": "user",
                                "installPath": str(
                                    plugins / "cache" / "derio-net" / "blog-craft" / "current"
                                ),
                                "version": "0.10.0",
                                "installedAt": "2026-07-20T17:51:38.000Z",
                                "lastUpdated": "2026-07-20T17:51:38.000Z",
                            }
                        ]
                    },
                }
            )
        )
        (home / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"blog-craft@derio-net": True}})
        )

    def test_reports_orphaned_entry_by_name(self, home_with_plugin_state: Path) -> None:
        self._register_orphan(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        combined = result.stdout + result.stderr
        assert "blog-craft@derio-net" in combined, (
            f"orphaned plugin entry must be reported by id:\n{combined}"
        )

    def test_does_not_delete_the_orphaned_entry(self, home_with_plugin_state: Path) -> None:
        self._register_orphan(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        installed = _installed(home_with_plugin_state)["plugins"]
        assert "blog-craft@derio-net" in installed, (
            "super-fr must not delete another repo's plugin registration"
        )
        enabled = _settings(home_with_plugin_state)["enabledPlugins"]
        assert enabled.get("blog-craft@derio-net") is True

    def test_silent_when_only_our_own_plugins_are_registered(
        self, home_with_plugin_state: Path
    ) -> None:
        _run_install(home_with_plugin_state)
        result = _run_install(home_with_plugin_state)

        assert "orphan" not in (result.stdout + result.stderr).lower()

    def test_our_own_plugin_names_come_from_the_manifest(self) -> None:
        """The orphan check compares against `.claude-plugin/marketplace.json`,
        so the manifest and the installer's PLUGIN_NAMES must not drift."""
        manifest_names = {p["name"] for p in _marketplace_manifest()["plugins"]}
        script = (REPO_ROOT / "scripts" / "install.sh").read_text()
        assert "PLUGIN_NAMES=(super-fr super-fr-dispatch)" in script
        assert manifest_names == {"super-fr", "super-fr-dispatch"}


# ── The name itself is the namespace ──────────────────────────────────


def test_marketplace_manifest_name_matches_the_directory_we_claim() -> None:
    """The self-consistency that makes super-fr the rightful owner of
    `derio-net`: our manifest declares that same name.  blog-craft's declares
    `blog-craft`, which is why it moves off this namespace rather than us."""
    assert _marketplace_manifest()["name"] == MARKETPLACE_NAME
    script = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert f'MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/{MARKETPLACE_NAME}"' in script
    assert f'CACHE_BASE="$CLAUDE_DIR/plugins/cache/{MARKETPLACE_NAME}"' in script
