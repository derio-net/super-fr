"""The privacy guard (spec 2026-10-07-cloud-triage R8, §C, Test Plan 7).

A private repo's issue must never reach a public state repo: not into a batch, a wave or
a judgement write, and not through a push of the state ref or a state export. The forge
is `tests.unit.fakes.FakeGhClient` (visibility per repo; a repo it does not know cannot
be read), or the captured `GET repos/derio-net/super-fr` where the route itself is the
point. Remotes are bare repos under `tmp_path`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.real_ghrestclient import RealGhRestClient
from fr.triage.errors import TriageError
from fr.triage.model import Facts, Issue, Scope, load_judgements
from fr.triage.privacy import PrivacyError, leak_risk, refusal
from fr.triage.scope_config import ScopeDurable, write_durable
from fr.triage.state_ref import push_state, ref_name
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

    assert ["api", f"repos/{OPEN_REPO}"] in fake.calls
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
