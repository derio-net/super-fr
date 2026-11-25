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
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [config]\n"
    assert config_space(root).at_default(".fr/docs.yaml") is None


def test_quiet_with_no_fr_config_yet_refuses_rather_than_reading_no_configuration(
    tmp_path: Path,
) -> None:
    """Review p1-r3: a configuration space that does not exist yet is not "no
    configuration", or lens rules, docs.yaml and gate_checks would vanish."""
    from fr.settings import SettingsError

    root = quiet_repo(tmp_path)
    space = config_space(root)
    with pytest.raises(SettingsError, match=r"origin/fr-config.*fr migrate artifacts --yes"):
        space.at_default(".fr/ci.yaml")
    with pytest.raises(SettingsError, match="origin/fr-config"):
        space.at_pair(".fr/ci.yaml", "main", "HEAD")


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
    track = tmp_path / "track.git"
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main-config", str(seed))
    git(seed, "remote", "add", "origin", str(track))
    _commit(seed, "local--work/.fr/ci.yaml", "gate_checks: [stealth]\n")
    git(tmp_path, "clone", "-q", "-b", "main-config", str(track), str(clone))
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [stealth]\n"
    assert config_space(root).at_default(".fr/docs.yaml") is None


def test_stealth_with_no_configuration_clone_refuses(tmp_path: Path, _home: Path) -> None:
    from fr.settings import SettingsError

    root, clone = stealth_repo(tmp_path, _home)
    with pytest.raises(SettingsError, match=r"configuration clone.*fr migrate artifacts --yes"):
        config_space(root).at_default(".fr/ci.yaml")
    with pytest.raises(SettingsError, match="configuration clone"):
        config_space(root).at_pair("ci.yaml", "main", "HEAD")


def test_stealth_clone_without_its_config_branch_refuses(tmp_path: Path, _home: Path) -> None:
    from fr.settings import SettingsError

    root, clone = stealth_repo(tmp_path, _home)
    git(tmp_path, "init", "-q", "-b", "main-config", str(clone))
    with pytest.raises(SettingsError, match="origin/main-config"):
        config_space(root).at_default(".fr/ci.yaml")


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


def test_quiet_declared_gates_ignore_the_branch_and_read_the_config_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.ci_evidence import CiEvidenceRefused, declared_gates

    _enforced(monkeypatch)
    root = quiet_repo(tmp_path)
    _commit(root, ".fr/ci.yaml", "gate_checks: [branch]\n", push=False)
    with pytest.raises(CiEvidenceRefused, match="origin/fr-config"):
        declared_gates(root, "main")
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    assert declared_gates(root, "main") == ["config"]


def test_quiet_lens_rules_ignore_the_branch_and_read_the_config_tip(tmp_path: Path) -> None:
    from fr.lenses.model import LensError
    from fr.lenses.rules import rules_in_force_at

    root = quiet_repo(tmp_path)
    rule = "require:\n  - paths: ['src/**']\n    lenses: [security]\n"
    _commit(root, ".fr/lenses.yaml", rule, push=False)
    with pytest.raises(LensError, match="origin/fr-config"):
        rules_in_force_at(root)
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
    # a real fr-config checkout at its fetched tip: guarded readers refuse any other (p3-r2)
    _push_orphan(root, "fr-config", {f".fr/{n}": t for n, t in config.items()})
    git(root, "fetch", "-q", "origin", "+refs/heads/fr-config:refs/remotes/origin/fr-config")
    where = home / ".cache" / "fr" / "worktrees" / "work" / "fr-config"
    where.parent.mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "-q", "-b", "fr-config", str(where), "origin/fr-config")
    for name, text in product.items():
        (root / ".fr").mkdir(exist_ok=True)
        (root / ".fr" / name).write_text(text)
    return root, where / ".fr"


def test_quiet_readers_read_the_config_space_and_ignore_the_product(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.debt.engine import load_stale_days
    from fr.docs.load import load_config as docs_config
    from fr.lenses.resolve import load_config as lens_config
    from fr.ops.load import load_ops_config
    from fr.verification.rows import load_remap

    root, _ = _quiet_with_config(tmp_path, _home)
    _enforced(monkeypatch)
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


_GUARDED_TRIAGE = (
    "post_merge: [./config.sh]\npr_authors: [mallory]\nstale_dispatch_days: 9\n"
    "mirrors: [[./regen]]\nqueue:\n  ci: none\nexit:\n  gates:\n    live: none\n"
)


class _RulesForge(_Forge):
    """A forge whose `branch_rules` answers *rules* (a list, or an exception to raise)."""

    def __init__(self, files: dict[tuple[str, str], str], rules: object) -> None:
        super().__init__(files)
        self.rules = rules
        self.asked: list[tuple[str, str]] = []

    def branch_rules(self, *, repo: str, branch: str) -> object:
        self.asked.append((repo, branch))
        if isinstance(self.rules, Exception):
            raise self.rules
        return self.rules


def _protected_rules() -> list[dict[str, object]]:
    rules = (
        Path(__file__).resolve().parents[1]
        / "fixtures/github_rest/rules/pull-request-approved.json"
    )
    return list(json.loads(rules.read_text()))


def test_forge_side_triage_config_follows_the_quiet_switch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Finding sec-1 / p1-r1: a pushed fr-config with no pull_request rule supplies no
    command and no trust key; the rest of its configuration is read, and the reason is said
    once."""
    from fr.triage.collect import read_config_lenient

    forge = _RulesForge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/triage.yaml", "fr-config"): _GUARDED_TRIAGE,
            (".fr/triage.yaml", "HEAD"): "post_merge: [./product.sh]\n",
        },
        [],
    )
    config, _ = read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    assert config is not None
    assert config.post_merge == [] and config.pr_authors == [] and config.mirrors == []
    assert config.queue is None and config.exit is None
    assert config.stale_dispatch_days == 9  # not executable: still read
    read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    err = capsys.readouterr().err
    assert err.count("ignoring") == 1
    assert "post_merge" in err and "pr_authors" in err and "protect fr-config" in err


def test_forge_side_triage_config_from_a_protected_fr_config_supplies_every_key() -> None:
    from fr.triage.collect import read_config_lenient

    forge = _RulesForge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/triage.yaml", "fr-config"): _GUARDED_TRIAGE,
        },
        _protected_rules(),
    )
    config, _ = read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    assert config is not None
    assert config.post_merge == ["./config.sh"] and config.pr_authors == ["mallory"]
    assert config.queue is not None and config.exit is not None
    assert forge.asked == [("o/r", "fr-config")]


def test_forge_side_triage_config_refuses_when_the_protection_read_fails() -> None:
    """A failed read is not "unprotected": that repo's config read refuses, naming it."""
    from fr.triage.collect import read_config_lenient
    from fr.triage.errors import TriageError

    forge = _RulesForge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/triage.yaml", "fr-config"): _GUARDED_TRIAGE,
        },
        RuntimeError("HTTP 502: bad gateway"),
    )
    with pytest.raises(TriageError, match="HTTP 502"):
        read_config_lenient(forge, "o/r")  # type: ignore[arg-type]


def test_forge_side_triage_config_without_guarded_keys_asks_nothing() -> None:
    from fr.triage.collect import read_config_lenient

    forge = _RulesForge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/triage.yaml", "fr-config"): "stale_dispatch_days: 5\n",
        },
        AssertionError("no guarded key, no forge read"),
    )
    config, _ = read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    assert config is not None and config.stale_dispatch_days == 5


def test_default_branch_triage_config_is_read_whole_without_asking() -> None:
    """Under repo (no quiet switch) nothing changes: the default branch's file is read."""
    from fr.triage.collect import read_config_lenient

    forge = _RulesForge(
        {(".fr/triage.yaml", "HEAD"): "post_merge: [./product.sh]\n"},
        AssertionError("repo placement never asks"),
    )
    config, _ = read_config_lenient(forge, "o/r")  # type: ignore[arg-type]
    assert config is not None and config.post_merge == ["./product.sh"]


def test_forge_side_settings_follow_the_quiet_switch() -> None:
    from fr.settings.remote import remote_settings_text

    forge = _Forge(
        {
            (".fr/settings.yaml", "fr-config"): QUIET,
            (".fr/settings.yaml", "HEAD"): "schema: 1\n",
        }
    )
    assert remote_settings_text(forge, "o/r") == QUIET


# --- forge_ref: only a not-found is "no switch" (review p1-r2, p1-r6) ------------------


class _Failing(_Forge):
    """Every read fails with *exc*."""

    def __init__(self, exc: Exception) -> None:
        super().__init__({})
        self.exc = exc

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        self.reads.append((path, ref))
        raise self.exc


def test_forge_ref_propagates_a_forge_error_that_is_not_a_not_found() -> None:
    from fr.config.space import forge_ref

    boom = RuntimeError("HTTP 500: server error")
    with pytest.raises(RuntimeError, match="HTTP 500"):
        forge_ref(_Failing(boom), "o/r")


def test_forge_ref_is_no_switch_on_a_forge_that_cannot_read_at_a_ref() -> None:
    from fr.config.space import forge_ref
    from fr.ghclient import UnsupportedForgeOperation

    assert forge_ref(object(), "o/r") is None
    glab = _Failing(UnsupportedForgeOperation("read_file_at_ref", "glab"))
    assert forge_ref(glab, "o/r") is None


def test_forge_ref_is_no_switch_when_triage_wrapped_the_unsupported_operation() -> None:
    """Triage's `ClientForge` turns `UnsupportedForgeOperation` into its `ForgeError`; the
    cause still says the backend cannot read a file at a ref."""
    from fr.config.space import forge_ref
    from fr.ghclient import UnsupportedForgeOperation
    from fr.triage.errors import ForgeError

    unsupported = UnsupportedForgeOperation("read_file_at_ref", "tea")
    wrapped = ForgeError(str(unsupported))
    wrapped.__cause__ = unsupported
    assert forge_ref(_Failing(wrapped), "o/r") is None


@pytest.mark.parametrize(
    "text",
    [
        "schema: 1\nplacement: 'quiet'\n",
        "schema: 1\nplacement: quiet  # on\n",
        "schema: 1\nplacement: stealth\n",
        "schema: 1\nplacement: quiet\nbogus_key: 1\n",
    ],
)
def test_forge_ref_refuses_a_switch_the_local_reader_refuses(text: str) -> None:
    from fr.config.space import forge_ref
    from fr.settings import SettingsError

    forge = _Forge({(".fr/settings.yaml", "fr-config"): text})
    with pytest.raises(SettingsError):
        forge_ref(forge, "o/r")


def test_forge_ref_is_no_switch_for_a_file_naming_no_placement() -> None:
    from fr.config.space import forge_ref

    assert forge_ref(_Forge({(".fr/settings.yaml", "fr-config"): "schema: 1\n"}), "o/r") is None


def test_remote_settings_refuses_when_the_switch_probe_fails() -> None:
    from fr.settings import SettingsError
    from fr.settings.remote import remote_settings_text

    with pytest.raises(SettingsError, match="HTTP 500"):
        remote_settings_text(_Failing(RuntimeError("HTTP 500: boom")), "o/r")


def test_remote_settings_passes_a_switch_refusal_through_unwrapped() -> None:
    from fr.settings import SettingsError
    from fr.settings.remote import remote_settings_text

    forge = _Forge({(".fr/settings.yaml", "fr-config"): "schema: 1\nplacement: stealth\n"})
    with pytest.raises(SettingsError, match="stealth") as info:
        remote_settings_text(forge, "o/r")
    assert "cannot read" not in str(info.value)


def test_triage_config_read_reports_a_bad_switch_as_that_repos_failure() -> None:
    """Collect skips a repo whose read raised `TriageError` (org scope) and names the
    reason; a malformed switch is one, never a traceback."""
    from fr.triage.collect import read_config_lenient
    from fr.triage.errors import TriageError

    forge = _Forge({(".fr/settings.yaml", "fr-config"): "schema: 1\nplacement: 'quiet'\n"})
    with pytest.raises(TriageError, match="o/r"):
        read_config_lenient(forge, "o/r")  # type: ignore[arg-type]


def test_triage_config_read_propagates_a_forge_error_on_the_switch_probe() -> None:
    from fr.triage.collect import read_config_lenient
    from fr.triage.errors import ForgeError

    with pytest.raises(ForgeError, match="HTTP 500"):
        read_config_lenient(_Failing(ForgeError("HTTP 500: boom")), "o/r")  # type: ignore[arg-type]


def test_the_queue_refuses_its_required_checks_when_fr_config_is_missing(
    tmp_path: Path,
) -> None:
    """Review p1-r3: the merge queue's `gate_checks` read refuses as a triage error the
    drive reports for that repo, never falls back to the base's required checks."""
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout
    from fr.triage.queue_exec import required_names

    class _Client:
        def required_check_names(self, repo: str, base: str) -> list[str]:
            raise AssertionError("a missing configuration space never falls back")

    root = quiet_repo(tmp_path)
    with pytest.raises(TriageError, match="origin/fr-config"):
        required_names(_Client(), Checkout(root), "o/r", "main")  # type: ignore[arg-type]


def test_the_ops_gate_reads_the_queue_block_from_the_configuration_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p1-r5 found `queue_configured` building `<rev>:.fr/triage.yaml` itself: under
    quiet it reads `fr-config`, and refuses while that space is missing."""
    from fr.commands.ops_gate_cmd import HostCheckout
    from fr.ops.gate import StageFailed

    root = quiet_repo(tmp_path)
    with pytest.raises(StageFailed, match="origin/fr-config"):
        HostCheckout(root).queue_configured("main")
    _push_orphan(root, "fr-config", {".fr/triage.yaml": "queue:\n  ci: push\n"})
    _enforced(monkeypatch)
    assert HostCheckout(root).queue_configured("main") is True


# --- a malformed switch reaches each reader as its own error (review p1-r4) -------------


def _bad_switch_repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    _push_orphan(root, "fr", {"settings.yaml": "schema: 1\nplacement: 'quiet'\n"})
    git(root, "fetch", "-q", "origin", "+refs/heads/fr:refs/remotes/origin/fr")
    return root


def test_a_malformed_switch_is_the_docs_readers_own_error(tmp_path: Path) -> None:
    from fr.docs.load import DocsEnvError, load_config

    with pytest.raises(DocsEnvError, match="placement"):
        load_config(_bad_switch_repo(tmp_path))


def test_a_malformed_switch_is_the_debt_readers_own_error(tmp_path: Path) -> None:
    from fr.debt.engine import DebtConfigError, load_stale_days

    with pytest.raises(DebtConfigError, match="placement"):
        load_stale_days(_bad_switch_repo(tmp_path), None)


def test_a_malformed_switch_is_the_ops_readers_own_error(tmp_path: Path) -> None:
    from fr.ops.load import OpsLoadError, load_ops_config

    with pytest.raises(OpsLoadError, match="placement"):
        load_ops_config(_bad_switch_repo(tmp_path))


def test_a_malformed_switch_is_the_lens_readers_own_error(tmp_path: Path) -> None:
    from fr.lenses.model import LensError
    from fr.lenses.resolve import load_config

    with pytest.raises(LensError, match="placement"):
        load_config(_bad_switch_repo(tmp_path))


def test_a_malformed_switch_leaves_the_lenient_remap_lenient(tmp_path: Path) -> None:
    from fr.verification.rows import load_remap

    remap, why = load_remap(_bad_switch_repo(tmp_path))
    assert remap == {}
    assert why is not None and "placement" in why


# --- the PR body's lens-config question reads at_pair (R3, review p1-r6) ----------------


def test_lens_config_changed_under_repo_compares_the_merge_base_with_head(
    tmp_path: Path,
) -> None:
    from fr.record.pr_body import _lens_config_changed

    root = make_repo(tmp_path)
    base = _commit(root, ".fr/lenses.yaml", "disable: [tests]\n")
    git(root, "checkout", "-q", "-b", "feat/x")
    changed = (".fr/lenses.yaml",)
    assert _lens_config_changed(root, base, changed) is False  # same text at both
    _commit(root, ".fr/lenses.yaml", "disable: [errors]\n", push=False)
    assert _lens_config_changed(root, base, changed) is True
    assert _lens_config_changed(root, base, ()) is False  # the diff did not name it
    assert _lens_config_changed(root, None, changed) is False  # no merge-base


def test_lens_config_changed_is_never_true_under_quiet(tmp_path: Path) -> None:
    from fr.record.pr_body import _lens_config_changed

    root = quiet_repo(tmp_path)
    base = git(root, "rev-parse", "HEAD").strip()
    _commit(root, ".fr/lenses.yaml", "disable: [errors]\n", push=False)
    _push_orphan(root, "fr-config", {".fr/lenses.yaml": "disable: [tests]\n"})
    assert _lens_config_changed(root, base, (".fr/lenses.yaml",)) is False


def _enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configuration branch reads as forge-protected (spec R7), so executable
    configuration is read; `tests/unit/test_config_protection_executors.py` covers the rest."""
    from fr.config import protection

    rules = _protected_rules()

    class _Client:
        def branch_rules(self, repo: str, branch: str) -> object:
            return rules

    monkeypatch.setattr(protection, "_origin_slug", lambda root: "example-org/example-repo")
    monkeypatch.setattr(protection, "_default_client", lambda space: _Client())
