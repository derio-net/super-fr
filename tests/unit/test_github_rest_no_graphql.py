"""With `forge.api: rest`, nothing reaches GraphQL (spec 2026-10-07-cloud-triage R1, R3;
Test Plan 2).

A fake `gh` on PATH refuses every GraphQL-backed command with the proxy's captured
403 and serves `gh api` REST GETs from the captured fixtures; every client factory
and the direct `fr.gh` helpers must get their answers through `gh api` alone, and
every forge command fr prints for an agent must be spelled as `gh api`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fr import gh as fr_gh
from fr import hostclient
from fr.gh import GhError
from fr.labels import LabelDef
from fr.real_ghrestclient import RealGhRestClient

from tests.unit.github_rest_support import FIXTURES, REPO

REFUSED = (
    "api graphql",
    "issue list --json",
    "issue view --json",
    "pr list --json",
    "pr view --json",
    "pr checks",
    "pr merge",
    "pr create",
    "pr close",
    "pr ready",
    "pr edit",
    "issue edit",
    "issue comment",
    "issue close",
    "label create",
    "repo view --json",
)

_FAKE_GH = """#!{python}
import json, os, sys
from pathlib import Path

fixtures = Path(os.environ["FAKE_GH_FIXTURES"])
log = Path(os.environ["FAKE_GH_LOG"])
argv = sys.argv[1:]
with log.open("a") as fh:
    fh.write(json.dumps(argv) + "\\n")
line = " ".join(argv)
if not argv or argv[0] != "api" or argv[1] == "graphql":
    sys.stderr.write((fixtures / "refused" / "pr-list.stderr").read_text())
    sys.exit(1)
rest = argv[1:]
method, header = "GET", None
while rest and rest[0] in ("-X", "-H"):
    if rest[0] == "-X":
        method = rest[1]
    else:
        header = rest[1]
    rest = rest[2:]
route, fields = rest[0], rest[1:]
if fields and method == "GET" and "--jq" not in fields:
    method = "POST"
if method != "GET":
    print("{{}}")
    sys.exit(0)
index = json.loads((fixtures / "index.json").read_text())
entry = index.get((header + " " if header else "") + route)
if entry is None:
    sys.stderr.write("fake gh: no fixture for " + route + "\\n")
    sys.exit(3)
body = (fixtures / entry["file"]).read_text()
if entry.get("error"):
    err = json.loads(body)
    sys.stdout.write(err["stdout"])
    sys.stderr.write(err["stderr"])
    sys.exit(err["exit"])
sys.stdout.write(body)
"""


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH.format(python=sys.executable))
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.touch()
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_FIXTURES", str(FIXTURES))
    monkeypatch.setenv("FAKE_GH_LOG", str(log))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_FORGE_API", "rest")
    monkeypatch.delenv("GH_HOST", raising=False)
    return log


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", f"https://github.com/{REPO}.git"],
        check=True,
    )
    return repo


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _assert_rest_only(log: Path) -> None:
    calls = _calls(log)
    assert calls, "no gh call reached the fake"
    for argv in calls:
        line = " ".join(argv)
        assert argv[0] == "api", argv
        assert not any(r in line for r in REFUSED), line


def test_every_client_factory_returns_the_rest_client(fake_gh: Path, checkout: Path) -> None:
    by_backend = hostclient.client_for_backend("github")
    by_url = hostclient.client_for_url(f"https://github.com/{REPO}/pull/1080")
    by_checkout = hostclient.client_for(checkout)
    for client in (by_backend, by_url, by_checkout):
        assert isinstance(client, RealGhRestClient)
    assert by_backend.viewer_login()
    assert by_url.pr_view(REPO, 1080)["head_ref"] == "feat/batch-secrets-injection"
    assert by_checkout.pr_body("1080", cwd=checkout).strip()
    _assert_rest_only(fake_gh)


def test_the_fr_gh_helpers_route_through_rest(
    fake_gh: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert fr_gh.view_pr_body("1080", cwd=checkout).strip()
    with monkeypatch.context() as m:
        # The captured open-issue pages are the two `per_page=2` ones.
        m.setattr(RealGhRestClient, "PER_PAGE", 2)
        assert fr_gh.list_issues(repo=REPO, state="open", limit=1)
    assert [p["number"] for p in fr_gh.list_prs(repo=REPO, state="open", limit=2)] == [1080, 1079]
    assert fr_gh.list_open_prs(repo=REPO, limit=1)[0]["number"] == 1080
    assert fr_gh.list_prs_by_head(repo=REPO, branch="docs/r8-light-path-benchmark")
    assert fr_gh.view_issue(REPO, 1074)["number"] == 1074
    assert fr_gh.is_issue_closed(repo=REPO, number=1074) is False
    labels = fr_gh.list_labels(repo=REPO)
    assert labels and set(labels[0]) == {"name", "color", "description"}
    fr_gh.close_issue(repo=REPO, number=7)
    fr_gh.edit_issue_labels(repo=REPO, issue_number=7, add_labels=["x"])
    _assert_rest_only(fake_gh)
    writes = [c for c in _calls(fake_gh) if "-X" in c or "-f" in c]
    assert ["api", "-X", "PATCH", f"repos/{REPO}/issues/7", "-f", "state=closed"] in writes


def test_list_repos_reaches_rest_and_raises_the_cloud_refusal(fake_gh: Path) -> None:
    # Captured: an org's repo list is refused from a cloud session. Raised, not [].
    with pytest.raises(GhError, match="403"):
        fr_gh.list_repos(owner="derio-net", limit=10)
    _assert_rest_only(fake_gh)


def test_graphql_is_the_default_without_the_setting(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FR_FORGE_API")
    with pytest.raises(GhError, match="403"):
        fr_gh.list_issues(repo=REPO, state="open", limit=1)
    assert _calls(fake_gh)[0][:2] == ["issue", "list"]


GITHUB_OPS = sorted(hostclient.FORGE_COMMANDS["github"])


def _rendered(checkout: Path) -> dict[str, str]:
    issue_ref = f"{REPO}#7"
    label = LabelDef(name="fr:awaiting live", color="ededed", description="it's owed")
    return {
        "create": hostclient.pr_command(checkout, "create", body="pr-body.md"),
        "edit": hostclient.pr_command(checkout, "edit", ref="feat/x", body="pr-body.md"),
        "edit-url": hostclient.pr_command(
            checkout, "edit", ref=f"https://github.com/{REPO}/pull/12", body="b.md"
        ),
        "ready": hostclient.pr_command(checkout, "ready", ref="12"),
        "fill": hostclient.pr_command(checkout, "fill"),
        "issue-close": hostclient.issue_command(
            checkout, "issue-close", ref=issue_ref, comment="done, it's live"
        ),
        "issue-label": hostclient.issue_command(
            checkout, "issue-label", ref=issue_ref, label="fr:awaiting live"
        ),
        "issue-unlabel": hostclient.issue_command(
            checkout, "issue-unlabel", ref=issue_ref, label="fr:awaiting live"
        ),
        "label-create": hostclient.label_command(checkout, label, repo=REPO),
    }


def test_every_github_op_has_a_rest_spelling() -> None:
    assert sorted(hostclient.FORGE_COMMANDS["github-rest"]) == GITHUB_OPS


def test_agent_commands_are_spelled_as_gh_api(fake_gh: Path, checkout: Path) -> None:
    rendered = _rendered(checkout)
    assert {k.split("-url")[0] for k in rendered} == set(GITHUB_OPS)
    for op, cmd in rendered.items():
        assert cmd.startswith("gh api "), (op, cmd)
        assert not any(f"gh {r}" in cmd for r in REFUSED), (op, cmd)
    assert f"repos/{REPO}/pulls/12" in rendered["edit-url"]
    assert "-F draft=true" in rendered["create"]
    assert f"repos/{REPO}/issues/7/labels" in rendered["issue-label"]
    assert "fr%3Aawaiting%20live" in rendered["issue-unlabel"]


def test_rendered_rest_commands_run_through_a_shell(fake_gh: Path, checkout: Path) -> None:
    """The spellings are real shell: run each against the fake and check that
    every `gh` it invoked was `gh api`, with the quoted values intact."""
    for op, cmd in _rendered(checkout).items():
        if op in {"create", "fill"}:
            continue  # they read the checkout's branch and last commit
        done = subprocess.run(["sh", "-c", cmd], cwd=checkout, capture_output=True, text=True)
        assert done.returncode == 0, (op, cmd, done.stderr)
    _assert_rest_only(fake_gh)
    calls = _calls(fake_gh)
    assert ["api", f"repos/{REPO}/issues/7/comments", "-f", "body=done, it's live"] in calls
    assert ["api", f"repos/{REPO}/issues/7/labels", "-f", "labels[]=fr:awaiting live"] in calls


def test_github_without_the_setting_keeps_the_gh_cli_spellings(
    checkout: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("FR_FORGE_API", raising=False)
    assert hostclient.pr_command(checkout, "ready", ref="12") == "gh pr ready 12"
