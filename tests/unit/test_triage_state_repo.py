"""Durable settings and where the state ref lives (spec 2026-10-07-cloud-triage R6, R7,
R11, §B, Test Plan 6).

Remotes are bare repos under `tmp_path`; the forge is faked (`FakeForge`) or answered
from the captured REST fixture of `repos/derio-net/super-fr`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd
from fr.real_ghrestclient import RealGhRestClient
from fr.triage.errors import TriageError
from fr.triage.model import Scope, load_facts
from fr.triage.scope_config import (
    SCOPE_DURABLE_FILE,
    ScopeConfig,
    ScopeDurable,
    load_durable,
    load_scope_config,
    write_durable,
)
from fr.triage.state_ref import NEW_REPO, decide_state_repo, fetch_state, push_state
from pydantic import ValidationError
from typer.testing import CliRunner

from tests.unit.github_rest_support import FixtureGh
from tests.unit.triage_fixtures import ISSUES, PRS, FakeForge

SCOPE_ID = "s-0123abcd"


class _Private:
    """A forge that answers every repo private: the privacy guard lets every push through."""

    def repo_visibility(self, repo: str) -> str:
        return "private"


PRIVATE: dict[str, Any] = {
    "scope": Scope(kind="repo", target="o/r"),
    "state_repo": "o/r",
    "client": _Private(),
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("FR_FORGE_API", raising=False)
    return h


# ------------------------------------------------------------- the settings


def test_scope_config_accepts_state_repo_and_forge_api() -> None:
    config = ScopeConfig.model_validate({"state_repo": "derio-net/super-fr", "forge_api": "rest"})
    assert (config.state_repo, config.forge_api) == ("derio-net/super-fr", "rest")
    assert ScopeConfig().state_repo is None and ScopeConfig().forge_api is None
    with pytest.raises(ValidationError):
        ScopeConfig.model_validate({"forge_api": "soap"})


def test_scope_durable_round_trips_both(tmp_path: Path) -> None:
    assert load_durable(tmp_path) == ScopeDurable()
    write_durable(tmp_path, ScopeDurable(state_repo="derio-net/super-fr", forge_api="rest"))

    assert SCOPE_DURABLE_FILE == "scope-durable.yaml"
    assert load_durable(tmp_path) == ScopeDurable(state_repo="derio-net/super-fr", forge_api="rest")


def test_a_malformed_scope_durable_is_refused_naming_it(tmp_path: Path) -> None:
    (tmp_path / SCOPE_DURABLE_FILE).write_text("state_repo: [x]\n")
    with pytest.raises(TriageError, match=SCOPE_DURABLE_FILE):
        load_durable(tmp_path)


# ------------------------------------------------------------- the decision


def _never(*a: Any) -> str:
    raise AssertionError("no question may be asked")


def test_one_repo_is_its_own_state_repo_without_a_question() -> None:
    assert decide_state_repo(["o/one"], {"o/one": "private"}, _never) == "o/one"
    assert decide_state_repo(["o/one"], {}, None) == "o/one"


def test_a_mixed_set_asks_among_the_private_ones_only() -> None:
    asked: list[tuple[list[str], str | None]] = []

    def ask(question: str, choices: list[str], warning: str | None) -> str:
        asked.append((choices, warning))
        return "o/secret-b"

    got = decide_state_repo(
        ["o/pub", "o/secret-b", "o/secret-a"],
        {"o/pub": "public", "o/secret-a": "private", "o/secret-b": "internal"},
        ask,
    )

    assert got == "o/secret-b"
    assert asked == [(["o/secret-a", "o/secret-b"], None)]


def test_all_public_asks_between_a_new_repo_and_each_public_one_and_warns() -> None:
    asked: list[tuple[list[str], str | None]] = []

    def ask(question: str, choices: list[str], warning: str | None) -> str:
        asked.append((choices, warning))
        return "o/b"

    got = decide_state_repo(["o/b", "o/a"], {"o/a": "public", "o/b": "public"}, ask)

    assert got == "o/b"
    [(choices, warning)] = asked
    assert choices == [NEW_REPO, "o/a", "o/b"]
    assert warning is not None and "private" in warning and "leak" in warning


def test_a_new_repo_answer_is_the_name_the_operator_gave() -> None:
    got = decide_state_repo(
        ["o/a", "o/b"], {"o/a": "public", "o/b": "public"}, lambda q, c, w: "o/triage-refs"
    )
    assert got == "o/triage-refs"


def test_an_answer_outside_the_choices_is_refused() -> None:
    with pytest.raises(TriageError, match="o/pub"):
        decide_state_repo(
            ["o/pub", "o/sec"], {"o/pub": "public", "o/sec": "private"}, lambda q, c, w: "o/pub"
        )


def test_non_interactive_decides_nothing() -> None:
    assert decide_state_repo(["o/a", "o/b"], {"o/a": "private"}, None) is None


# --------------------------------------------------- restore recovers them


def _clone(tmp_path: Path, name: str, origin: Path) -> Path:
    path = tmp_path / name
    _git(tmp_path, "clone", "--quiet", str(origin), str(path))
    return path


def test_a_restore_recovers_state_repo_and_forge_api_and_writes_forge_yaml_if_absent(
    tmp_path: Path, home: Path
) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(origin))
    a = _clone(tmp_path, "a", origin)
    state_a = a / ".fr" / "triage-state" / "scope"
    state_a.mkdir(parents=True)
    write_durable(state_a, ScopeDurable(state_repo="derio-net/super-fr", forge_api="rest"))
    push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    (state_b).mkdir(parents=True)
    (state_b / "scope.yaml").write_text("# mine\nclaim_expiry_hours: 12\n")
    forge_yaml = home / ".config" / "fr" / "forge.yaml"
    fetch_state(state_b, str(origin), SCOPE_ID)

    assert load_durable(state_b) == ScopeDurable(state_repo="derio-net/super-fr", forge_api="rest")
    assert forge_yaml.read_text() == "api: rest\n"
    config = load_scope_config(state_b)
    assert config.state_repo == "derio-net/super-fr" and config.claim_expiry_hours == 12
    assert (state_b / "scope.yaml").read_text().startswith("# mine\n")


def test_a_restore_never_overwrites_an_existing_forge_yaml(tmp_path: Path, home: Path) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(origin))
    a = _clone(tmp_path, "a", origin)
    state_a = a / ".fr" / "triage-state" / "scope"
    state_a.mkdir(parents=True)
    write_durable(state_a, ScopeDurable(state_repo="derio-net/super-fr", forge_api="rest"))
    push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    forge_yaml = home / ".config" / "fr" / "forge.yaml"
    forge_yaml.parent.mkdir(parents=True)
    forge_yaml.write_text("api: graphql\n")

    fetch_state(_clone(tmp_path, "b", origin) / ".fr" / "s", str(origin), SCOPE_ID)

    assert forge_yaml.read_text() == "api: graphql\n"


# ------------------------------------------------------- the forge's answer


def test_the_rest_client_reads_visibility_from_get_repos() -> None:
    fake = FixtureGh()
    assert RealGhRestClient(run=fake).repo_visibility("derio-net/super-fr") == "public"
    assert fake.calls == [["api", "repos/derio-net/super-fr"]]


def test_the_graphql_client_reads_visibility_from_repo_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr import gh as _gh
    from fr.real_ghclient import RealGhClient

    seen: list[list[str]] = []

    def fake(args: list[str], *a: Any, **kw: Any) -> str:
        seen.append(args)
        return json.dumps({"visibility": "PRIVATE"})

    monkeypatch.setattr(_gh, "_run_gh", fake)
    assert RealGhClient().repo_visibility("o/r") == "private"
    assert seen == [["repo", "view", "o/r", "--json", "visibility"]]


# ------------------------------------------------- collect records and decides

REPO = "derio-net/super-fr"
GROUP = ["example-org/alpha", "example-org/beta"]


def _forge(repos: list[str], visibility: dict[str, str]) -> FakeForge:
    return FakeForge(
        issues={r: list(ISSUES) if r == REPO else [] for r in repos},
        prs={r: list(PRS) if r == REPO else [] for r in repos},
        visibility=visibility,
    )


def test_collect_records_each_repos_visibility_and_decides_a_single_repo(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge([REPO], {REPO: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    result = CliRunner().invoke(app, ["triage", "collect", "--repo", REPO, "--dir", str(state)])

    assert result.exit_code == 0, result.output
    assert load_facts(state / "facts.json").visibility == {REPO: "public"}
    assert load_durable(state).state_repo == REPO
    assert load_scope_config(state).state_repo == REPO
    assert forge.visibility_calls == [REPO]


def test_collect_of_a_group_non_interactive_warns_once_and_keeps_state_local(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge(GROUP, {GROUP[0]: "private", GROUP[1]: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    state = tmp_path / "s"

    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", ",".join(GROUP), "--dir", str(state)]
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("no state repo") == 1
    assert not (state / SCOPE_DURABLE_FILE).exists()
    assert not (state / "scope.yaml").exists()


def test_collect_of_a_group_asks_when_interactive_and_records_the_answer(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge(GROUP, {GROUP[0]: "private", GROUP[1]: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    asked: list[list[str]] = []

    def ask(question: str, choices: list[str], warning: str | None) -> str:
        asked.append(choices)
        return choices[0]

    monkeypatch.setattr(triage_cmd, "state_repo_prompt", lambda: ask)
    state = tmp_path / "s"

    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", ",".join(GROUP), "--dir", str(state)]
    )

    assert result.exit_code == 0, result.output
    assert asked == [[GROUP[0]]]
    assert load_durable(state).state_repo == GROUP[0]
    assert load_scope_config(state).state_repo == GROUP[0]


def test_a_decided_state_repo_is_not_asked_again(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge(GROUP, {GROUP[0]: "private", GROUP[1]: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(triage_cmd, "state_repo_prompt", lambda: _never)
    state = tmp_path / "s"
    write_durable(state, ScopeDurable(state_repo=GROUP[0]))

    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", ",".join(GROUP), "--dir", str(state)]
    )

    assert result.exit_code == 0, result.output
    assert "no state repo" not in result.output


# ------------------------------------- decided on an explicit collect only (p3-r7)


def test_a_loop_collect_never_decides_and_warns_once_per_pass(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The drive and watch loops collect through `collect_into`: even a single repo, which
    an explicit collect decides with no question, stays undecided there, warned once."""
    forge = _forge([REPO], {REPO: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(triage_cmd, "state_repo_prompt", lambda: _never)
    state = tmp_path / "s"

    triage_cmd.collect_into(Scope(kind="repo", target=REPO), state, carry=True, lenient=True)

    assert not (state / SCOPE_DURABLE_FILE).exists()
    assert capsys.readouterr().err.count("no state repo") == 1


@pytest.mark.parametrize("loop", ["drive", "watch"])
def test_the_drive_and_watch_loops_never_settle_the_state_repo(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch, loop: str
) -> None:
    from fr.commands import triage_batch_cmd, triage_kanban_cmd

    forge = _forge([REPO], {REPO: "public"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)

    def refuse(*a: Any) -> None:
        raise AssertionError("a loop's collect settled the state repo")

    monkeypatch.setattr(triage_cmd, "_settle_state_repo", refuse)
    scope, state = Scope(kind="repo", target=REPO), tmp_path / "s"

    if loop == "drive":
        triage_batch_cmd.recollect(scope, state)
    else:
        triage_kanban_cmd.recollect(scope, state)

    assert (state / "facts.json").exists()


# --------------------------------- visibility from the repo list (p3-r9)


def test_an_org_collect_takes_visibility_from_the_repo_list_with_no_get(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = FakeForge(
        issues={"example-org/a": [], "example-org/b": []},
        prs={"example-org/a": [], "example-org/b": []},
        repos=[
            {"name": "a", "isArchived": False, "visibility": "PRIVATE"},
            {"name": "b", "isArchived": False, "visibility": "public"},
        ],
    )
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(triage_cmd, "state_repo_prompt", lambda: None)
    state = tmp_path / "s"

    result = CliRunner().invoke(
        app, ["triage", "collect", "--org", "example-org", "--dir", str(state)]
    )

    assert result.exit_code == 0, result.output
    assert load_facts(state / "facts.json").visibility == {
        "example-org/a": "private",
        "example-org/b": "public",
    }
    assert forge.visibility_calls == []


def test_a_repo_the_list_carries_no_visibility_for_is_read_once(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = FakeForge(
        issues={"example-org/a": [], "example-org/b": []},
        prs={"example-org/a": [], "example-org/b": []},
        repos=[{"name": "a", "isArchived": False}, {"name": "b", "isArchived": False,
                                                       "visibility": "public"}],
        visibility={"example-org/a": "internal"},
    )  # fmt: skip
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(triage_cmd, "state_repo_prompt", lambda: None)
    state = tmp_path / "s"

    result = CliRunner().invoke(
        app, ["triage", "collect", "--org", "example-org", "--dir", str(state)]
    )

    assert result.exit_code == 0, result.output
    assert load_facts(state / "facts.json").visibility["example-org/a"] == "internal"
    assert forge.visibility_calls == ["example-org/a"]


def test_the_graphql_repo_list_asks_for_visibility(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr import gh as _gh

    seen: list[list[str]] = []

    def fake(args: list[str]) -> str:
        seen.append(args)
        return json.dumps([{"name": "a", "isArchived": False, "visibility": "PRIVATE"}])

    monkeypatch.setattr(_gh, "_run_gh", fake)

    assert _gh.list_repos(owner="o", include_archived=True) == [
        {"name": "a", "isArchived": False, "visibility": "private"}
    ]
    assert seen[0][4] == "name,isArchived,visibility"


def test_the_rest_repo_list_keeps_visibility() -> None:
    def run(argv: list[str]) -> str:
        assert "orgs/o/repos" in argv[-1], argv
        return json.dumps(
            [
                {"name": "a", "archived": False, "visibility": "private"},
                {"name": "b", "archived": True, "private": False},
            ]
        )

    assert RealGhRestClient(run=run).list_repos("o", 10) == [
        {"name": "a", "isArchived": False, "visibility": "private"},
        {"name": "b", "isArchived": True, "visibility": "public"},
    ]
