"""`fr.config.protection` (spec 2026-11-19-event-driven-a-la-carte R7, §C): does the forge
enforce a pull-request rule on the configuration branch?

The forge replies are captured (`tests/fixtures/github_rest/rules/`, see its README); the
clients around them are the real `RealGhRestClient` and `RealGhClient` over a fake `gh`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr.config import protection
from fr.config.protection import Enforced, NotEnforced, ProtectionError, ProtectionReadError
from fr.config.space import ConfigSpace
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient

RULES = Path(__file__).resolve().parents[1] / "fixtures" / "github_rest" / "rules"
REPO = "example-org/example-repo"
APPROVED = "pull-request-approved-dismiss-stale.json"
"""The captured approved reply with `dismiss_stale_reviews_on_push` flipped to true (README)."""


def _reply(name: str) -> str:
    return (RULES / name).read_text().strip()


def _error(name: str) -> _gh.GhError:
    err = json.loads((RULES / name).read_text())
    return _gh.GhError(
        err["stderr"].strip(), stderr=err["stderr"], returncode=err["exit"], stdout=err["stdout"]
    )


class _Gh:
    """A `gh` that answers `rules/branches/<b>` with *reply* (text, or an error to raise)."""

    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[str] = []

    def __call__(self, argv: list[str]) -> str:
        assert argv[0] == "api"
        self.calls.append(argv[-1])
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _rest(reply: str | Exception) -> tuple[RealGhRestClient, _Gh]:
    fake = _Gh(reply)
    return RealGhRestClient(run=fake), fake


# --- the answer ---------------------------------------------------------------------


def test_a_pull_request_rule_with_force_push_and_deletion_blocked_is_enforced() -> None:
    client, fake = _rest(_reply(APPROVED))
    assert protection.branch_protection(client, REPO, "fr-config") == Enforced(REPO, "fr-config")
    assert fake.calls == [f"repos/{REPO}/rules/branches/fr-config"]


def test_a_pull_request_rule_needing_no_approval_is_not_enforced() -> None:
    """Review p3-r3: a pull-request rule with `required_approving_review_count: 0` lets the
    author merge their own unreviewed change, so it proves no review."""
    client, _ = _rest(_reply("pull-request.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "requires no approving review" in answer.reason


def test_an_approval_a_later_push_keeps_is_not_enforced() -> None:
    """Lens review l-security-r1: with neither `dismiss_stale_reviews_on_push` nor
    `require_last_push_approval`, an author can get a harmless change approved, push the real
    one and merge it unreviewed. The captured reply has both false."""
    client, _ = _rest(_reply("pull-request-approved.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert answer.reason == protection.STALE_APPROVAL


def test_requiring_the_last_push_to_be_approved_is_enforced() -> None:
    rules = json.loads(_reply("pull-request-approved.json"))
    for r in rules:
        if r["type"] == "pull_request":
            r["parameters"]["require_last_push_approval"] = True
    client, _ = _rest(json.dumps(rules))
    assert isinstance(protection.branch_protection(client, REPO, "fr-config"), Enforced)


@pytest.mark.parametrize("value", [None, "true", 1])
def test_an_unreadable_stale_review_setting_is_not_enforced(value: object) -> None:
    rules = json.loads(_reply(APPROVED))
    for r in rules:
        if r["type"] == "pull_request":
            if value is None:
                del r["parameters"]["dismiss_stale_reviews_on_push"]
            else:
                r["parameters"]["dismiss_stale_reviews_on_push"] = value
    client, _ = _rest(json.dumps(rules))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert answer.reason == protection.STALE_APPROVAL


def test_the_fix_names_the_stale_approval_setting() -> None:
    text = protection.fix_text("fr-config")
    assert "dismiss stale" in text and "most recent push" in text


@pytest.mark.parametrize("count", [None, "1", True, -1])
def test_an_unreadable_approval_count_is_not_enforced(count: object) -> None:
    rules = json.loads(_reply(APPROVED))
    for r in rules:
        if r["type"] == "pull_request":
            if count is None:
                del r["parameters"]["required_approving_review_count"]
            else:
                r["parameters"]["required_approving_review_count"] = count
    client, _ = _rest(json.dumps(rules))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "requires no approving review" in answer.reason


def test_one_approving_pull_request_rule_among_several_is_enforced() -> None:
    """Every rule GitHub returns applies, so the strictest pull-request rule decides."""
    rules = json.loads(_reply(APPROVED))
    loose = next(r for r in json.loads(_reply("pull-request.json")) if r["type"] == "pull_request")
    client, _ = _rest(json.dumps([loose, *rules]))
    assert isinstance(protection.branch_protection(client, REPO, "fr-config"), Enforced)


def test_every_refusal_says_fr_cannot_see_bypass_actors() -> None:
    text = protection.fix_text("fr-config")
    assert "at least one approving review" in text
    assert "bypass" in text and "cannot see" in text


def test_the_branch_is_quoted_in_the_route() -> None:
    client, fake = _rest(_reply(APPROVED))
    protection.branch_protection(client, REPO, "main-config/x")
    assert fake.calls == [f"repos/{REPO}/rules/branches/main-config%2Fx"]


def test_rules_without_a_pull_request_rule_are_not_enforced() -> None:
    client, _ = _rest(_reply("no-pull-request.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "no rule requires a pull request" in answer.reason


def test_a_branch_with_no_rules_is_not_enforced() -> None:
    client, _ = _rest(_reply("empty.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert answer.reason == (
        "no ruleset on this branch (classic branch protection is not read; protect it with a "
        "ruleset)"
    )


@pytest.mark.parametrize(
    ("drop", "said"),
    [("non_fast_forward", "force-pushes"), ("deletion", "deletion")],
)
def test_a_pull_request_rule_alone_is_not_enforced(drop: str, said: str) -> None:
    """Protected means the branch takes changes only by pull request: a force-push or a
    deletion would replace or remove what was reviewed."""
    rules = [r for r in json.loads(_reply(APPROVED)) if r["type"] != drop]
    client, _ = _rest(json.dumps(rules))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert said in answer.reason


def test_the_free_plan_403_is_not_enforced_and_says_why() -> None:
    client, _ = _rest(_error("free-plan.error.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "free plan" in answer.reason and "403" in answer.reason


def test_a_404_is_not_enforced() -> None:
    client, _ = _rest(_error("not-found.error.json"))
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "404" in answer.reason


@pytest.mark.parametrize("body", ['{"message": "odd"}', "not json at all", "[1, 2]"])
def test_an_unparseable_reply_is_not_enforced(body: str) -> None:
    client, _ = _rest(body)
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "not a list of rules" in answer.reason


def test_a_client_without_the_rules_read_is_not_enforced() -> None:
    answer = protection.branch_protection(object(), REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert "cannot read branch rules" in answer.reason


@pytest.mark.parametrize("backend", ["gitlab", "gitea"])
def test_gitlab_and_gitea_clients_are_not_enforced(backend: str) -> None:
    from fr.real_glabclient import RealGlabClient
    from fr.real_teaclient import RealTeaClient

    client = RealGlabClient() if backend == "gitlab" else RealTeaClient()
    answer = protection.branch_protection(client, REPO, "fr-config")
    assert isinstance(answer, NotEnforced)
    assert backend in answer.reason and "cannot read branch rules" in answer.reason


@pytest.mark.parametrize(
    "exc",
    [
        _gh.GhError("gh: Server Error (HTTP 502)", stderr="gh: Server Error (HTTP 502)\n"),
        _gh.GhError("gh: Bad credentials (HTTP 401)", stderr="gh: Bad credentials (HTTP 401)\n"),
        _gh.GhError(
            "gh: Resource not accessible by integration (HTTP 403)",
            stderr="gh: Resource not accessible by integration (HTTP 403)\n",
        ),
        _gh.GhError("error connecting to api.github.com", stderr="error connecting\n"),
    ],
)
def test_a_failed_read_is_neither_answer(exc: Exception) -> None:
    """A failed read is NOT "unprotected": it refuses, naming the error."""
    client, _ = _rest(exc)
    with pytest.raises(ProtectionReadError, match=str(exc).split(" (")[0][:20]):
        protection.branch_protection(client, REPO, "fr-config")


def test_a_failed_read_through_triage_forge_errors_is_still_a_failed_read() -> None:
    """collect's `ClientForge` wraps every adapter error as a `ForgeError`; the free-plan 403
    is still recognised through it, and a 5xx is still a failed read."""
    from fr.triage.collect import ClientForge

    free, _ = _rest(_error("free-plan.error.json"))
    assert isinstance(
        protection.branch_protection(ClientForge(free), REPO, "fr-config"), NotEnforced
    )
    protection.forget()
    broken, _ = _rest(_gh.GhError("gh: boom (HTTP 500)", stderr="gh: boom (HTTP 500)\n"))
    with pytest.raises(ProtectionReadError, match="HTTP 500"):
        protection.branch_protection(ClientForge(broken), REPO, "fr-config")


def test_the_graphql_client_reads_the_same_route() -> None:
    fake = _Gh(_reply(APPROVED))

    class _Rest(RealGhRestClient):
        def __init__(self, host: str | None = None, run: Any = None) -> None:
            super().__init__(host=host, run=fake)

    import fr.real_ghrestclient as rest_mod

    original = rest_mod.RealGhRestClient
    rest_mod.RealGhRestClient = _Rest  # type: ignore[misc]
    try:
        answer = protection.branch_protection(RealGhClient(), REPO, "fr-config")
    finally:
        rest_mod.RealGhRestClient = original  # type: ignore[misc]
    assert answer == Enforced(REPO, "fr-config")


def test_the_answer_is_cached_for_the_command_and_a_failure_is_not() -> None:
    client, fake = _rest(_reply(APPROVED))
    protection.branch_protection(client, REPO, "fr-config")
    protection.branch_protection(client, REPO, "fr-config")
    assert len(fake.calls) == 1
    protection.forget()
    protection.branch_protection(client, REPO, "fr-config")
    assert len(fake.calls) == 2

    failing, ffake = _rest(_gh.GhError("gh: boom (HTTP 500)", stderr="x"))
    for _ in range(2):
        with pytest.raises(ProtectionReadError):
            protection.branch_protection(failing, "o/other", "fr-config")
    assert len(ffake.calls) == 2


def test_two_forges_with_the_same_slug_get_their_own_answers() -> None:
    """Security review: a GitHub Enterprise host's answer never stands for github.com's,
    nor a GitHub client's for a GitLab one's."""
    from fr.real_glabclient import RealGlabClient

    class _Hosted:
        def __init__(self, host: str | None, gh: _Gh) -> None:
            self._host, self.gh = host, gh

        def branch_rules(self, repo: str, branch: str) -> Any:
            return json.loads(self.gh(["api", f"repos/{repo}/rules/branches/{branch}"]))

    enforced = _Gh(_reply(APPROVED))
    bare = _Gh(_reply("empty.json"))
    ghe = _Hosted("ghe.example.com", enforced)
    dotcom = _Hosted(None, bare)
    assert protection.branch_protection(ghe, REPO, "fr-config") == Enforced(REPO, "fr-config")
    assert isinstance(protection.branch_protection(dotcom, REPO, "fr-config"), NotEnforced)
    assert isinstance(
        protection.branch_protection(RealGlabClient(), REPO, "fr-config"), NotEnforced
    )
    assert protection.branch_protection(ghe, REPO, "fr-config") == Enforced(REPO, "fr-config")
    assert len(enforced.calls) == 1 and len(bare.calls) == 1


def test_the_cache_lives_in_memory_only() -> None:
    """Never on disk: the module holds no path."""
    source = Path(protection.__file__).read_text()
    assert "Path(" not in source and "open(" not in source


# --- the guard ----------------------------------------------------------------------


def _space(placement: str, tmp_path: Path, tracking: str | None = None) -> ConfigSpace:
    ref = None if placement == "repo" else "origin/fr-config"
    return ConfigSpace(placement, tmp_path / ".fr", tmp_path, tmp_path, ref, tracking=tracking)


def test_under_repo_the_guard_asks_nothing(tmp_path: Path) -> None:
    class _Boom:
        def branch_rules(self, repo: str, branch: str) -> Any:
            raise AssertionError("repo placement never reads protection")

    protection.require_protected(_space("repo", tmp_path), _Boom(), "run post_merge")


def test_the_quiet_target_is_fr_config_on_the_products_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protection, "_origin_slug", lambda root: REPO)
    assert protection.config_target(_space("quiet", tmp_path)) == (REPO, "fr-config")


def test_the_stealth_target_is_branch_config_on_the_tracking_repo(tmp_path: Path) -> None:
    space = _space("stealth", tmp_path, tracking="git@github.com:example-org/track.git@main")
    assert protection.config_target(space) == ("example-org/track", "main-config")


def test_a_local_tracking_repo_is_not_enforced(tmp_path: Path) -> None:
    space = _space("stealth", tmp_path, tracking="/srv/track.git@main")
    with pytest.raises(ProtectionError, match="local path"):
        protection.require_protected(space, None, "run the candidate install")


def test_a_quiet_origin_that_is_no_forge_is_not_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protection, "_origin_slug", lambda root: None)
    with pytest.raises(ProtectionError, match="not a forge repository"):
        protection.require_protected(_space("quiet", tmp_path), None, "run post_merge")


def test_not_enforced_refuses_naming_the_reason_and_the_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protection, "_origin_slug", lambda root: REPO)
    client, _ = _rest(_error("free-plan.error.json"))
    with pytest.raises(ProtectionError) as caught:
        protection.require_protected(_space("quiet", tmp_path), client, "run post_merge")
    text = str(caught.value)
    assert "run post_merge" in text and "fr-config" in text and REPO in text
    assert "free plan" in text
    assert "protect fr-config with a ruleset requiring pull requests" in text
    assert "GitHub needs a public repo or a paid plan for a private one" in text
    assert not isinstance(caught.value, ProtectionReadError)


def test_a_failed_read_refuses_naming_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protection, "_origin_slug", lambda root: REPO)
    client, _ = _rest(_gh.GhError("gh: Server Error (HTTP 502)", stderr="x"))
    with pytest.raises(ProtectionReadError, match="HTTP 502"):
        protection.require_protected(_space("quiet", tmp_path), client, "run post_merge")


def test_enforced_lets_the_action_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protection, "_origin_slug", lambda root: REPO)
    client, _ = _rest(_reply(APPROVED))
    protection.require_protected(_space("quiet", tmp_path), client, "run post_merge")


def test_the_guard_is_a_settings_error() -> None:
    """Readers that already turn an unreadable configuration space into their own error
    (`SettingsError`) carry a protection refusal the same way."""
    from fr.settings import SettingsError

    assert issubclass(ProtectionError, SettingsError)


def test_the_guarded_triage_keys_cover_commands_and_trust() -> None:
    assert {"post_merge", "version", "mirrors", "pr_authors", "queue", "exit", "export"} <= set(
        protection.GUARDED_TRIAGE_KEYS
    )


def test_under_stealth_the_tracking_repos_forge_answers_never_the_given_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security review: under stealth the configuration branch lives in the tracking repo
    (maybe on another host); a product-repo client saying "protected" never answers for it."""
    product_client, product_calls = _rest(_reply(APPROVED))
    tracking_client, tracking_calls = _rest(_reply("empty.json"))
    monkeypatch.setattr(protection, "_default_client", lambda space: tracking_client)
    space = _space("stealth", tmp_path, tracking="git@github.com:example-org/track.git@main")
    with pytest.raises(ProtectionError, match="no ruleset on this branch"):
        protection.require_protected(space, product_client, "run post_merge")
    assert product_calls.calls == []
    assert tracking_calls.calls == ["repos/example-org/track/rules/branches/main-config"]
