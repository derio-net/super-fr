"""R4/R5: every triage config read is lenient, and what it dropped or skipped is shown."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage import collect as collect_mod
from fr.triage.batch_dispatch import check_config_fresh
from fr.triage.check import classify
from fr.triage.collect import collect_facts_counted
from fr.triage.components import skew_banner, skew_entries
from fr.triage.errors import TriageError
from fr.triage.model import Facts, Judgements, Skipped, parse_triage_config
from fr.triage.render import render
from typer.testing import CliRunner

from tests.unit.test_triage_collect import NOW, ORG, REPO, SUPER_FR, FakeForge, _org_forge

CONFIG = (REPO, ".fr/triage.yaml", "HEAD")


def _forge(body: str) -> FakeForge:
    return FakeForge(
        issues={REPO: []}, prs={REPO: []}, viewer="operator", file_bodies={CONFIG: body}
    )


def _facts(**kw: Any) -> Facts:
    return Facts.model_validate(
        {
            "schema": 9,
            "scope": "derio-net--super-fr",
            "kind": "repo",
            "collected_at": "2026-10-12T00:00:00+00:00",
            "repos": [REPO],
            "issues": [],
            **kw,
        }
    )


def test_an_unknown_key_is_collected_and_named_without_any_lenient_argument() -> None:
    assert "lenient" not in inspect.signature(collect_facts_counted).parameters
    facts, _ = collect_facts_counted(_forge("future_key: 1\n"), SUPER_FR, now=NOW)
    assert facts.repos == [REPO] and facts.skipped == []
    assert facts.config_ignored == {REPO: ["future_key"]}


def test_an_invalid_value_still_fails_a_repo_scope_collect() -> None:
    with pytest.raises(TriageError, match="not valid triage config"):
        collect_facts_counted(_forge("stale_dispatch_days: -1\n"), SUPER_FR, now=NOW)


def test_an_invalid_value_still_skips_the_repo_in_org_scope() -> None:
    forge = _org_forge()
    forge.file_bodies[("example-org/beta", ".fr/triage.yaml", "HEAD")] = "stale_dispatch_days: -1\n"
    forge.file_bodies[("example-org/alpha", ".fr/triage.yaml", "HEAD")] = "future_key: 1\n"
    facts, _ = collect_facts_counted(forge, ORG, now=NOW)
    assert [s.repo for s in facts.skipped] == ["example-org/beta"]
    assert facts.config_ignored == {"example-org/alpha": ["future_key"]}


def test_the_freshness_check_and_fresh_config_accept_an_unknown_key() -> None:
    collected = parse_triage_config({}, lenient=True)[0]
    check_config_fresh(collected, "future_key: 1\n")  # no lenient argument, no refusal
    assert "lenient" not in inspect.signature(triage_batch_cmd._fresh_config).parameters
    assert "lenient" not in inspect.signature(collect_mod.collect_facts_counted).parameters


def test_the_banner_is_empty_with_nothing_skipped_or_ignored() -> None:
    assert skew_banner(_facts()) == ""


def test_the_banner_names_ignored_keys_and_skipped_repos_escaped() -> None:
    facts = _facts(
        config_ignored={REPO: ["future_key", "<b>x</b>"]},
        skipped=[Skipped(repo="o/<i>r</i>", reason="HTTP 502 <script>")],
    )
    banner = skew_banner(facts)
    assert 'role="alert"' in banner and "upgrade fr to read them" in banner
    assert "future_key" in banner and "&lt;b&gt;x&lt;/b&gt;" in banner
    assert "o/&lt;i&gt;r&lt;/i&gt;" in banner and "HTTP 502 &lt;script&gt;" in banner
    assert "<script>" not in banner and "<b>x" not in banner


def test_triage_html_renders_the_banner_directly_under_the_nav_and_no_skipped_note() -> None:
    facts = _facts(config_ignored={REPO: ["future_key"]}, skipped=[Skipped(repo="o/r", reason="x")])
    page = render(facts, Judgements.model_validate({"schema": 1}))
    nav_end = page.index("</nav>")
    assert page.index('role="alert"') > nav_end
    assert "<nav" not in page[nav_end : page.index('role="alert"')]
    assert "Skipped o/r" not in page


def test_check_names_skipped_and_ignored_in_json_and_first_in_the_text(tmp_path: Path) -> None:
    facts = _facts(config_ignored={REPO: ["future_key"]}, skipped=[Skipped(repo="o/r", reason="x")])
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    args = ["triage", "check", "--repo", REPO, "--dir", str(tmp_path)]
    data = json.loads(CliRunner().invoke(app, [*args, "--json"]).output)
    assert data["skipped"] == [{"repo": "o/r", "reason": "x"}]
    assert data["config_ignored"] == {REPO: ["future_key"]}
    text = CliRunner().invoke(app, args).output
    order = [text.index(s) for s in ("skipped repos", "config ignored", "closed in progress")]
    assert order == sorted(order) and text.splitlines()[0].startswith("skipped repos")


def test_banner_and_check_share_one_list_builder() -> None:
    facts = _facts(config_ignored={REPO: ["k"]}, skipped=[Skipped(repo="o/r", reason="x")])
    result = classify(facts, Judgements.model_validate({"schema": 1}))
    ignored, skipped = skew_entries(facts)
    assert result.config_ignored == ignored and result.skipped == skipped
