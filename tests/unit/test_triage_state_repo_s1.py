"""Where a scope keeps its state ref after S1 (spec 2026-11-19-event-driven-a-la-carte R19,
R20, R21, §G; row `s1-triage-state-home`).

The stealth workspace's tracking repo, the one-repo default, the repo's own
`triage.state_repo` (read through the forge from its configuration space, and only from a
protected `fr-config`), `fr triage check`'s mismatch set, settings `schema: 2`, and the
privacy guard on the repo each rule chooses. Forges are faked; remotes are bare repos under
`tmp_path`; `HOME` is the suite's sandbox.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd
from fr.placement import stealth
from fr.settings import SettingsError
from fr.settings.model import Settings, parse_settings
from fr.triage import state_home
from fr.triage.model import Facts, Issue, Scope, load_facts
from fr.triage.privacy import PrivacyError
from fr.triage.scope_config import ScopeDurable, load_durable, write_durable
from fr.triage.state_ref import decide_state_repo, push_state
from typer.testing import CliRunner

from tests.unit.triage_fixtures import ISSUES, PRS, FakeForge

REPO = "derio-net/super-fr"
SETTINGS = ".fr/settings.yaml"
DECLARED = "schema: 2\ntriage:\n  state_repo: example-org/triage-refs\n"
QUIET_DECLARED = "schema: 2\nplacement: quiet\ntriage:\n  state_repo: example-org/triage-refs\n"


def _never(*a: Any) -> str:
    raise AssertionError("no question may be asked")


# ------------------------------------------------------------------ the decision


def test_a_declared_state_repo_wins_for_a_one_repo_scope_outside_stealth() -> None:
    got = decide_state_repo(["o/one"], {}, _never, declared="o/refs")
    assert got == "o/refs"


def test_the_stealth_tracking_repo_comes_before_the_one_repo_default() -> None:
    assert decide_state_repo(["o/one"], {}, _never, stealth="o/track") == "o/track"
    assert decide_state_repo(["o/a", "o/b"], {}, _never, stealth="o/track") == "o/track"


def test_a_declared_state_repo_is_never_taken_for_a_scope_of_several_repos() -> None:
    asked: list[list[str]] = []

    def ask(question: str, choices: list[str], warning: str | None) -> str:
        asked.append(choices)
        return choices[0]

    got = decide_state_repo(["o/a", "o/b"], {"o/a": "private"}, ask, declared="o/refs")
    assert got == "o/a" and asked == [["o/a"]]


def test_without_either_the_rules_are_todays() -> None:
    assert decide_state_repo(["o/one"], {}, None) == "o/one"
    assert decide_state_repo(["o/a", "o/b"], {}, None) is None


# ------------------------------------------------------- the stealth workspace


def _clone(tmp_path: Path) -> Path:
    path = tmp_path / "target"
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    return path


@pytest.mark.parametrize(
    ("tracking", "want"),
    [
        ("git@github.com:example-org/track.git", "example-org/track"),
        ("https://github.com/example-org/track", "example-org/track"),
        ("/srv/track.git", None),
    ],
)
def test_a_stealth_workspace_names_its_tracking_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tracking: str, want: str | None
) -> None:
    clone = _clone(tmp_path)
    monkeypatch.setattr(
        stealth, "marker_tracking", lambda root: (stealth.StealthRef(tracking, "main"), "t")
    )
    assert state_home.stealth_tracking(clone) == (True, want)


def test_outside_a_stealth_workspace_there_is_no_tracking_repo(tmp_path: Path) -> None:
    assert state_home.stealth_tracking(_clone(tmp_path)) == (False, None)
    assert state_home.stealth_tracking(tmp_path / "nowhere") == (False, None)


# ------------------------------------------------- collect: R19 and R20 in action


class _RulesForge(FakeForge):
    def __init__(self, rules: object, **kw: Any) -> None:
        super().__init__(**kw)
        self.rules = rules

    def branch_rules(self, *, repo: str, branch: str) -> object:
        return self.rules


PROTECTED = [
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
    {"type": "non_fast_forward"},
    {"type": "deletion"},
]


def _forge(files: dict[tuple[str, str, str], str] | None = None, rules: object = None) -> Any:
    kw: dict[str, Any] = {
        "issues": {REPO: list(ISSUES)},
        "prs": {REPO: list(PRS)},
        "visibility": {REPO: "private"},
        "file_bodies": files or {},
    }
    return _RulesForge(rules, **kw) if rules is not None else FakeForge(**kw)


def _collect(state: Path, *extra: str) -> Any:
    return CliRunner().invoke(app, ["triage", "collect", "--repo", REPO, "--dir", str(state),
                                    *extra])  # fmt: skip


@pytest.fixture
def no_stealth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state_home, "stealth_tracking", lambda start: (False, None))


def test_collect_applies_the_declared_state_repo_from_the_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge({(REPO, SETTINGS, "HEAD"): DECLARED})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    result = _collect(state)

    assert result.exit_code == 0, result.output
    assert load_durable(state).state_repo == "example-org/triage-refs"
    assert load_facts(state / "facts.json").state_repo_declared == {REPO: "example-org/triage-refs"}


def test_collect_without_a_declaration_keeps_the_one_repo_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge()
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == REPO
    assert load_facts(state / "facts.json").state_repo_declared == {}


def test_a_declaration_on_an_unprotected_fr_config_is_ignored_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge({(REPO, SETTINGS, "fr-config"): QUIET_DECLARED}, rules=[])
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    result = _collect(state)

    assert result.exit_code == 0, result.output
    assert load_durable(state).state_repo == REPO
    assert "ignoring triage.state_repo" in result.output and "fr-config" in result.output


def test_a_declaration_on_a_protected_fr_config_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge({(REPO, SETTINGS, "fr-config"): QUIET_DECLARED}, rules=PROTECTED)
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == "example-org/triage-refs"


def test_an_unusable_settings_file_never_decides_and_never_fails_the_collect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    bad = "schema: 1\ntriage:\n  state_repo: example-org/triage-refs\n"  # triage needs 2
    forge = _forge({(REPO, SETTINGS, "HEAD"): bad})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    result = _collect(state)

    assert result.exit_code == 0, result.output
    assert load_durable(state).state_repo == REPO
    assert "triage.state_repo" in result.output and "schema: 2" in result.output


def test_a_recorded_state_repo_is_kept_and_check_reports_the_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge({(REPO, SETTINGS, "HEAD"): DECLARED})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"
    write_durable(state, ScopeDurable(state_repo=REPO))

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == REPO
    result = CliRunner().invoke(
        app, ["triage", "check", "--repo", REPO, "--dir", str(state), "--json"]
    )
    plain = CliRunner().invoke(app, ["triage", "check", "--repo", REPO, "--dir", str(state)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state_repo_mismatch"] == [
        {"repo": REPO, "declared": "example-org/triage-refs", "recorded": REPO}
    ]
    assert "state repo mismatch (1)" in plain.output
    assert "declares example-org/triage-refs, records derio-net/super-fr" in plain.output


def test_the_loops_carry_the_declaration_without_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_stealth: None
) -> None:
    forge = _forge({(REPO, SETTINGS, "HEAD"): DECLARED})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"
    assert _collect(state).exit_code == 0
    reads = len([kw for kw in forge.called("read_file_at_ref") if kw["path"] == SETTINGS])

    triage_cmd.collect_into(Scope(kind="repo", target=REPO), state, carry=True)

    after = len([kw for kw in forge.called("read_file_at_ref") if kw["path"] == SETTINGS])
    assert after == reads + 1  # only the quiet switch probe of the triage config read
    assert load_facts(state / "facts.json").state_repo_declared == {REPO: "example-org/triage-refs"}


def test_collect_from_a_stealth_workspace_takes_its_tracking_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge()
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(state_home, "stealth_tracking", lambda start: (True, "example-org/track"))
    state = tmp_path / "s"

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == "example-org/track"


def test_a_stealth_tracking_repo_that_is_no_forge_repo_leaves_the_state_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never the product repo: under stealth the one-repo default would push there."""
    forge = _forge()
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(state_home, "stealth_tracking", lambda start: (True, None))
    state = tmp_path / "s"

    result = _collect(state)

    assert result.exit_code == 0, result.output
    assert load_durable(state).state_repo is None
    assert "no forge repo" in result.output


# ------------------------------------------------------------- settings schema 2


def test_settings_accept_schema_2_with_the_triage_section() -> None:
    got = parse_settings({"schema": 2, "triage": {"state_repo": "o/r"}}, source="s")
    assert got.triage.state_repo == "o/r" and got.schema_ == 2


def test_settings_refuse_the_triage_key_under_schema_1() -> None:
    with pytest.raises(SettingsError, match="schema: 2"):
        parse_settings({"schema": 1, "triage": {"state_repo": "o/r"}}, source="s")
    with pytest.raises(SettingsError, match="schema: 2"):
        parse_settings({"triage": {"state_repo": "o/r"}}, source="s")
    # An empty section sets no key: the commented `fr settings init` file, uncommented,
    # still parses at schema 1.
    assert parse_settings({"triage": {"state_repo": None}}, source="s").schema_ == 1


def test_a_settings_file_without_the_key_may_stay_at_schema_1() -> None:
    assert parse_settings({"schema": 1}, source="s").triage.state_repo is None
    assert parse_settings({"schema": 2}, source="s").schema_ == 2


def test_a_newer_schema_is_refused_with_the_existing_message() -> None:
    with pytest.raises(SettingsError, match="newer than this fr"):
        parse_settings({"schema": 3}, source="s")


@pytest.mark.parametrize("bad", ["no-slash", "a/b/c", "o/..", "", 7])
def test_the_state_repo_is_owner_slash_repo(bad: object) -> None:
    with pytest.raises(SettingsError, match="triage.state_repo"):
        parse_settings({"schema": 2, "triage": {"state_repo": bad}}, source="s")


def test_settings_show_lists_triage_state_repo() -> None:
    from fr.commands.settings_cmd import _flatten

    assert _flatten(Settings.model_validate({}))["triage.state_repo"] is None


def test_settings_init_documents_the_key_commented_out() -> None:
    from fr.settings.render import render_init

    text = render_init()
    assert "#triage:\n" in text and "#  state_repo: null\n" in text
    assert parse_settings({}, source="s") == Settings.model_validate({})


# --------------------------------------------- R21: the privacy guard, every rule


def _state_with_a_private_issue(path: Path, state_repo: str) -> Path:
    path.mkdir(parents=True)
    write_durable(path, ScopeDurable(state_repo=state_repo))
    (path / "judgements.yaml").write_text(
        'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "secret#7": {tier: 1}\n'
    )
    facts = Facts(
        scope="example-org--secret",
        kind="repo",
        collected_at="2026-11-25T00:00:00+00:00",
        repos=["example-org/secret"],
        issues=[
            Issue(repo="example-org/secret", number=7, title="t", state="open",
                  url="https://github.com/example-org/secret/issues/7")
        ],
        visibility={"example-org/secret": "private"},
    )  # fmt: skip
    (path / "facts.json").write_text(json.dumps(facts.to_json()))
    return path


class _Visibility:
    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers

    def repo_visibility(self, repo: str) -> str:
        return self.answers[repo]


def _push_chosen(tmp_path: Path, chosen: str, visibility: dict[str, str]) -> str:
    scope = Scope(kind="repo", target="example-org/secret")
    state = _state_with_a_private_issue(tmp_path / "state", chosen)
    subprocess.run(["git", "init", "--quiet", str(state)], check=True)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(origin)], check=True)
    return push_state(state, str(origin), "s-0123abcd", expected_old=None, scope=scope,
                      state_repo=chosen, client=_Visibility(visibility))  # fmt: skip


@pytest.mark.parametrize("rule", ["declared", "stealth"])
def test_the_privacy_guard_refuses_a_public_state_repo_whichever_rule_chose_it(
    tmp_path: Path, rule: str
) -> None:
    chosen = decide_state_repo(
        ["example-org/secret"],
        {},
        None,
        declared="example-org/public-refs" if rule == "declared" else None,
        stealth="example-org/public-refs" if rule == "stealth" else None,
    )
    assert chosen == "example-org/public-refs"

    with pytest.raises(PrivacyError):
        _push_chosen(tmp_path, chosen, {chosen: "public", "example-org/secret": "private"})


def test_the_one_repo_default_is_guarded_too_and_passes_for_its_own_private_repo(
    tmp_path: Path,
) -> None:
    chosen = decide_state_repo(["example-org/secret"], {}, None)
    assert chosen == "example-org/secret"

    assert _push_chosen(tmp_path, chosen, {chosen: "private"})


# ------------------------------------ review p6-r5: stealth never reads the product repo


def _declaration_reads(forge: Any) -> list[dict[str, Any]]:
    """Reads of the product repo's settings at its default branch, where the declaration is
    (the quiet switch probe of the triage config read, at `fr-config`, is another read)."""
    return [
        kw
        for kw in forge.called("read_file_at_ref")
        if kw["path"] == SETTINGS and kw["ref"] == "HEAD"
    ]


def test_p6_r5_under_stealth_the_product_repos_declaration_is_never_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A product repo's `.fr/settings.yaml` may not decide where a stealth workspace's state
    is pushed: the tracking repo wins, and the product file is not even read."""
    forge = _forge({(REPO, SETTINGS, "HEAD"): DECLARED})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(state_home, "stealth_tracking", lambda start: (True, "example-org/track"))
    monkeypatch.setattr(state_home, "stealth_declared_state_repo", lambda start: None)
    state = tmp_path / "s"

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == "example-org/track"
    assert not _declaration_reads(forge)
    assert load_facts(state / "facts.json").state_repo_declared == {}


def test_p6_r5_a_stealth_space_declaration_counts_only_without_a_forge_tracking_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge({(REPO, SETTINGS, "HEAD"): DECLARED})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(state_home, "stealth_tracking", lambda start: (True, None))
    monkeypatch.setattr(
        state_home, "stealth_declared_state_repo", lambda start: "example-org/operator-refs"
    )
    state = tmp_path / "s"

    assert _collect(state).exit_code == 0
    assert load_durable(state).state_repo == "example-org/operator-refs"
    assert not _declaration_reads(forge)


def test_p6_r5_the_tracking_repo_wins_over_any_declaration() -> None:
    got = decide_state_repo(["o/one"], {}, _never, declared="o/refs", stealth="o/track")
    assert got == "o/track"


def test_p6_r5_outside_stealth_there_is_no_stealth_declaration(tmp_path: Path) -> None:
    assert state_home.stealth_declared_state_repo(_clone(tmp_path)) is None
    assert state_home.stealth_declared_state_repo(tmp_path / "nowhere") is None
