"""Integration tests for the cncd adapter against a local stub HTTP
server (cnc-fr spec 2026-07-02, §3.5).

The stub is a real `http.server` on a loopback port — no cncd binary,
no mocking of urllib internals. It records every request (method, path,
headers, JSON body) and answers with a configurable status, which is
enough to pin the thin-client wire contract:

  - `dispatch()` POSTs the plan folder verbatim to `POST /v1/ingest`,
  - non-2xx responses and unreachable servers raise `CncdError`,
  - `fr_dispatch.tick` drives the runner end-to-end (FakeGhClient) and
    stamps `fr:synced` after a successful ingest.

The real cncd round-trip test (acceptance §4.6) lives in the umbrella
repo, against the actual Go server.
"""

from __future__ import annotations

import json
import textwrap
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from tests.unit.fakes import FakeGhClient

MINIMAL = Path(__file__).resolve().parents[1] / "unit" / "fixtures" / "v2_plan_minimal"


@dataclass
class StubCncd:
    """Handle the tests use: recorded requests + knobs."""

    base_url: str
    requests: list[dict[str, Any]] = field(default_factory=list)
    respond_status: int = 200


@pytest.fixture
def stub_cncd() -> Iterator[StubCncd]:
    stub: StubCncd | None = None

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 — http.server API
            assert stub is not None
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            stub.requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "content_type": self.headers.get("Content-Type"),
                    "auth_user": self.headers.get("X-Forwarded-User"),
                    "body": json.loads(raw) if raw else None,
                }
            )
            body = b'{"ok": true}' if stub.respond_status < 400 else b'{"error": "boom"}'
            self.send_response(stub.respond_status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:  # silence test output
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    stub = StubCncd(base_url=f"http://127.0.0.1:{server.server_port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield stub
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ── dispatch wire contract ──────────────────────────────────────────


def test_dispatch_posts_plan_folder_to_v1_ingest(stub_cncd: StubCncd) -> None:
    from fr.parser import parse
    from fr_cncd import CncdRunner

    plan = parse(MINIMAL)
    runner = CncdRunner(base_url=stub_cncd.base_url)
    runner.dispatch(plan, plan.phases[0], "agentic-stoa/cnc-demo", 42)

    assert len(stub_cncd.requests) == 1
    req = stub_cncd.requests[0]
    assert req["path"] == "/v1/ingest"
    assert req["content_type"] == "application/json"
    # The forward-auth identity must reach cncd (default CNCD_AUTH_USER).
    assert req["auth_user"] == "fr-cncd"
    body = req["body"]
    assert body["kind"] == "plan_folder"
    assert body["schema_version"] == 2
    assert body["plan"] == plan.meta.plan
    assert body["target_repo"] == plan.meta.target_repo
    assert body["repo"] == "agentic-stoa/cnc-demo"
    assert body["issue_number"] == 42
    assert body["phase"] == 1
    assert body["source_path"] == "tests/unit/fixtures/v2_plan_minimal"
    # the folder travels verbatim — files-win ingestion hashes content
    assert body["files"]["_meta.yaml"] == (MINIMAL / "_meta.yaml").read_text()
    assert body["files"]["_prose.md"] == (MINIMAL / "_prose.md").read_text()
    assert body["files"]["01.yaml"] == (MINIMAL / "01.yaml").read_text()
    assert set(body["files"]) == {"_meta.yaml", "_prose.md", "01.yaml"}


def test_dispatch_raises_cncd_error_on_non_2xx(stub_cncd: StubCncd) -> None:
    from fr.parser import parse
    from fr_cncd import CncdError, CncdRunner

    stub_cncd.respond_status = 500
    plan = parse(MINIMAL)
    runner = CncdRunner(base_url=stub_cncd.base_url)
    with pytest.raises(CncdError, match="500"):
        runner.dispatch(plan, plan.phases[0], "agentic-stoa/cnc-demo", 42)


def test_dispatch_raises_cncd_error_when_unreachable() -> None:
    from fr.parser import parse
    from fr_cncd import CncdError, CncdRunner

    plan = parse(MINIMAL)
    # RFC 5737 TEST-NET address with a tiny timeout — nothing listens there.
    runner = CncdRunner(base_url="http://127.0.0.1:1", timeout=2.0)
    with pytest.raises(CncdError, match="unreachable"):
        runner.dispatch(plan, plan.phases[0], "agentic-stoa/cnc-demo", 42)


# ── registry: `fr apply --to cncd` resolves the runner ──────────────


def test_cncd_registered_under_fr_runners_entry_point_group() -> None:
    from fr_dispatch.registry import available_runners, runner_names

    names = runner_names()
    assert "cncd" in names
    assert "vk" in names  # the split's first adapter is untouched
    ep = available_runners()["cncd"]
    loaded = ep.load()  # type: ignore[attr-defined]
    from fr_cncd import CncdRunner

    assert loaded is CncdRunner


# ── tick end-to-end: eligible phase → ingest POST + synced stamp ────


def _write_plan_with_prose(plan_dir: Path, *, repo: str, issue: int) -> None:
    plan_dir.mkdir(parents=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: cncd-e2e-fixture
            target_repo: {repo}
            created: "2026-07-02"
            """
        )
    )
    (plan_dir / "_prose.md").write_text("# cncd-e2e-fixture\n\nProse.\n")
    (plan_dir / "01.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            phase:
              number: 1
              title: Root ready
              tag: agentic
              depends_on: []
              tracking_issue: "https://github.com/{repo}/issues/{issue}"
            tasks:
              - number: 1
                title: t
                steps:
                  - id: P1.T1.S1
                    text: s
            state:
              steps:
                P1.T1.S1: {{ state: " ", ticked_at: null, note: null }}
              completion: {{ at: null, note: null, observed_prs: [] }}
            """
        )
    )


def test_tick_dispatches_eligible_phase_to_cncd(tmp_path: Path, stub_cncd: StubCncd) -> None:
    """
    GIVEN a plan with one ready, tracked, unsynced phase
    AND   a CncdRunner pointed at the stub server
    WHEN  fr_dispatch.tick() runs once
    THEN  the stub received exactly one POST /v1/ingest for the plan
    AND   the Issue gained fr:synced (the dispatch was stamped)
    """
    from fr.parser import parse
    from fr_cncd import CncdRunner
    from fr_dispatch import tick

    repo = "agentic-stoa/cnc-demo"
    plan_dir = tmp_path / "plan"
    _write_plan_with_prose(plan_dir, repo=repo, issue=7)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(repo, set()).update(
        {"fr:ready", "fr:blocked", "fr:synced", "plan:cncd-e2e-fixture", "phase:1"}
    )
    gh.add_issue(repo, 7, state="OPEN", labels={"fr:ready", "phase:1", "plan:cncd-e2e-fixture"})

    result = tick(plan, gh, CncdRunner(base_url=stub_cncd.base_url))

    assert result.errors == 0, result.failures
    assert result.synced == 1
    ingests = [r for r in stub_cncd.requests if r["path"] == "/v1/ingest"]
    assert len(ingests) == 1
    assert ingests[0]["body"]["plan"] == "cncd-e2e-fixture"
    assert ingests[0]["body"]["files"]["_prose.md"].startswith("# cncd-e2e-fixture")
    assert "fr:synced" in gh.issues[(repo, 7)].labels


def test_tick_preflight_blocks_all_phases_without_cncd_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No CNCD_URL → every eligible phase fails cleanly, nothing dispatched."""
    from fr.parser import parse
    from fr_cncd import CncdRunner
    from fr_dispatch import tick

    monkeypatch.delenv("CNCD_URL", raising=False)
    repo = "agentic-stoa/cnc-demo"
    plan_dir = tmp_path / "plan"
    _write_plan_with_prose(plan_dir, repo=repo, issue=7)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(repo, set()).update(
        {"fr:ready", "fr:blocked", "fr:synced", "plan:cncd-e2e-fixture", "phase:1"}
    )
    gh.add_issue(repo, 7, state="OPEN", labels={"fr:ready", "phase:1", "plan:cncd-e2e-fixture"})

    result = tick(plan, gh, CncdRunner())

    assert result.synced == 0
    assert result.skipped == 1
    assert any("CNCD_URL" in f for f in result.failures)
    assert "fr:synced" not in gh.issues[(repo, 7)].labels
