"""The privacy guard (spec 2026-10-07-cloud-triage R8, §C, Test Plan 7).

A private repo's issue must never reach a public state repo: not into a batch, a wave or
a judgement write, and not through a push of the state ref or a state export. The forge
is `tests.unit.fakes.FakeGhClient` (visibility per repo; a repo it does not know cannot
be read), or the captured `GET repos/derio-net/super-fr` where the route itself is the
point. Remotes are bare repos under `tmp_path`.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.real_ghrestclient import RealGhRestClient
from fr.triage.errors import TriageError
from fr.triage.model import Facts, Issue, Scope, load_judgements
from fr.triage.privacy import (
    PrivacyError,
    VisibilityUnreadable,
    carried_files,
    leak_risk,
    refusal,
)
from fr.triage.scope_config import ScopeDurable, write_durable
from fr.triage.state_ref import REF_FILES, push_state, ref_name
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.github_rest_support import FixtureGh

OPEN_REPO = "derio-net/super-fr"
SECRET = "example-org/secret"
REFS = "example-org/refs"
GROUP = f"{OPEN_REPO},{SECRET}"
SCOPE = Scope.group([OPEN_REPO, SECRET])
SCOPE_ID = "s-0123abcd"

JUDGEMENTS = """\
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "super-fr#1": {tier: 1}
  "secret#7": {tier: 1}
  "secret#8": {tier: 1}
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _facts(visibility: dict[str, str] | None = None) -> Facts:
    def issue(repo: str, n: int) -> Issue:
        return Issue(
            repo=repo,
            number=n,
            title=f"issue {n}",
            state="open",
            url=f"https://github.com/{repo}/issues/{n}",
            author_association="OWNER",  # intake admits a maintainer's issue
        )

    return Facts(
        viewer="operator",
        scope=SCOPE.name,
        kind="group",
        collected_at="2026-10-08T12:00:00+00:00",
        repos=[OPEN_REPO, SECRET],
        issues=[issue(OPEN_REPO, 1), issue(SECRET, 7), issue(SECRET, 8)],
        visibility=visibility
        if visibility is not None
        else {OPEN_REPO: "public", SECRET: "private"},
    )


def _state(
    state: Path, *, state_repo: str | None, facts: Facts | None = None, with_facts: bool = True
) -> Path:
    state.mkdir(parents=True, exist_ok=True)
    (state / "judgements.yaml").write_text(JUDGEMENTS, encoding="utf-8")
    if with_facts:
        (state / "facts.json").write_text(json.dumps((facts or _facts()).to_json()), "utf-8")
    if state_repo is not None:
        write_durable(state, ScopeDurable(state_repo=state_repo))
    return state


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGhClient:
    client = FakeGhClient()
    client.visibility = {OPEN_REPO: "public", SECRET: "private", REFS: "private"}
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: client)
    return client


def _batch(state: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", *args, "--repo", GROUP, "--dir", str(state)]
    )
    return result.exit_code, " ".join(result.output.split())


def _names_all(out: str, state_repo: str) -> None:
    assert "secret#7" in out and SECRET in out and state_repo in out, out


# ------------------------------------------------------------- the predicate


def test_leak_risk_is_a_private_key_into_a_public_state_repo() -> None:
    vis = {OPEN_REPO: "public", SECRET: "private", "o/int": "internal", REFS: "private"}
    assert leak_risk({"secret#7": SECRET}, OPEN_REPO, vis)
    assert leak_risk({"int#1": "o/int"}, OPEN_REPO, vis)  # internal is not public
    assert not leak_risk({"secret#7": SECRET}, REFS, vis)
    assert not leak_risk({"super-fr#1": OPEN_REPO}, OPEN_REPO, vis)
    assert not leak_risk({}, OPEN_REPO, vis)


def test_the_refusal_names_the_issue_its_repo_and_the_state_repo() -> None:
    message = refusal("secret#7", SECRET, OPEN_REPO)
    assert "secret#7" in message and SECRET in message and OPEN_REPO in message


# ------------------------------------------------- batch, wave and judgement writes


def test_batch_create_of_a_private_issue_into_a_public_state_repo_exits_2(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    state = _state(tmp_path / "s", state_repo=OPEN_REPO)
    before = (state / "judgements.yaml").read_bytes()

    code, out = _batch(state, "create", "b1", "--title", "t", "--issue", "secret#7")

    assert code == 2
    _names_all(out, OPEN_REPO)
    assert (state / "judgements.yaml").read_bytes() == before


def test_batch_create_proceeds_when_the_state_repo_is_private(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    state = _state(tmp_path / "s", state_repo=REFS)

    code, out = _batch(state, "create", "b1", "--title", "t", "--issue", "secret#7")

    assert code == 0, out
    assert [b.id for b in load_judgements(state / "judgements.yaml").batches] == ["b1"]
    assert ("repo_visibility", {"repo": REFS}) in gh.calls  # outside the scope: read live


def test_batch_create_with_no_state_repo_is_never_checked(tmp_path: Path, gh: FakeGhClient) -> None:
    state = _state(tmp_path / "s", state_repo=None)

    code, out = _batch(state, "create", "b1", "--title", "t", "--issue", "secret#7")

    assert code == 0, out
    assert not [c for c in gh.calls if c[0] == "repo_visibility"]


def test_batch_edit_add_issue_exits_2(tmp_path: Path, gh: FakeGhClient) -> None:
    """A batch judged before the state repo was chosen gains a private member: refused."""
    state = _state(tmp_path / "s", state_repo=None)
    assert _batch(state, "create", "b1", "--title", "t", "--issue", "secret#8")[0] == 0
    write_durable(state, ScopeDurable(state_repo=OPEN_REPO))
    before = (state / "judgements.yaml").read_bytes()

    code, out = _batch(state, "edit", "b1", "--add-issue", "secret#7")

    assert code == 2
    _names_all(out, OPEN_REPO)
    assert (state / "judgements.yaml").read_bytes() == before


def test_the_wave_setter_exits_2(tmp_path: Path, gh: FakeGhClient) -> None:
    """A batch judged before the state repo was chosen: putting it in a wave is refused."""
    state = _state(tmp_path / "s", state_repo=None)
    assert _batch(state, "create", "b1", "--title", "t", "--issue", "secret#7")[0] == 0
    write_durable(state, ScopeDurable(state_repo=OPEN_REPO))
    before = (state / "judgements.yaml").read_bytes()

    code, out = _batch(state, "edit", "b1", "--wave", "1")

    assert code == 2
    _names_all(out, OPEN_REPO)
    assert (state / "judgements.yaml").read_bytes() == before


def test_a_judgement_write_adding_a_key_is_refused(tmp_path: Path, gh: FakeGhClient) -> None:
    """Every engine write of judgements.yaml passes `_save`: a key it adds is checked."""
    from fr.triage.model import Batch

    state = _state(tmp_path / "s", state_repo=OPEN_REPO)
    new = Batch.model_validate({"id": "b1", "title": "t", "ids": ["secret#7"]})

    with pytest.raises(PrivacyError, match="secret#7"):
        triage_batch_cmd._save(state, [new], _facts(), read=[])


def test_an_unreadable_state_repo_refuses_a_private_add(tmp_path: Path, gh: FakeGhClient) -> None:
    state = _state(tmp_path / "s", state_repo="example-org/gone")

    code, out = _batch(state, "create", "b1", "--title", "t", "--issue", "secret#7")

    assert code == 2
    assert "example-org/gone" in out


# ------------------------------------------------------------------ push


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(bare))
    return bare


def _workspace(tmp_path: Path, origin: Path) -> Path:
    clone = tmp_path / "ws"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    return clone / ".fr" / "triage-state" / SCOPE.name


def _push(state: Path, origin: Path, state_repo: str, client: Any) -> str:
    return push_state(
        state,
        str(origin),
        SCOPE_ID,
        expected_old=None,
        scope=SCOPE,
        state_repo=state_repo,
        client=client,
    )


def _ref(origin: Path) -> str:
    return _git(origin, "for-each-ref", ref_name(SCOPE_ID))


def test_push_refuses_a_private_key_into_a_public_state_repo(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    state = _state(_workspace(tmp_path, origin), state_repo=OPEN_REPO)

    with pytest.raises(PrivacyError) as exc:
        _push(state, origin, OPEN_REPO, gh)

    _names_all(str(exc.value), OPEN_REPO)
    assert _ref(origin) == ""


def test_push_proceeds_when_the_state_repo_is_private(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    state = _state(_workspace(tmp_path, origin), state_repo=REFS)

    _push(state, origin, REFS, gh)

    assert _ref(origin) != ""


def test_push_reads_the_state_repos_visibility_live_with_get_repos(
    tmp_path: Path, origin: Path
) -> None:
    """Even with facts naming it public, the push asks the forge first (R8): the captured
    `GET repos/derio-net/super-fr` answer is public, so the private key is refused."""
    fake = FixtureGh()
    state = _state(_workspace(tmp_path, origin), state_repo=OPEN_REPO)

    with pytest.raises(PrivacyError):
        _push(state, origin, OPEN_REPO, RealGhRestClient(run=fake))

    assert ["api", "-i", f"repos/{OPEN_REPO}"] in fake.calls
    assert _ref(origin) == ""


def test_push_reads_the_state_repo_live_when_it_is_outside_the_scope(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    gh.visibility[REFS] = "public"
    state = _state(_workspace(tmp_path, origin), state_repo=REFS)

    with pytest.raises(PrivacyError):
        _push(state, origin, REFS, gh)

    assert ("repo_visibility", {"repo": REFS}) in gh.calls


def test_with_no_facts_the_keys_repos_are_read_live_too(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    state = _state(_workspace(tmp_path, origin), state_repo=OPEN_REPO, with_facts=False)

    with pytest.raises(PrivacyError):
        _push(state, origin, OPEN_REPO, gh)

    asked = [c[1]["repo"] for c in gh.calls if c[0] == "repo_visibility"]
    assert asked[0] == OPEN_REPO and SECRET in asked
    assert _ref(origin) == ""


def test_facts_that_say_public_do_not_outvote_the_forge_for_the_state_repo(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    """A state repo made public after the last collect is caught at the next push."""
    gh.visibility[REFS] = "public"
    facts = _facts({OPEN_REPO: "public", SECRET: "private", REFS: "private"})
    state = _state(_workspace(tmp_path, origin), state_repo=REFS, facts=facts)

    with pytest.raises(PrivacyError):
        _push(state, origin, REFS, gh)


def test_an_unreadable_state_repo_visibility_refuses_the_push(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    state = _state(_workspace(tmp_path, origin), state_repo="example-org/gone")

    with pytest.raises(PrivacyError, match="example-org/gone"):
        _push(state, origin, "example-org/gone", gh)

    assert _ref(origin) == ""


def test_an_unreadable_visibility_is_its_own_privacy_error(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    """Unreadable is retryable (gh#1134); a leak is not (R10)."""
    from fr.triage.privacy import guard_state

    state = _state(_workspace(tmp_path, origin), state_repo="example-org/gone")
    with pytest.raises(VisibilityUnreadable) as caught:
        guard_state(state, scope=SCOPE, state_repo="example-org/gone", client_for=lambda r: gh)
    assert isinstance(caught.value, PrivacyError)

    gh.visibility[REFS] = "public"
    state = _state(tmp_path / "state2", state_repo=REFS)
    with pytest.raises(PrivacyError) as leak:
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda r: gh)
    assert not isinstance(leak.value, VisibilityUnreadable)


def test_an_unreadable_judgements_file_refuses_the_push(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    gh.visibility[REFS] = "public"
    state = _state(_workspace(tmp_path, origin), state_repo=REFS)
    (state / "judgements.yaml").write_text("schema: [\n")

    with pytest.raises(TriageError, match="judgements"):
        _push(state, origin, REFS, gh)

    assert _ref(origin) == ""


# ------------------------------------------------------------------ export


def _export(state: Path, to: Path) -> tuple[int, str]:
    result = CliRunner().invoke(
        app,
        ["triage", "state", "export", "--to", str(to), "--repo", GROUP, "--dir", str(state)],
    )
    return result.exit_code, " ".join(result.output.split())


def test_state_export_refuses_a_private_key_with_a_public_state_repo(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    state = _state(tmp_path / "s", state_repo=OPEN_REPO)

    code, out = _export(state, tmp_path / "repo")

    assert code == 2
    _names_all(out, OPEN_REPO)
    assert not (tmp_path / "repo").exists()


def test_state_export_proceeds_with_a_private_state_repo(tmp_path: Path, gh: FakeGhClient) -> None:
    state = _state(tmp_path / "s", state_repo=REFS)

    code, out = _export(state, tmp_path / "repo")

    assert code == 0, out
    assert (tmp_path / "repo" / SCOPE.name / "judgements.yaml").exists()


def test_state_export_with_an_unreadable_state_repo_visibility_exits_2(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    """R9: only a looping drive retries an unreadable visibility; export refuses."""
    state = _state(tmp_path / "s", state_repo="example-org/gone")

    code, out = _export(state, tmp_path / "repo")

    assert code == 2
    assert "cannot read the visibility" in out and "example-org/gone" in out
    assert not (tmp_path / "repo").exists()


def test_guard_state_reads_the_visibility_live_on_every_call(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    """R11: no answer is cached between calls."""
    from fr.triage.privacy import guard_state

    state = _state(tmp_path / "s", state_repo=REFS)
    for _ in range(2):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda r: gh)

    assert [c for c in gh.calls if c == ("repo_visibility", {"repo": REFS})] == [
        ("repo_visibility", {"repo": REFS})
    ] * 2


# ------------------------------------------- a key outside the scope (p3-r8)


def test_a_key_whose_repo_the_scope_does_not_cover_has_its_visibility_read(
    gh: FakeGhClient,
) -> None:
    """A hand-edited key, or one left from a repo removed from the scope: its repo is read
    like any other, and a private one is refused."""
    from fr.triage.privacy import guard_write

    gh.visibility["derio-net/hidden"] = "private"
    scope = Scope(kind="repo", target=OPEN_REPO)

    with pytest.raises(PrivacyError, match="hidden#3"):
        guard_write(
            ["hidden#3"], scope=scope, facts=_facts(), state_repo=OPEN_REPO,
            client_for=lambda _r: gh,
        )  # fmt: skip

    assert ("repo_visibility", {"repo": "derio-net/hidden"}) in gh.calls


def test_a_key_whose_repo_cannot_be_named_or_read_counts_as_private(
    gh: FakeGhClient,
) -> None:
    """A group of two owners cannot name the repo of `nowhere#1`: unreadable, so private."""
    from fr.triage.privacy import guard_write

    scope = Scope.group([OPEN_REPO, "other-org/thing"])

    with pytest.raises(PrivacyError, match="nowhere#1"):
        guard_write(
            ["nowhere#1"], scope=scope, facts=_facts(), state_repo=OPEN_REPO,
            client_for=lambda _r: gh,
        )  # fmt: skip


def test_a_push_carrying_a_key_outside_the_scope_reads_its_repo(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    gh.visibility["derio-net/hidden"] = "private"
    state = _workspace(tmp_path, origin)
    state.mkdir(parents=True)
    (state / "judgements.yaml").write_text(
        'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "hidden#3": {tier: 1}\n'
    )

    with pytest.raises(PrivacyError, match="hidden#3"):
        push_state(
            state, str(origin), SCOPE_ID, expected_old=None,
            scope=Scope(kind="repo", target=OPEN_REPO), state_repo=OPEN_REPO, client=gh,
        )  # fmt: skip

    assert _ref(origin) == ""


def test_a_5xx_after_a_cached_200_makes_the_visibility_unreadable() -> None:
    """R12 fails closed end to end: the cache never answers for a forge that errored."""
    from fr import gh
    from fr.gh import GhError
    from fr.triage.privacy import live_visibility

    answers: list[object] = [
        'HTTP/2.0 200 OK\nEtag: W/"v1"\n\n{"visibility": "private"}',
        GhError("HTTP 503", stdout="HTTP/2.0 503 x\n", returncode=1),
    ]

    def run(argv: list[str]) -> str:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    class Client:
        def repo_visibility(self, repo: str) -> str:
            return gh.repo_visibility(run, None, repo)

    assert live_visibility(Client(), "o/r") == "private"
    assert live_visibility(Client(), "o/r") is None


# ------------------------------------------- an unreadable member repo (gh#1144)


def test_a_member_repo_whose_visibility_cannot_be_read_is_unreadable_not_a_leak(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    """A public state repo, and a key's repo the forge does not answer for (a rate
    limit): nothing is known to leak, so the push refuses as retryable, naming the repo
    it could not read, never as the leak line (gh#1144)."""
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    del gh.visibility[SECRET]
    state = _state(tmp_path / "s", state_repo=REFS, with_facts=False)

    with pytest.raises(VisibilityUnreadable) as caught:
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)

    assert SECRET in str(caught.value) and REFS in str(caught.value)
    assert "which is not public" not in str(caught.value)


def test_a_definite_leak_outranks_an_unreadable_member_repo(gh: FakeGhClient) -> None:
    """One key's repo is known private, another's cannot be read: the leak is certain,
    so it is the leak refusal, which a looping driver does not retry (R10)."""
    from fr.triage.privacy import guard_write

    gh.visibility[REFS] = "public"
    scope = Scope.group([OPEN_REPO, SECRET, "example-org/flaky"])
    facts = _facts({OPEN_REPO: "public", SECRET: "private"})

    with pytest.raises(PrivacyError, match="secret#7") as caught:
        guard_write(
            ["secret#7", "flaky#2"], scope=scope, facts=facts, state_repo=REFS,
            client_for=lambda _r: gh,
        )  # fmt: skip

    assert not isinstance(caught.value, VisibilityUnreadable)


def test_guard_write_with_an_unreadable_member_repo_is_unreadable(gh: FakeGhClient) -> None:
    from fr.triage.privacy import guard_write

    gh.visibility[REFS] = "public"
    scope = Scope.group([OPEN_REPO, "example-org/flaky"])

    with pytest.raises(VisibilityUnreadable, match="example-org/flaky"):
        guard_write(
            ["flaky#2"], scope=scope, facts=_facts(), state_repo=REFS,
            client_for=lambda _r: gh,
        )  # fmt: skip


# ------------------------------------------------------------------ snapshots (R12)


def _snapshot(state: Path, **fields: Any) -> Path:
    """A `snapshots/<stamp>.json` holding only what the test names."""
    body = {"schema_version": 2, "batches": {}, "issues": {}, "prs": {}, "figures": {}}
    body.update(fields)
    path = state / "snapshots" / "20261101T100000000000Z.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _only_snapshot(tmp_path: Path, **fields: Any) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    _snapshot(state, **fields)
    return state


def test_state_keys_reads_the_snapshots_issue_and_pr_keys(tmp_path: Path) -> None:
    from fr.triage.privacy import state_keys

    state = _only_snapshot(
        tmp_path,
        issues={"secret#3": {"state": "open", "tier": None}},
        prs={f"{SECRET}#4": {"state": "OPEN", "draft": False, "checks": {}}},
    )

    assert state_keys(state) == ["example-org/secret#4", "secret#3"]


def test_a_snapshot_issue_key_of_a_private_repo_refuses_a_public_state_repo(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _only_snapshot(tmp_path, issues={"secret#3": {"state": "open", "tier": None}})

    with pytest.raises(PrivacyError, match="secret"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_a_snapshot_pr_key_of_a_private_repo_refuses_a_public_state_repo(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _only_snapshot(
        tmp_path, prs={f"{SECRET}#4": {"state": "OPEN", "draft": False, "checks": {}}}
    )

    with pytest.raises(PrivacyError, match="secret"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_a_snapshot_debt_repo_that_is_private_refuses_a_public_state_repo(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state, state_repos

    gh.visibility[REFS] = "public"
    state = _only_snapshot(tmp_path, debt={SECRET: {"open_rows": 2}})
    assert state_repos(state) == [SECRET]

    with pytest.raises(PrivacyError, match="secret"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_an_unparseable_snapshot_is_a_refusal_not_skipped(tmp_path: Path, gh: FakeGhClient) -> None:
    from fr.triage.privacy import guard_state, state_keys

    state = _only_snapshot(tmp_path)
    (state / "snapshots" / "20261102T100000000000Z.json").write_text("{not json", "utf-8")

    with pytest.raises(TriageError, match="snapshot"):
        state_keys(state)
    gh.visibility[REFS] = "public"
    with pytest.raises(TriageError, match="snapshot"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_a_debt_only_leak_is_worded_as_debt_not_as_an_issue(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _only_snapshot(tmp_path, debt={SECRET: {"open_rows": 2}})

    with pytest.raises(PrivacyError) as err:
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)
    assert f"debt figures of {SECRET}" in str(err.value)
    assert "is an issue of" not in str(err.value)


def test_a_snapshot_pr_key_of_a_repo_outside_the_scope_is_read_not_skipped(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    other = "example-org/elsewhere"
    gh.visibility[REFS] = "public"
    gh.visibility[other] = "private"
    state = _only_snapshot(
        tmp_path, prs={f"{other}#9": {"state": "OPEN", "draft": False, "checks": {}}}
    )

    with pytest.raises(PrivacyError, match="elsewhere"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_no_snapshots_directory_adds_no_key_and_no_repo(tmp_path: Path) -> None:
    from fr.triage.privacy import state_keys, state_repos

    state = tmp_path / "state"
    state.mkdir()

    assert state_keys(state) == [] and state_repos(state) == []


@pytest.mark.parametrize("extra", ["20261101T100000000000Z.json.bak", "old/a.json"])
def test_a_snapshots_entry_the_strict_reader_does_not_parse_refuses(
    tmp_path: Path, gh: FakeGhClient, extra: str
) -> None:
    """Lens finding S3: the state ref carries every file under `snapshots/`, so any entry the
    guard does not parse (a stray file, a nested directory) refuses instead of riding along."""
    from fr.triage.privacy import guard_state

    state = _only_snapshot(tmp_path)
    stray = state / "snapshots" / extra
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text(json.dumps({"issues": {"secret#3": {}}}), encoding="utf-8")
    gh.visibility[REFS] = "public"

    with pytest.raises(TriageError, match="snapshot"):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


# ------------------------------------------------------- snapshots pass through (T1)


def test_a_snapshot_naming_only_public_repos_passes_a_public_state_repo(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _only_snapshot(
        tmp_path,
        issues={"super-fr#1": {"state": "open", "tier": None}},
        prs={f"{OPEN_REPO}#4": {"state": "OPEN", "draft": False, "checks": {}}},
        debt={OPEN_REPO: {"open_rows": 2}},
    )
    scope = Scope(kind="repo", target=OPEN_REPO)

    guard_state(state, scope=scope, state_repo=REFS, client_for=lambda _r: gh)  # no raise


def test_a_private_state_repo_passes_a_snapshot_naming_private_repos(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    state = _only_snapshot(
        tmp_path,
        issues={"secret#3": {"state": "open", "tier": None}},
        prs={f"{SECRET}#4": {"state": "OPEN", "draft": False, "checks": {}}},
        debt={SECRET: {"open_rows": 2}},
    )
    assert gh.visibility[REFS] == "private"

    guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)  # no raise


# ------------------------------------------- carried files (cloud-triage R8, R9)

PUBLIC_ONLY = 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "super-fr#1": {tier: 1}\n'


def _clean_state(
    tmp_path: Path, facts: Facts | None = None, with_facts: bool = True, **files: str
) -> Path:
    """A state dir whose judgements name only the public repo, plus *files* (name -> text)."""
    state = tmp_path / "carried-state"
    state.mkdir()
    (state / "judgements.yaml").write_text(PUBLIC_ONLY, encoding="utf-8")
    if with_facts:
        (state / "facts.json").write_text(json.dumps((facts or _facts()).to_json()), "utf-8")
    for name, text in files.items():
        path = state / name.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return state


def _leaks(tmp_path: Path, text: str, look_for: list[str], vis: dict[str, str | None]) -> list:
    from fr.triage.privacy import carried_text_leaks

    (tmp_path / "f.txt").write_text(text, encoding="utf-8")
    return carried_text_leaks(["f.txt"], look_for, vis, root=tmp_path)


@pytest.mark.parametrize(
    "text",
    [
        "stopped on example-org/secret#4",
        "see https://github.com/example-org/secret.git",
        "please look at secret#12 now",
        "it is in example-org/secret.",
        "EXAMPLE-ORG/SECRET",
    ],
)
def test_carried_text_naming_a_private_repo_is_a_leak(tmp_path: Path, text: str) -> None:
    got = _leaks(tmp_path, text, [SECRET], {SECRET: "private"})
    assert got == [("f.txt", SECRET)]


@pytest.mark.parametrize(
    "text",
    ["example-org/secretive", "xexample-org/secret", "example-org/secret-two", "secret# none"],
)
def test_text_beside_a_private_repo_name_is_not_a_leak(tmp_path: Path, text: str) -> None:
    assert _leaks(tmp_path, text, [SECRET], {SECRET: "private"}) == []


def test_a_public_repo_sharing_the_name_keeps_its_issue_refs_out_of_the_private_pattern(
    tmp_path: Path,
) -> None:
    vis = {"acme/docs": "public", "bob/docs": "private"}
    assert _leaks(tmp_path, "docs#3", ["acme/docs", "bob/docs"], vis) == []
    assert _leaks(tmp_path, "see bob/docs", ["acme/docs", "bob/docs"], vis) == [
        ("f.txt", "bob/docs")
    ]


def test_an_unreadable_carried_file_raises_naming_it(tmp_path: Path) -> None:
    from fr.triage.privacy import carried_text_leaks

    with pytest.raises(PrivacyError, match="gone.txt"):
        carried_text_leaks(["gone.txt"], [SECRET], {SECRET: "private"}, root=tmp_path)


@pytest.mark.parametrize(
    "name", ["merge-stops.json", "requests.yaml", "history__x.md", "backlog__page.md"]
)
def test_guard_state_refuses_a_carried_file_naming_a_private_repo(
    tmp_path: Path, gh: FakeGhClient, name: str
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _clean_state(tmp_path, **{name: "blocked on example-org/secret#4"})

    with pytest.raises(PrivacyError) as caught:
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)
    message = str(caught.value)
    assert name.replace("__", "/") in message and SECRET in message
    assert "#4" not in message  # never the matched text


def test_guard_state_passes_a_clean_directory(tmp_path: Path, gh: FakeGhClient) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = _clean_state(tmp_path, **{"merge-stops.json": "super-fr#1 stopped"})
    guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_all_public_look_for_repos_read_no_carried_file(
    tmp_path: Path, gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage import privacy

    gh.visibility.update({REFS: "public", SECRET: "public"})
    facts = _facts({OPEN_REPO: "public", SECRET: "public"})
    state = _clean_state(tmp_path, facts, **{"merge-stops.json": "example-org/secret#4"})
    opened: list[object] = []
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: opened.append(self) or real(self))
    privacy.guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)
    assert [p for p in opened if p.name == "merge-stops.json"] == []


def test_a_private_state_repo_returns_before_any_scan(tmp_path: Path, gh: FakeGhClient) -> None:
    from fr.triage.privacy import guard_state

    state = _clean_state(tmp_path, **{"merge-stops.json": "example-org/secret#4"})
    guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_an_org_scope_with_no_facts_is_unreadable_naming_collect(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    state = tmp_path / "org-state"
    state.mkdir()
    with pytest.raises(VisibilityUnreadable, match="fr triage collect"):
        guard_state(
            state, scope=Scope("org", "example-org"), state_repo=REFS, client_for=lambda _r: gh
        )


def test_a_repo_whose_visibility_cannot_be_read_and_which_a_file_names_is_unreadable(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    from fr.triage.privacy import guard_state

    gh.visibility[REFS] = "public"
    del gh.visibility[SECRET]
    state = _clean_state(tmp_path, with_facts=False, **{"merge-stops.json": "example-org/secret#4"})
    with pytest.raises(VisibilityUnreadable):
        guard_state(state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh)


def test_an_export_scans_the_durable_set_only(tmp_path: Path, gh: FakeGhClient) -> None:
    from fr.triage.privacy import durable_files, guard_state

    gh.visibility[REFS] = "public"
    state = _clean_state(tmp_path, **{"merge-stops.json": "example-org/secret#4"})
    guard_state(
        state, scope=SCOPE, state_repo=REFS, client_for=lambda _r: gh, carried=durable_files(state)
    )
    (state / "history").mkdir()
    (state / "history" / "x.md").write_text("example-org/secret", encoding="utf-8")
    with pytest.raises(PrivacyError, match="history/x.md"):
        guard_state(
            state,
            scope=SCOPE,
            state_repo=REFS,
            client_for=lambda _r: gh,
            carried=durable_files(state),
        )


@pytest.mark.parametrize("entry", REF_FILES)
def test_every_carried_entry_is_scanned_on_push(
    tmp_path: Path, origin: Path, gh: FakeGhClient, entry: str
) -> None:
    """A private key planted in ANY `REF_FILES` entry (a file inside a directory entry)
    refuses the push, naming that file: a scan that walked fewer entries would pass."""
    state = _workspace(tmp_path, origin)
    state.mkdir(parents=True, exist_ok=True)
    (state / "judgements.yaml").write_text(PUBLIC_ONLY, encoding="utf-8")
    (state / "facts.json").write_text(json.dumps(_facts().to_json()), "utf-8")
    write_durable(state, ScopeDurable(state_repo=OPEN_REPO))
    name = entry.rstrip("/")
    # Entries whose reader checks shape before the guard runs get content it accepts.
    shaped = {
        "origins.yaml": (state / name, "schema: 2\n# see example-org/secret#4\n"),
        "snapshots": (
            state / name / "x.json",
            json.dumps(
                {"batches": {"b": "example-org/secret#4"}, "issues": {}, "prs": {}, "figures": {}}
            ),
        ),
    }
    if name in shaped:
        target, text = shaped[name]
    else:
        target = state / name / "deep" / "x.md" if entry.endswith("/") else state / name
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        text = before + "\n# see example-org/secret#4\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    with pytest.raises(PrivacyError, match=re.escape(target.relative_to(state).as_posix())):
        _push(state, origin, OPEN_REPO, gh)

    assert _ref(origin) == ""


def test_a_symlinked_entry_is_neither_carried_nor_scanned(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    """A symlink is never carried, so the file it points at is not scanned either."""
    state = _workspace(tmp_path, origin)
    state.mkdir(parents=True, exist_ok=True)
    (state / "judgements.yaml").write_text(PUBLIC_ONLY, encoding="utf-8")
    (state / "facts.json").write_text(json.dumps(_facts().to_json()), "utf-8")
    write_durable(state, ScopeDurable(state_repo=OPEN_REPO))
    outside = tmp_path / "elsewhere.json"
    outside.write_text("example-org/secret#4", encoding="utf-8")
    (state / "merge-stops.json").symlink_to(outside)

    assert "merge-stops.json" not in carried_files(state)
    _push(state, origin, OPEN_REPO, gh)
    assert _ref(origin) != ""


def test_a_push_naming_a_private_repo_in_a_carried_file_pushes_nothing(
    tmp_path: Path, origin: Path, gh: FakeGhClient
) -> None:
    state = _workspace(tmp_path, origin)
    state.mkdir(parents=True, exist_ok=True)
    (state / "judgements.yaml").write_text(PUBLIC_ONLY, encoding="utf-8")
    (state / "facts.json").write_text(json.dumps(_facts().to_json()), "utf-8")
    write_durable(state, ScopeDurable(state_repo=OPEN_REPO))
    (state / "merge-stops.json").write_text("example-org/secret#4", encoding="utf-8")

    with pytest.raises(PrivacyError, match="merge-stops.json"):
        _push(state, origin, OPEN_REPO, gh)

    assert _ref(origin) == ""
