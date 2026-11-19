"""The driver record, the failure ledger and `fr triage drive failures` (spec
2026-11-19-batch-train-truth R8-R10).

Both files live in the scope's state directory, are written atomically and are host-local:
neither rides on the state ref.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fr.triage import driver_record, state_ref
from fr.triage.driver_record import (
    FAILURES_FILE,
    RECORD_FILE,
    load_ledger,
    load_record,
    record_failure,
    record_pass,
    record_refusal,
    stopped,
)

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


# --------------------------------------------------------------------- the ledger (R9)


def test_record_failure_starts_a_cause(tmp_path: Path) -> None:
    record_failure(tmp_path, "transient", "push-refused", "the remote refused", NOW, "8.3.0")
    data = yaml.safe_load((tmp_path / FAILURES_FILE).read_text())
    assert data == {
        "schema": 1,
        "causes": {
            "push-refused": {
                "kind": "transient",
                "count": 1,
                "first": "2026-11-19T12:00:00Z",
                "last": "2026-11-19T12:00:00Z",
                "message": "the remote refused",
                "fr_version": "8.3.0",
                "exception": None,
                "issue": None,
                "filed_count": 0,
            }
        },
    }


def test_record_failure_increments_and_keeps_the_first_time(tmp_path: Path) -> None:
    record_failure(tmp_path, "transient", "git:fetch", "one", NOW, "8.3.0")
    record_failure(tmp_path, "transient", "git:fetch", "two", LATER, "8.4.0", exception="GitError")
    entry = load_ledger(tmp_path).causes["git:fetch"]
    assert (entry.count, entry.first, entry.last) == (2, NOW, LATER)
    assert (entry.message, entry.fr_version, entry.exception) == ("two", "8.4.0", "GitError")


def test_record_failure_keeps_other_causes_and_the_filed_issue(tmp_path: Path) -> None:
    record_failure(tmp_path, "refusal", "lease-held", "held", NOW, "8.3.0")
    ledger = load_ledger(tmp_path)
    ledger.causes["lease-held"].issue = "derio-net/super-fr#9"
    driver_record.save_ledger(tmp_path, ledger)
    record_failure(tmp_path, "transient", "push-refused", "refused", NOW, "8.3.0")
    record_failure(tmp_path, "refusal", "lease-held", "held", LATER, "8.3.0")
    out = load_ledger(tmp_path)
    assert set(out.causes) == {"lease-held", "push-refused"}
    assert out.causes["lease-held"].issue == "derio-net/super-fr#9"
    assert out.causes["lease-held"].count == 2


def test_an_absent_ledger_is_empty(tmp_path: Path) -> None:
    assert load_ledger(tmp_path).causes == {}


# ----------------------------------------------------------------- the record (R8)


def test_record_refusal_writes_the_last_refusal(tmp_path: Path) -> None:
    record_refusal(tmp_path, "lease-held", "held by y", "wait for it", NOW, "8.3.0")
    record = load_record(tmp_path)
    assert record is not None and record.last_refusal is not None
    assert record.last_refusal.cause == "lease-held"
    assert record.last_refusal.message == "held by y"
    assert record.last_refusal.resume == "wait for it"
    assert record.last_refusal.at == NOW
    assert record.last_refusal.fr_version == "8.3.0"
    assert record.pid > 0


def test_neither_file_rides_on_the_state_ref() -> None:
    assert RECORD_FILE not in state_ref.REF_FILES
    assert FAILURES_FILE not in state_ref.REF_FILES
    assert RECORD_FILE in (state_ref.__doc__ or "")
    assert FAILURES_FILE in (state_ref.__doc__ or "")


def test_writes_are_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[Path] = []
    real = driver_record.write_text_atomic

    def spy(path: Path, text: str) -> None:
        written.append(path)
        real(path, text)

    monkeypatch.setattr(driver_record, "write_text_atomic", spy)
    record_failure(tmp_path, "transient", "x", "m", NOW, "8.3.0")
    record_refusal(tmp_path, "x", "m", "r", NOW, "8.3.0")
    assert written == [tmp_path / FAILURES_FILE, tmp_path / RECORD_FILE]


# ------------------------------------------------------- the stopped driver (R8)


def test_a_refusal_newer_than_the_last_pass_is_a_stopped_driver(tmp_path: Path) -> None:
    record_refusal(tmp_path, "lease-held", "held", "wait", LATER, "8.3.0")
    assert stopped(load_record(tmp_path), NOW) is not None
    assert stopped(load_record(tmp_path), None) is not None


def test_a_pass_after_the_refusal_clears_the_stop(tmp_path: Path) -> None:
    record_refusal(tmp_path, "lease-held", "held", "wait", NOW, "8.3.0")
    assert stopped(load_record(tmp_path), LATER) is None
    record_pass(tmp_path, LATER)
    assert stopped(load_record(tmp_path), None) is None
    assert stopped(None, None) is None


def test_needs_you_lists_a_stopped_driver_with_its_reason_and_resume(tmp_path: Path) -> None:
    from fr.triage.views import NEED_LABELS, needs_you

    from tests.unit.test_triage_batch_drive_cmd import World

    facts = World().facts()
    from fr.triage.model import Judgements

    record_refusal(tmp_path, "lease-held", "held by y", "wait for y", LATER, "8.3.0")
    rows = needs_you(facts, Judgements(), driver=load_record(tmp_path), last_pass=NOW)
    (need,) = [n for n in rows if n.kind == "driver-stopped"]
    assert "held by y" in need.text
    assert "wait for y" in need.text
    assert "fr triage drive failures --file --yes" in need.text
    assert "driver-stopped" in NEED_LABELS
    assert not [
        n
        for n in needs_you(facts, Judgements(), driver=load_record(tmp_path), last_pass=LATER)
        if n.kind == "driver-stopped"
    ]


# ------------------------------------------- `fr triage drive failures` (R10)


class FakeIssues:
    """The forge calls filing makes, recorded; issues numbered from 10."""

    def __init__(self, settings: str | None = None) -> None:
        self.settings = settings
        self.issues: dict[int, dict[str, object]] = {}
        self.comments: list[tuple[int, str]] = []
        self.labels_ensured: list[str] = []
        self.created: list[dict[str, object]] = []

    def read_file(self, repo: str, path: str) -> str:
        if self.settings is None:
            raise RuntimeError("HTTP 404: Not Found")
        return self.settings

    def list_open_issues_with_body(
        self, repo: str, *, search: tuple[str, ...], limit: int
    ) -> list[dict[str, object]]:
        return [
            {"number": n, "body": i["body"], "title": i["title"], "labels": []}
            for n, i in self.issues.items()
            if i["state"] == "OPEN" and any(s in str(i["body"]) for s in search)
        ]

    def view_issue(self, repo: str, number: int) -> dict[str, object]:
        return {"state": self.issues[number]["state"]}

    def ensure_labels(self, repo: str, labels: list[object]) -> None:
        self.labels_ensured += [getattr(x, "name", str(x)) for x in labels]

    def create_issue(self, repo: str, *, title: str, body: str, labels: frozenset[str]) -> str:
        number = 10 + len(self.issues)
        issue = {"repo": repo, "title": title, "body": body, "labels": labels, "state": "OPEN"}
        self.issues[number] = issue
        self.created.append(issue)
        return f"https://github.com/{repo}/issues/{number}"

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        self.comments.append((number, body))


REPO = "derio-net/super-fr"


def _failures(
    state: Path,
    client: FakeIssues,
    monkeypatch: pytest.MonkeyPatch,
    *args: str,
    org: bool = False,
) -> tuple[int, str, list[str]]:
    from fr.cli import app
    from fr.commands import triage_drive_cmd
    from typer.testing import CliRunner

    targets: list[str] = []

    def make(repo: str, host: str = "github.com") -> FakeIssues:
        targets.append(repo)
        return client

    monkeypatch.setattr(triage_drive_cmd, "make_failures_client", make)
    scope = ["--org", "derio-net"] if org else ["--repo", REPO]
    result = CliRunner().invoke(
        app, ["triage", "drive", "failures", *args, *scope, "--dir", str(state)]
    )
    return result.exit_code, result.output, targets


def _ledger(state: Path) -> None:
    record_failure(state, "transient", "push-refused", "secret-host refused", NOW, "8.3.0",
                   exception="StateRefPushRefused")  # fmt: skip
    for _ in range(3):
        record_failure(state, "refusal", "lease-held", "held by secret-host", LATER, "8.3.0",
                       exception="LeaseHeld")  # fmt: skip


@pytest.fixture
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.mark.usefixtures("_home")
def test_failures_lists_the_most_frequent_cause_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    code, out, targets = _failures(tmp_path, FakeIssues(), monkeypatch)
    assert code == 0, out
    assert out.index("lease-held") < out.index("push-refused")
    assert targets == []  # listing reads no forge


@pytest.mark.usefixtures("_home")
def test_failures_file_files_one_issue_per_cause_without_the_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues()
    code, out, targets = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert targets == [REPO]
    assert len(client.created) == 2
    assert client.labels_ensured == ["fr:driver-failure"]
    for issue in client.created:
        assert issue["labels"] == frozenset({"fr:driver-failure"})
        assert "secret-host" not in str(issue["body"]) + str(issue["title"])
    lease = next(i for i in client.created if "lease-held" in str(i["body"]))
    body = str(lease["body"])
    assert "<!-- fr-driver-failure:lease-held -->" in body
    for part in ("refusal", "count: 3", "2026-11-19", "8.3.0", "LeaseHeld"):
        assert part in body
    ledger = load_ledger(tmp_path)
    assert {c.issue for c in ledger.causes.values()} == {f"{REPO}#10", f"{REPO}#11"}
    assert all(c.filed_count == c.count for c in ledger.causes.values())


@pytest.mark.usefixtures("_home")
def test_failures_file_comments_a_grown_count_on_the_open_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues()
    _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert client.comments == [] and len(client.created) == 2, "nothing new: nothing written"
    record_failure(tmp_path, "refusal", "lease-held", "held again", LATER, "8.3.0")
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert len(client.created) == 2
    ((number, text),) = client.comments
    lease = load_ledger(tmp_path).causes["lease-held"]
    assert f"{REPO}#{number}" == lease.issue
    assert "now 4" in text and "held again" not in text
    assert lease.filed_count == 4


@pytest.mark.usefixtures("_home")
def test_failures_file_refiles_a_cause_that_recurred_after_its_issue_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues()
    _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    closed = load_ledger(tmp_path).causes["lease-held"].issue
    assert closed is not None
    client.issues[int(closed.split("#")[1])]["state"] = "CLOSED"
    record_failure(tmp_path, "refusal", "lease-held", "held", LATER, "8.3.0")
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert len(client.created) == 3
    assert closed in str(client.created[-1]["body"])
    assert load_ledger(tmp_path).causes["lease-held"].issue == f"{REPO}#12"


@pytest.mark.usefixtures("_home")
def test_failures_file_adopts_an_open_issue_another_host_filed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_failure(tmp_path, "refusal", "lease-held", "held", NOW, "8.3.0")
    client = FakeIssues()
    client.issues[7] = {"body": "<!-- fr-driver-failure:lease-held -->\n", "title": "t",
                        "state": "OPEN", "labels": frozenset()}  # fmt: skip
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert client.created == []
    assert load_ledger(tmp_path).causes["lease-held"].issue == f"{REPO}#7"


@pytest.mark.usefixtures("_home")
def test_failures_file_targets_the_state_repo_when_the_scope_has_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    (tmp_path / "scope-durable.yaml").write_text("state_repo: derio-net/triage-state\n")
    client = FakeIssues()
    code, out, targets = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert targets == ["derio-net/triage-state"]
    assert {i["repo"] for i in client.created} == {"derio-net/triage-state"}


@pytest.mark.usefixtures("_home")
def test_failures_file_refuses_an_org_scope_with_no_state_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues()
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes", org=True)
    assert code == 2, out
    assert "no state repo" in out
    assert client.created == []


@pytest.mark.usefixtures("_home")
def test_failures_file_files_nothing_under_forge_issues_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues(settings="forge:\n  issues: off\n")
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert "forge.issues: off" in out
    assert client.created == [] and client.comments == []


@pytest.mark.usefixtures("_home")
def test_failures_file_files_nothing_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_drive_cmd
    from fr.settings.model import Forge
    from fr.settings.remote import RepoPolicy

    _ledger(tmp_path)
    client = FakeIssues()
    monkeypatch.setattr(
        triage_drive_cmd, "failure_policy", lambda c, r, k: RepoPolicy(Forge(), tracking_none=True)
    )
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file", "--yes")
    assert code == 0, out
    assert "tracking" in out
    assert client.created == []


@pytest.mark.usefixtures("_home")
def test_failures_file_without_yes_prints_the_plan_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger(tmp_path)
    client = FakeIssues()
    before = (tmp_path / FAILURES_FILE).read_bytes()
    code, out, _ = _failures(tmp_path, client, monkeypatch, "--file")
    assert code == 0, out
    assert "would file" in out and "nothing written" in out
    assert client.created == [] and client.labels_ensured == []
    assert (tmp_path / FAILURES_FILE).read_bytes() == before
