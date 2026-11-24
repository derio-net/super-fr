"""The configuration space resolver (spec 2026-11-19-event-driven-a-la-carte §A, R1-R4)."""

from __future__ import annotations

import json
from pathlib import Path

import fr.config.space as space_mod
import pytest
from fr.config.space import ConfigSpace, config_space

from tests.unit.settings_repo import git, make_repo


def test_the_resolver_names_its_spec() -> None:
    assert "2026-11-19-event-driven-a-la-carte" in (space_mod.__doc__ or "")


# --- ConfigSpace under repo, quiet and stealth (R1, R2) ---------------------------------

QUIET = "schema: 1\nplacement: quiet\nforge:\n  labels: off\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _push_orphan(root: Path, branch: str, files: dict[str, str]) -> None:
    """An orphan *branch* on origin holding *files*; the local branch is deleted again."""
    back = git(root, "symbolic-ref", "--short", "HEAD").strip()
    git(root, "checkout", "-q", "--orphan", branch)
    git(root, "rm", "-rfq", ".")
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", branch)
    git(root, "push", "-q", "origin", branch)
    git(root, "checkout", "-q", back)
    git(root, "branch", "-q", "-D", branch)


def _commit(root: Path, rel: str, text: str, *, push: bool = True) -> str:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", rel)
    if push:
        git(root, "push", "-q", "origin", "HEAD")
    return git(root, "rev-parse", "HEAD").strip()


def quiet_repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    _push_orphan(root, "fr", {"settings.yaml": QUIET})
    git(root, "checkout", "-q", "-b", "feat/q")
    return root


def stealth_repo(tmp_path: Path, home: Path) -> tuple[Path, Path]:
    """A product checkout with a stealth marker, and its configuration clone (on
    `main-config`, the tracking branch `main`'s configuration branch)."""
    root = make_repo(tmp_path)
    git(root, "checkout", "-q", "-b", "feat/s")
    track = tmp_path / "track.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(track))
    marker = {
        "toplevel": str(root),
        "branch": "feat/s",
        "mode": "worktree",
        "placement": "stealth",
        "tracking": {"ref": f"{track}@main", "target": "local--work"},
    }
    (root / ".fr-isolation").write_text(json.dumps(marker))
    clone = home / ".cache" / "fr" / "worktrees" / "work" / "stealth--local--track--main-config"
    return root, clone


def test_repo_space_is_the_product_checkout(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    space = config_space(root)
    assert isinstance(space, ConfigSpace)
    assert space.placement == "repo"
    assert space.dir == root / ".fr"
    assert space.checkout == root
    assert space.default_ref == "origin/main"


def test_repo_at_default_reads_the_default_branch_never_the_working_tree(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    _commit(root, ".fr/ci.yaml", "gate_checks: [a]\n")
    (root / ".fr" / "ci.yaml").write_text("gate_checks: [local]\n")
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [a]\n"
    assert config_space(root).at_default("ci.yaml") == "gate_checks: [a]\n"


def test_quiet_space_is_the_fr_config_worktree(tmp_path: Path, _home: Path) -> None:
    root = quiet_repo(tmp_path)
    space = config_space(root)
    assert space.placement == "quiet"
    checkout = _home / ".cache" / "fr" / "worktrees" / "work" / "fr-config"
    assert space.checkout == checkout
    assert space.dir == checkout / ".fr"
    assert space.default_ref == "origin/fr-config"


def test_quiet_at_default_reads_the_fr_config_tip(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    _commit(root, ".fr/ci.yaml", "gate_checks: [product]\n", push=False)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [config]\n"


def test_stealth_space_is_the_configuration_clone(tmp_path: Path, _home: Path) -> None:
    root, clone = stealth_repo(tmp_path, _home)
    space = config_space(root)
    assert space.placement == "stealth"
    assert space.checkout == clone
    assert space.dir == clone / "local--work" / ".fr"
    assert space.default_ref == "origin/main-config"


def test_stealth_at_default_reads_the_config_branch_in_the_clone(
    tmp_path: Path, _home: Path
) -> None:
    root, clone = stealth_repo(tmp_path, _home)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    track = tmp_path / "track.git"
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main-config", str(seed))
    git(seed, "remote", "add", "origin", str(track))
    _commit(seed, "local--work/.fr/ci.yaml", "gate_checks: [stealth]\n")
    git(tmp_path, "clone", "-q", "-b", "main-config", str(track), str(clone))
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [stealth]\n"


# --- at_pair and the feature-branch rule (R3) -------------------------------------------


def test_repo_at_pair_reads_the_two_commits_it_is_given(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    base = _commit(root, ".fr/ci.yaml", "gate_checks: [base]\n")
    git(root, "checkout", "-q", "-b", "feat/x")
    head = _commit(root, ".fr/ci.yaml", "gate_checks: [head]\n", push=False)
    assert config_space(root).at_pair(".fr/ci.yaml", base, head) == (
        "gate_checks: [base]\n",
        "gate_checks: [head]\n",
    )


def test_quiet_at_pair_reads_the_config_tip_for_both_sides(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    base = git(root, "rev-parse", "HEAD").strip()
    head = _commit(root, ".fr/ci.yaml", "gate_checks: [branch]\n", push=False)
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    tip = "gate_checks: [config]\n"
    assert config_space(root).at_pair(".fr/ci.yaml", base, head) == (tip, tip)


def test_stealth_at_pair_reads_the_config_tip_for_both_sides(tmp_path: Path, _home: Path) -> None:
    root, clone = stealth_repo(tmp_path, _home)
    head = _commit(root, ".fr/ci.yaml", "gate_checks: [branch]\n", push=False)
    track = tmp_path / "track.git"
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main-config", str(seed))
    git(seed, "remote", "add", "origin", str(track))
    _commit(seed, "local--work/.fr/ci.yaml", "gate_checks: [stealth]\n")
    git(tmp_path, "clone", "-q", "-b", "main-config", str(track), str(clone))
    tip = "gate_checks: [stealth]\n"
    assert config_space(root).at_pair("ci.yaml", "main", head) == (tip, tip)


def test_quiet_declared_gates_ignore_the_branch_and_read_the_config_tip(tmp_path: Path) -> None:
    from fr.run.ci_evidence import declared_gates

    root = quiet_repo(tmp_path)
    _commit(root, ".fr/ci.yaml", "gate_checks: [branch]\n", push=False)
    assert declared_gates(root, "main") is None
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    assert declared_gates(root, "main") == ["config"]


def test_quiet_lens_rules_ignore_the_branch_and_read_the_config_tip(tmp_path: Path) -> None:
    from fr.lenses.rules import rules_in_force_at

    root = quiet_repo(tmp_path)
    rule = "require:\n  - paths: ['src/**']\n    lenses: [security]\n"
    _commit(root, ".fr/lenses.yaml", rule, push=False)
    assert rules_in_force_at(root) == ()
    _push_orphan(root, "fr-config", {".fr/lenses.yaml": rule})
    assert [r.lenses for r in rules_in_force_at(root)] == [("security",)]


# --- the .fr readers under quiet (R1, R4) -----------------------------------------------


def _quiet_with_config(tmp_path: Path, home: Path) -> tuple[Path, Path]:
    """A quiet product whose own `.fr/` says one thing and whose `fr-config` worktree
    directory says another."""
    root = quiet_repo(tmp_path)
    product = {
        "docs.yaml": "pages: [product.md]\n",
        "lenses.yaml": "disable: [tests]\n",
        "ops.yaml": "env_passthrough: [PRODUCT]\n",
        "debt.yaml": "stale_days: 3\n",
        "triage.yaml": "exit:\n  gates:\n    tester: devops\n",
        "isolation-allow": "data/**\n",
    }
    config = {
        "docs.yaml": "pages: [config.md]\n",
        "lenses.yaml": "disable: [errors]\n",
        "ops.yaml": "env_passthrough: [CONFIG]\n",
        "debt.yaml": "stale_days: 9\n",
    }
    for name, text in product.items():
        (root / ".fr").mkdir(exist_ok=True)
        (root / ".fr" / name).write_text(text)
    cfg = home / ".cache" / "fr" / "worktrees" / "work" / "fr-config" / ".fr"
    cfg.mkdir(parents=True)
    for name, text in config.items():
        (cfg / name).write_text(text)
    return root, cfg


def test_quiet_readers_read_the_config_space_and_ignore_the_product(
    tmp_path: Path, _home: Path
) -> None:
    from fr.debt.engine import load_stale_days
    from fr.docs.load import load_config as docs_config
    from fr.lenses.resolve import load_config as lens_config
    from fr.ops.load import load_ops_config
    from fr.verification.rows import load_remap

    root, _ = _quiet_with_config(tmp_path, _home)
    docs = docs_config(root)
    assert docs is not None and docs.pages == ["config.md"]
    assert lens_config(root).disable == ("errors",)
    assert load_ops_config(root).env_passthrough == ("CONFIG",)
    assert load_stale_days(root, None) == 9
    assert load_remap(root) == ({}, None)


def test_the_ignored_product_files_are_named_once_per_process(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.debt.engine import load_stale_days
    from fr.docs.load import load_config as docs_config

    root, _ = _quiet_with_config(tmp_path, _home)
    docs_config(root)
    load_stale_days(root, None)
    err = capsys.readouterr().err
    lines = [line for line in err.splitlines() if "ignoring the product" in line]
    assert lines == [
        "fr: ignoring the product checkout's .fr/ under quiet: "
        "debt.yaml, docs.yaml, lenses.yaml, ops.yaml, triage.yaml"
    ]
    assert "isolation-allow" not in lines[0]


def test_repo_readers_say_nothing_about_ignored_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_repo(tmp_path)
    (root / ".fr").mkdir()
    (root / ".fr" / "debt.yaml").write_text("stale_days: 4\n")
    from fr.debt.engine import load_stale_days

    assert load_stale_days(root, None) == 4
    assert "ignoring" not in capsys.readouterr().err


def test_a_directory_outside_git_is_a_repo_space(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    space = config_space(plain)
    assert (space.placement, space.dir) == ("repo", plain / ".fr")
    assert space.at_default("ci.yaml") is None


class _Forge:
    """Serves `{(path, ref): text}`; anything else is a 404."""

    def __init__(self, files: dict[tuple[str, str], str]) -> None:
        self.files = files
        self.reads: list[tuple[str, str]] = []

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        self.reads.append((path, ref))
        if (path, ref) not in self.files:
            raise RuntimeError("Not Found (HTTP 404)")
        return self.files[(path, ref)]

    def read_file(self, repo: str, path: str) -> str:
        return self.read_file_at_ref(repo=repo, path=path, ref="HEAD")


def test_forge_ref_is_fr_config_only_when_it_carries_a_quiet_switch() -> None:
    from fr.config.space import forge_ref

    assert forge_ref(_Forge({}), "o/r") is None
    repo_switch = _Forge({(".fr/settings.yaml", "fr-config"): "schema: 1\nplacement: repo\n"})
    assert forge_ref(repo_switch, "o/r") is None
    quiet = _Forge({(".fr/settings.yaml", "fr-config"): QUIET})
    assert forge_ref(quiet, "o/r") == "fr-config"


def test_forge_side_triage_config_follows_the_quiet_switch() -> None:
    from fr.triage.collect import read_config_lenient

    forge = _Forge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/triage.yaml", "fr-config"): "post_merge: [./config.sh]\n",
            (".fr/triage.yaml", "HEAD"): "post_merge: [./product.sh]\n",
        }
    )
    config, _ = read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    assert config is not None and config.post_merge == ["./config.sh"]


def test_forge_side_settings_follow_the_quiet_switch() -> None:
    from fr.settings.remote import remote_settings_text

    forge = _Forge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/settings.yaml", "HEAD"): "schema: 1\n",
        }
    )
    assert remote_settings_text(forge, "o/r") == QUIET
