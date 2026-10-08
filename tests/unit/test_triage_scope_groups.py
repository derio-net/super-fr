"""Scope groups (spec 2026-10-02-wave-driver §H, R15): `--repo A/B,C/D` is one scope.

The forge is faked (`tests.unit.triage_fixtures.FakeForge`); nothing here reaches `gh`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.triage.collect import collect_facts
from fr.triage.errors import ForgeError
from fr.triage.model import (
    FACTS_SCHEMA,
    Facts,
    Issue,
    Scope,
    load_facts,
    load_judgements,
    state_dir,
)
from typer.testing import CliRunner

from tests.unit.triage_fixtures import NOW, FakeForge

ALPHA, BETA = "example-org/alpha", "other-org/beta"
GROUP = f"{ALPHA},{BETA}"


def _issue(repo: str, number: int) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"issue {number}",
        "labels": [],
        "url": f"https://github.com/{repo}/issues/{number}",
    }


def _forge(**kw: Any) -> FakeForge:
    return FakeForge(
        issues={ALPHA: [_issue(ALPHA, 1)], BETA: [_issue(BETA, 2)]},
        prs={ALPHA: [], BETA: []},
        **kw,
    )


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


# ----------------------------------------------------------- the scope itself


def test_a_group_scope_name_is_the_sorted_owner_repo_slugs_joined_by_plus(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    forward = Scope.group([BETA, ALPHA])
    backward = Scope.group([ALPHA, BETA.upper()])
    assert forward.kind == "group"
    assert forward.name == "example-org--alpha+other-org--beta"
    assert backward.name == forward.name  # order and case do not move the directory
    assert state_dir(forward, workspace=tmp_path).name == forward.name
    assert state_dir(forward, Path("/elsewhere")) == Path("/elsewhere")  # --dir overrides


def test_a_group_name_over_80_characters_is_shortened_with_an_eight_character_hash() -> None:
    repos = [f"organisation-number-{i}/a-rather-long-repository-name-{i}" for i in range(3)]
    name = Scope.group(repos).name
    assert len(name) <= 80
    assert name != "+".join(sorted(r.replace("/", "--") for r in repos))
    assert name == Scope.group(reversed(repos)).name  # still stable
    other = Scope.group([*repos[:2], "organisation-number-9/a-rather-long-repository-name-9"])
    assert other.name != name  # the hash tells two long groups apart
    head, _, digest = name.rpartition("-")
    assert len(digest) == 8 and head


def test_a_group_with_a_repeated_repo_name_is_refused_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _forge()
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", "one/same,two/same", "--dir", str(tmp_path / "s")]
    )
    assert result.exit_code == 2
    assert "same" in result.output
    assert not (tmp_path / "s").exists() and forge.calls == []
    subprocess.run(["git", "init", "--quiet", str(tmp_path / "ws")], check=True)
    monkeypatch.chdir(tmp_path / "ws")
    default = state_dir(Scope.group(["one/same", "two/same"]))
    assert not default.exists()


@pytest.mark.parametrize("bad", ["a/b,c", "a/b,", "a/b,c/d/e"])
def test_a_malformed_group_member_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setattr(triage_cmd, "make_forge", _forge)
    result = CliRunner().invoke(app, ["triage", "collect", "--repo", bad, "--dir", str(tmp_path)])
    assert result.exit_code == 2
    assert not (tmp_path / "facts.json").exists()


# ----------------------------------------------------------- collect and facts 4


def test_collect_reads_each_repo_in_turn_and_records_a_failed_repo_as_skipped() -> None:
    forge = _forge(failing={BETA: "HTTP 502"})
    facts = collect_facts(forge, Scope.group([BETA, ALPHA]), now=NOW)
    assert facts.kind == "group" and facts.schema_ == FACTS_SCHEMA == 8
    assert facts.scope == "example-org--alpha+other-org--beta"
    assert facts.repos == [ALPHA, BETA]
    assert [(s.repo, s.reason) for s in facts.skipped] == [(BETA, "HTTP 502")]
    assert [i.repo for i in facts.issues] == [ALPHA]
    assert [kw["repo"] for kw in forge.called("list_issues")] == [ALPHA, BETA]
    assert forge.called("list_repos") == []  # a group never lists an owner


def test_a_group_in_which_no_repo_could_be_read_is_an_error() -> None:
    forge = _forge(failing={ALPHA: "HTTP 502", BETA: "HTTP 503"})
    with pytest.raises(ForgeError, match="no repo of the group could be read"):
        collect_facts(forge, Scope.group([ALPHA, BETA]), now=NOW)


def test_facts_4_round_trips_and_schema_3_still_loads_then_is_upgraded_by_collect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "facts.json"
    old = {
        "schema": 3,
        "scope": "example-org--alpha",
        "kind": "repo",
        "collected_at": "2026-09-21T00:00:00+00:00",
        "repos": [ALPHA],
        "issues": [],
    }
    path.write_text(json.dumps(old), encoding="utf-8")
    assert load_facts(path).schema_ == 3

    monkeypatch.setattr(triage_cmd, "make_forge", _forge)
    result = CliRunner().invoke(app, ["triage", "collect", "--repo", GROUP, "--dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    written = json.loads(path.read_text(encoding="utf-8"))
    assert (written["schema"], written["kind"], written["repos"]) == (8, "group", [ALPHA, BETA])
    assert load_facts(path).kind == "group"


def test_a_schema_3_file_cannot_claim_the_group_kind(tmp_path: Path) -> None:
    doc = {
        "schema": 3,
        "scope": "x",
        "kind": "group",
        "collected_at": "2026-09-21T00:00:00+00:00",
        "repos": [ALPHA, BETA],
        "issues": [],
    }
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    from fr.triage.errors import TriageError

    with pytest.raises(TriageError, match="schema 4"):
        load_facts(path)


# ----------------------------------------------------------- check, render, drive


def _issue_model(repo: str, number: int) -> Issue:
    return Issue(
        repo=repo,
        number=number,
        title=f"issue {number}",
        state="open",
        url=f"https://github.com/{repo}/issues/{number}",
    )


def _group_state(
    tmp_path: Path, *batches: str, alpha: tuple[int, ...] = (1,), beta: tuple[int, ...] = (2,)
) -> Path:
    keys = [(ALPHA, "alpha", n) for n in alpha] + [(BETA, "beta", n) for n in beta]
    facts = Facts(
        schema=4,
        scope=Scope.group([ALPHA, BETA]).name,
        kind="group",
        collected_at=NOW.isoformat(),
        repos=[ALPHA, BETA],
        issues=[_issue_model(repo, n) for repo, _, n in keys],
    )
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers:\n  - {n: 1, title: Now}\nissues:\n"
        + "".join(f"  {name}#{n}: {{tier: 1}}\n" for _, name, n in keys)
        + ("batches:\n" + "".join(batches) if batches else ""),
        encoding="utf-8",
    )
    return tmp_path


LAUNCH = "{runner: fake, harness: claude, model: claude-opus-5-5}"


def _batch(bid: str, key: str, **kw: Any) -> str:
    extra = "".join(f"    {k}: {v}\n" for k, v in kw.items())
    return (
        f'  - id: {bid}\n    title: {bid}\n    ids: ["{key}"]\n    wave: 1\n'
        f"    launch: {LAUNCH}\n{extra}"
    )


def test_check_and_render_run_over_a_two_repo_group(tmp_path: Path) -> None:
    _group_state(tmp_path)
    check = CliRunner().invoke(app, ["triage", "check", "--repo", GROUP, "--dir", str(tmp_path)])
    assert check.exit_code == 0, check.output
    render = CliRunner().invoke(app, ["triage", "render", "--repo", GROUP, "--dir", str(tmp_path)])
    assert render.exit_code == 0, render.output
    html = (tmp_path / "triage.html").read_text(encoding="utf-8")
    assert "group scope" in html and "alpha" in html and "beta" in html


def test_batch_list_and_create_work_over_a_group_and_stay_single_repo(tmp_path: Path) -> None:
    _group_state(tmp_path)
    created = CliRunner().invoke(
        app,
        [
            "triage",
            "batch",
            "create",
            "one",
            "--issue",
            "alpha#1",
            "--title",
            "one",
            "--repo",
            GROUP,
        ]
        + ["--dir", str(tmp_path)],
    )
    assert created.exit_code == 0, created.output
    listed = CliRunner().invoke(
        app, ["triage", "batch", "list", "--repo", GROUP, "--dir", str(tmp_path)]
    )
    assert listed.exit_code == 0 and "one" in listed.output
    mixed = CliRunner().invoke(
        app,
        [
            "triage",
            "batch",
            "create",
            "two",
            "--issue",
            "alpha#1",
            "--issue",
            "beta#2",
            "--title",
            "two",
        ]
        + ["--repo", GROUP, "--dir", str(tmp_path)],
    )
    assert mixed.exit_code == 2
    assert [b.id for b in load_judgements(tmp_path / "judgements.yaml").batches] == ["one"]


def _drive(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "drive", *args, "--repo", GROUP, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


@pytest.fixture
def _no_forge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(triage_batch_cmd, "recollect", lambda scope, target: None)


def _clones(tmp_path: Path, *repos: str) -> list[str]:
    out: list[str] = []
    for r in repos:
        path = tmp_path / "clones" / r.replace("/", "--")
        path.mkdir(parents=True)
        out += ["--checkout", f"{r}={path}"]
    return out


def test_drive_plans_both_repos_of_a_group_against_one_shared_cap(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path, _batch("ba", "alpha#1"), _batch("bb", "beta#2"))
    clones = _clones(tmp_path, ALPHA, BETA)
    code, out = _drive(tmp_path, *clones)
    assert code == 0, out
    assert "dispatch ba: wave 1" in out and "dispatch bb: wave 1" in out

    code, out = _drive(tmp_path, *clones, "--max-inflight", "1")
    assert code == 0, out
    lines = [line for line in out.splitlines() if line.startswith("dispatch ")]
    assert len(lines) == 1  # one cap for both repos, not one each


def test_a_dispatched_batch_in_one_repo_uses_the_cap_of_the_other(
    tmp_path: Path, _no_forge: None
) -> None:
    event = (
        "    events:\n      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: fake, "
        "handle: h, branch: feat/batch-ba}\n"
    )
    _group_state(tmp_path, _batch("ba", "alpha#1") + event, _batch("bb", "beta#2"))
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA, BETA), "--max-inflight", "1")
    assert code in (0, 3), out
    assert "dispatch bb" not in out
    # Held by the other repo's batch, not merely absent (gh#884).
    assert "held bb: the in-flight cap (1) is full: ba" in out


def _dispatched(bid: str) -> str:
    return (
        "    events:\n      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: fake, "
        f"handle: h-{bid}, branch: feat/batch-{bid}}}\n"
    )


def test_a_fifth_batch_is_held_by_four_in_flight_across_two_owners(
    tmp_path: Path, _no_forge: None
) -> None:
    """gh#884: two in flight per repo (and per owner) is under a cap of 4 each, so
    per-repo or per-owner counting would dispatch the fifth; the group's one cap holds
    it. The control run proves the fifth is dispatchable, so the hold is the cap's."""
    state = [
        _batch("a1", "alpha#1") + _dispatched("a1"),
        _batch("a2", "alpha#3") + _dispatched("a2"),
        _batch("b1", "beta#2") + _dispatched("b1"),
        _batch("b2", "beta#4") + _dispatched("b2"),
        _batch("b5", "beta#6"),
    ]
    _group_state(tmp_path, *state, alpha=(1, 3), beta=(2, 4, 6))
    clones = _clones(tmp_path, ALPHA, BETA)
    code, out = _drive(tmp_path, *clones)
    assert code in (0, 3), out
    assert "dispatch b5" not in out
    assert "held b5: the in-flight cap (4) is full: a1, a2, b1, b2" in out

    code, out = _drive(tmp_path, *clones, "--max-inflight", "5")
    assert code in (0, 3), out
    assert "dispatch b5: wave 1" in out


def test_drive_refuses_a_group_repo_with_no_checkout_before_anything_runs(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path, _batch("ba", "alpha#1"), _batch("bb", "beta#2"))
    before = (tmp_path / "judgements.yaml").read_text(encoding="utf-8")
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA))
    assert code == 2
    assert BETA in out and "--checkout" in out
    assert (tmp_path / "judgements.yaml").read_text(encoding="utf-8") == before


def test_drive_needs_a_checkout_for_every_repo_of_the_group_even_one_with_no_batch(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path, _batch("ba", "alpha#1"))  # beta has no batch at all
    before = (tmp_path / "judgements.yaml").read_text(encoding="utf-8")
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA))
    assert code == 2
    assert BETA in out and "--checkout" in out
    assert "dispatch ba" not in out
    assert (tmp_path / "judgements.yaml").read_text(encoding="utf-8") == before


def test_drive_over_a_group_with_no_batches_still_refuses_an_unmapped_repo(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path)
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA))
    assert code == 2
    assert BETA in out and "--checkout" in out


def test_drive_over_a_group_with_no_batches_runs_when_every_repo_is_mapped(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path)
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA, BETA))
    assert code in (0, 3), out


def test_group_casing_and_order_do_not_change_name_target_or_repos() -> None:
    spellings = [
        ["Org/Repo", "org/repo", "Other/Two"],
        ["org/repo", "Org/Repo", "other/two"],
        ["OTHER/TWO", "ORG/REPO"],
    ]
    scopes = [Scope.group(s) for s in spellings]
    for sc in scopes[1:]:
        assert (sc.name, sc.target, sc.repos) == (
            scopes[0].name,
            scopes[0].target,
            scopes[0].repos,
        )
    assert scopes[0].repos == ("org/repo", "other/two")


def test_drive_refuses_a_checkout_for_a_repo_outside_the_group(
    tmp_path: Path, _no_forge: None
) -> None:
    _group_state(tmp_path, _batch("ba", "alpha#1"))
    code, out = _drive(tmp_path, *_clones(tmp_path, ALPHA, BETA, "elsewhere/gamma"))
    assert code == 2
    assert "elsewhere/gamma" in out
