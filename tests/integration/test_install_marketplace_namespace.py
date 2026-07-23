"""A marketplace name is `<org>--<repo>`, and the bare org name is retired.

Root cause (docs/superpowers/journals/debug/2026-07-23-marketplace-config-clobber.md):
a Claude Code marketplace name is a 1:1 namespace over ONE source repo — its
manifest at `plugins/marketplaces/<name>/.claude-plugin/marketplace.json` is a
single file listing every plugin of that marketplace, and each installer
populates it with `rsync -a --delete <own repo root>/`.  super-fr and the
sibling `blog-craft` repo both claimed the bare org name `derio-net`, so
whichever installer ran last evicted the other's plugins from the manifest
while their `enabledPlugins` / `installed_plugins.json` entries survived as
dangling references.

The fix is not to award `derio-net` to a winner but to **retire** it: super-fr
installs as `derio-net--super-fr`, blog-craft as `derio-net--blog-craft`, and
both installers purge the bare name on sight.  No repo owns an org-level
namespace, which closes the same trap for every future derio-net plugin, and
`<org>--<repo>` makes the 1:1 rule self-documenting.

Pinned here:

1. registry keys for our own name are written unconditionally, so a wrong
   `source.repo` is corrected rather than preserved;
2. the retired `derio-net` marketplace is purged wholesale — key, directory,
   cache, and every `*@derio-net` id — because with no owner left they are all
   dangling by definition;
3. a foreign manifest squatting our directory is named, not silently evicted;
4. `*@derio-net--super-fr` ids our own manifest doesn't list are reported, not
   silently deleted.
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

MARKETPLACE_NAME = "derio-net--super-fr"
LEGACY_NAME = "derio-net"
OWN_IDS = (f"super-fr@{MARKETPLACE_NAME}", f"super-fr-dispatch@{MARKETPLACE_NAME}")


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


def _known(home: Path) -> dict:
    return json.loads((home / ".claude" / "plugins" / "known_marketplaces.json").read_text())


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def _installed(home: Path) -> dict:
    return json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())


def _seed_legacy(home: Path, *, with_sibling: bool = True) -> None:
    """Pre-seed a machine as the old installers left it: everything under the
    shared bare-org `derio-net` marketplace, including blog-craft's squat."""
    plugins = home / ".claude" / "plugins"
    (plugins / "known_marketplaces.json").write_text(
        json.dumps(
            {
                LEGACY_NAME: {
                    "source": {"source": "github", "repo": "derio-net/blog-craft"},
                    "installLocation": str(plugins / "marketplaces" / LEGACY_NAME),
                },
                "thedotmack": {
                    "source": {"source": "github", "repo": "thedotmack/claude-mem"},
                    "installLocation": "/elsewhere/thedotmack",
                },
            }
        )
    )
    enabled = {
        "super-fr@derio-net": True,
        "super-fr-dispatch@derio-net": True,
        "superpowers-for-vk@derio-net": True,
        "claude-mem@thedotmack": True,
    }
    registered = {
        "super-fr@derio-net": [{"scope": "user", "version": "3.12.0"}],
        "claude-mem@thedotmack": [{"scope": "user", "version": "10.6.3"}],
    }
    if with_sibling:
        enabled["blog-craft@derio-net"] = True
        registered["blog-craft@derio-net"] = [{"scope": "user", "version": "0.10.0"}]
    (home / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "extraKnownMarketplaces": {
                    LEGACY_NAME: {"source": {"source": "github", "repo": "derio-net/blog-craft"}},
                    "thedotmack": {"source": {"source": "github", "repo": "thedotmack/claude-mem"}},
                },
                "enabledPlugins": enabled,
            }
        )
    )
    (plugins / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": registered})
    )
    manifest = plugins / "marketplaces" / LEGACY_NAME / ".claude-plugin" / "marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "blog-craft", "plugins": []}))
    (plugins / "cache" / LEGACY_NAME / "super-fr" / "3.12.0").mkdir(parents=True)


# ── The name encodes org AND repo ─────────────────────────────────────


def test_manifest_name_encodes_org_and_repo() -> None:
    """`<org>--<repo>`: the bare org name is a namespace two repos can claim,
    which is exactly how the eviction bug happened."""
    assert _marketplace_manifest()["name"] == MARKETPLACE_NAME
    script = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert f'MARKETPLACE_NAME="{MARKETPLACE_NAME}"' in script
    assert 'MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/$MARKETPLACE_NAME"' in script
    assert 'CACHE_BASE="$CLAUDE_DIR/plugins/cache/$MARKETPLACE_NAME"' in script


class TestInstallsUnderOwnName:
    def test_registers_its_own_marketplace_key(self, home_with_plugin_state: Path) -> None:
        _run_install(home_with_plugin_state)

        entry = _known(home_with_plugin_state)[MARKETPLACE_NAME]
        assert entry["source"] == {"source": "github", "repo": "derio-net/super-fr"}
        assert entry["installLocation"].endswith(f"/marketplaces/{MARKETPLACE_NAME}")

        source = _settings(home_with_plugin_state)["extraKnownMarketplaces"][MARKETPLACE_NAME]
        assert source["source"] == {"source": "github", "repo": "derio-net/super-fr"}

    def test_plugin_ids_are_namespaced_to_the_new_name(self, home_with_plugin_state: Path) -> None:
        _run_install(home_with_plugin_state)

        installed = _installed(home_with_plugin_state)["plugins"]
        enabled = _settings(home_with_plugin_state)["enabledPlugins"]
        for plugin_id in OWN_IDS:
            assert plugin_id in installed
            assert enabled[plugin_id] is True
            assert installed[plugin_id][0]["installPath"].endswith(
                f"/cache/{MARKETPLACE_NAME}/{plugin_id.split('@')[0]}/current"
            )

    def test_writes_its_tree_into_its_own_marketplace_dir(
        self, home_with_plugin_state: Path
    ) -> None:
        _run_install(home_with_plugin_state)

        manifest = (
            home_with_plugin_state
            / ".claude"
            / "plugins"
            / "marketplaces"
            / MARKETPLACE_NAME
            / ".claude-plugin"
            / "marketplace.json"
        )
        data = json.loads(manifest.read_text())
        assert data["name"] == MARKETPLACE_NAME
        assert {p["name"] for p in data["plugins"]} == {"super-fr", "super-fr-dispatch"}


class TestRegistryWriteIsUnconditional:
    """`if ! jq -e '."<key>"'` reads as idempotence but means first-writer-wins:
    a wrong `source.repo` survives every reinstall, and a later
    `/plugin marketplace update` re-fetches the wrong repo."""

    def test_corrects_a_wrong_source_on_our_own_key(self, home_with_plugin_state: Path) -> None:
        plugins = home_with_plugin_state / ".claude" / "plugins"
        (plugins / "known_marketplaces.json").write_text(
            json.dumps(
                {
                    MARKETPLACE_NAME: {
                        "source": {"source": "directory", "path": "/stale/checkout"},
                        "installLocation": "/stale/checkout",
                    }
                }
            )
        )
        (home_with_plugin_state / ".claude" / "settings.json").write_text(
            json.dumps(
                {
                    "extraKnownMarketplaces": {
                        MARKETPLACE_NAME: {
                            "source": {"source": "directory", "path": "/stale/checkout"}
                        }
                    }
                }
            )
        )

        _run_install(home_with_plugin_state)

        entry = _known(home_with_plugin_state)[MARKETPLACE_NAME]
        assert entry["source"] == {"source": "github", "repo": "derio-net/super-fr"}
        assert entry["installLocation"].endswith(f"/marketplaces/{MARKETPLACE_NAME}")


# ── The bare org name is retired, and purged on sight ─────────────────


class TestRetiresTheBareOrgMarketplace:
    """With `derio-net` owned by nobody, every `*@derio-net` registration is
    dangling by definition — so purging the whole key is safe by construction,
    not us reaching into a sibling repo's install state."""

    def test_removes_the_legacy_marketplace_from_both_registries(
        self, home_with_plugin_state: Path
    ) -> None:
        _seed_legacy(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        assert LEGACY_NAME not in _known(home_with_plugin_state)
        assert LEGACY_NAME not in _settings(home_with_plugin_state)["extraKnownMarketplaces"]

    def test_removes_the_legacy_directory_and_cache(self, home_with_plugin_state: Path) -> None:
        _seed_legacy(home_with_plugin_state)
        plugins = home_with_plugin_state / ".claude" / "plugins"

        _run_install(home_with_plugin_state)

        assert not (plugins / "marketplaces" / LEGACY_NAME).exists()
        assert not (plugins / "cache" / LEGACY_NAME).exists()

    def test_drops_every_legacy_plugin_id_including_a_siblings(
        self, home_with_plugin_state: Path
    ) -> None:
        _seed_legacy(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        installed = _installed(home_with_plugin_state)["plugins"]
        enabled = _settings(home_with_plugin_state)["enabledPlugins"]
        for stale in (
            "super-fr@derio-net",
            "super-fr-dispatch@derio-net",
            "superpowers-for-vk@derio-net",
            "blog-craft@derio-net",
        ):
            assert stale not in installed, f"{stale} must be purged from installed_plugins"
            assert stale not in enabled, f"{stale} must be purged from enabledPlugins"

    def test_reports_what_it_purged(self, home_with_plugin_state: Path) -> None:
        _seed_legacy(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        combined = result.stdout + result.stderr
        assert "blog-craft@derio-net" in combined, (
            f"a sibling's dropped registration must be named, not silent:\n{combined}"
        )
        assert "Retired" in combined

    def test_tells_the_operator_to_rerun_a_siblings_installer(
        self, home_with_plugin_state: Path
    ) -> None:
        _seed_legacy(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        assert "Re-run their installers" in (result.stdout + result.stderr)

    def test_no_sibling_note_when_only_our_own_ids_were_purged(
        self, home_with_plugin_state: Path
    ) -> None:
        """Don't nag about siblings that aren't there."""
        _seed_legacy(home_with_plugin_state, with_sibling=False)

        result = _run_install(home_with_plugin_state)

        assert "Re-run their installers" not in (result.stdout + result.stderr)

    def test_leaves_unrelated_marketplaces_and_plugins_alone(
        self, home_with_plugin_state: Path
    ) -> None:
        _seed_legacy(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        known = _known(home_with_plugin_state)
        assert known["thedotmack"]["source"]["repo"] == "thedotmack/claude-mem"
        assert known["thedotmack"]["installLocation"] == "/elsewhere/thedotmack"
        settings = _settings(home_with_plugin_state)
        assert settings["extraKnownMarketplaces"]["thedotmack"]["source"]["repo"] == (
            "thedotmack/claude-mem"
        )
        assert settings["enabledPlugins"]["claude-mem@thedotmack"] is True
        assert "claude-mem@thedotmack" in _installed(home_with_plugin_state)["plugins"]

    def test_purge_is_quiet_on_a_clean_machine(self, home_with_plugin_state: Path) -> None:
        """Nothing legacy present → no scary retirement banner."""
        result = _run_install(home_with_plugin_state)

        assert "Retired the" not in result.stdout + result.stderr

    def test_idempotent_across_reinstalls(self, home_with_plugin_state: Path) -> None:
        _seed_legacy(home_with_plugin_state)

        _run_install(home_with_plugin_state)
        _run_install(home_with_plugin_state)

        assert LEGACY_NAME not in _known(home_with_plugin_state)
        for plugin_id in OWN_IDS:
            assert plugin_id in _installed(home_with_plugin_state)["plugins"]


# ── Guards on our own namespace ───────────────────────────────────────


class TestForeignOccupantWarning:
    """`derio-net--super-fr` names exactly one repo, so nothing else should ever
    be in that directory — but a name collision is silent and total, so check
    rather than assume."""

    def _plant_foreign_manifest(self, home: Path, name: str = "somebody-else") -> Path:
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
        manifest.write_text(json.dumps({"name": name, "plugins": [{"name": name, "source": "./"}]}))
        return manifest

    def test_warns_and_names_the_squatter(self, home_with_plugin_state: Path) -> None:
        self._plant_foreign_manifest(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        combined = result.stdout + result.stderr
        assert "WARNING" in combined
        assert "somebody-else" in combined
        assert MARKETPLACE_NAME in combined

    def test_reclaims_the_directory_despite_the_warning(self, home_with_plugin_state: Path) -> None:
        """Advisory, not fatal — refusing would let a squat permanently break
        super-fr installs."""
        manifest = self._plant_foreign_manifest(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        assert json.loads(manifest.read_text())["name"] == MARKETPLACE_NAME

    def test_quiet_when_the_directory_is_our_own(self, home_with_plugin_state: Path) -> None:
        _run_install(home_with_plugin_state)
        result = _run_install(home_with_plugin_state)

        assert "foreign" not in (result.stdout + result.stderr).lower()


class TestOrphanedPluginEntryReport:
    """An id under OUR name that our manifest doesn't list can never resolve.
    Report it — silently deleting a registration is how the original bug hid."""

    def _register_orphan(self, home: Path) -> None:
        plugins = home / ".claude" / "plugins"
        (plugins / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        f"fr-retired@{MARKETPLACE_NAME}": [{"scope": "user", "version": "1.0.0"}]
                    },
                }
            )
        )
        (home / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {f"fr-retired@{MARKETPLACE_NAME}": True}})
        )

    def test_reports_orphaned_entry_by_id(self, home_with_plugin_state: Path) -> None:
        self._register_orphan(home_with_plugin_state)

        result = _run_install(home_with_plugin_state)

        assert f"fr-retired@{MARKETPLACE_NAME}" in (result.stdout + result.stderr)

    def test_does_not_delete_the_orphaned_entry(self, home_with_plugin_state: Path) -> None:
        self._register_orphan(home_with_plugin_state)

        _run_install(home_with_plugin_state)

        assert f"fr-retired@{MARKETPLACE_NAME}" in _installed(home_with_plugin_state)["plugins"]

    def test_silent_when_only_our_own_plugins_are_registered(
        self, home_with_plugin_state: Path
    ) -> None:
        _run_install(home_with_plugin_state)
        result = _run_install(home_with_plugin_state)

        assert "orphan" not in (result.stdout + result.stderr).lower()

    def test_owned_ids_track_the_manifest(self) -> None:
        manifest_names = {p["name"] for p in _marketplace_manifest()["plugins"]}
        script = (REPO_ROOT / "scripts" / "install.sh").read_text()
        assert "PLUGIN_NAMES=(super-fr super-fr-dispatch)" in script
        assert manifest_names == {"super-fr", "super-fr-dispatch"}
