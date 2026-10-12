"""R4/R5: every triage config read is lenient, and what it dropped or skipped is shown."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.commands.triage_kanban_cmd import write_board
from fr.triage.batch_dispatch import check_config_fresh
from fr.triage.check import skew_entries
from fr.triage.collect import collect_facts_counted
from fr.triage.components import skew_banner
from fr.triage.errors import TriageError
from fr.triage.kanban import Board
from fr.triage.kanban_render import render_board
from fr.triage.model import Facts, Judgements, Scope, Skipped, TriageConfig
from fr.triage.render import render
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeCheckout
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
    facts, _ = collect_facts_counted(_forge("future_key: 1\n"), SUPER_FR, now=NOW)
    assert facts.repos == [REPO] and facts.skipped == []
    assert facts.config_ignored == {REPO: ["future_key"]}


def test_collect_into_collects_an_unknown_key_and_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: _forge("future_key: 1\n"))
    facts, out, _ = triage_cmd.collect_into(SUPER_FR, tmp_path)
    assert facts.config_ignored == {REPO: ["future_key"]}
    assert json.loads(out.read_text())["config_ignored"] == {REPO: ["future_key"]}


def test_fr_triage_collect_names_the_dropped_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: _forge("futur_key: 1\n"))
    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", REPO, "--dir", str(tmp_path / "s")]
    )
    assert result.exit_code == 0, result.output
    assert REPO in result.output and "futur_key" in result.output
    assert "ignored" in result.output


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


def _checkout(origin_config: dict[str, Any]) -> FakeCheckout:
    checkout = FakeCheckout(Path("."))
    checkout.serve(origin_config)
    return checkout


def test_fresh_config_accepts_an_unknown_origin_key_and_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    facts = _facts(config={REPO: TriageConfig().model_dump(by_alias=True)})
    ref = triage_batch_cmd._fresh_config(_checkout({"future_key": 1}), facts, REPO)  # type: ignore[arg-type]
    assert ref == "origin/main"
    err = capsys.readouterr().err
    assert REPO in err and "future_key" in err


def test_reservation_accepts_an_unknown_origin_key(capsys: pytest.CaptureFixture[str]) -> None:
    facts = _facts(config={REPO: TriageConfig().model_dump(by_alias=True)})
    reserved = triage_batch_cmd._reservation(
        _checkout({"future_key": 1}),  # type: ignore[arg-type]
        facts,
        Judgements.model_validate({"schema": 1}),
        None,  # type: ignore[arg-type]
        REPO,
    )
    assert reserved is None and "future_key" in capsys.readouterr().err


def test_check_config_fresh_returns_the_origin_ignored_keys() -> None:
    assert check_config_fresh(TriageConfig(), "a_key: 1\nb_key: 2\n") == ("a_key", "b_key")
    assert check_config_fresh(None, None) == ()


def test_the_banner_is_empty_with_nothing_skipped_or_ignored() -> None:
    assert skew_banner(_facts()) == ""


def test_the_banner_names_ignored_keys_and_skipped_repos_escaped() -> None:
    facts = _facts(
        config_ignored={REPO: ["future_key", "<b>x</b>"]},
        skipped=[Skipped(repo="o/<i>r</i>", reason="HTTP 502 <script>")],
    )
    banner = skew_banner(facts)
    assert "This page is not the whole truth." in banner
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


def test_the_shared_builder_orders_repos_and_keys_in_banner_and_check(tmp_path: Path) -> None:
    facts = _facts(
        kind="org",
        scope="o",
        repos=["o/a", "o/b", "o/c"],
        config_ignored={"o/c": ["z", "a"], "o/a": ["m"]},
        skipped=[Skipped(repo="o/z", reason="r1"), Skipped(repo="o/b", reason="r2")],
    )
    ignored, skipped = skew_entries(facts)
    assert [r for r, _ in ignored] == ["o/a", "o/c"]
    assert ignored[1][1] == ["a", "z"]
    assert [r for r, _ in skipped] == ["o/b", "o/z"]
    banner = skew_banner(facts)
    positions = [banner.index(f"<b>{r}</b>") for r in ("o/a", "o/c", "o/b", "o/z")]
    assert positions == sorted(positions)
    assert banner.index("a, z") > 0
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    args = ["triage", "check", "--org", "o", "--dir", str(tmp_path), "--json"]
    data = json.loads(CliRunner().invoke(app, args).output)
    assert list(data["config_ignored"]) == ["o/a", "o/c"]
    assert data["config_ignored"]["o/c"] == ["a", "z"]
    assert [x["repo"] for x in data["skipped"]] == ["o/b", "o/z"]


def test_write_board_passes_the_skew_banner_and_places_it_under_the_header(
    tmp_path: Path,
) -> None:
    facts = _facts(
        kind="org",
        scope="derio-net",
        config_ignored={REPO: ["future_key"]},
        skipped=[Skipped(repo="o/r", reason="x")],
    )
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    out, _ = write_board(Scope(kind="org", target="derio-net"), tmp_path, scope_args=[])
    page = out.read_text(encoding="utf-8")
    assert page.count('role="alert"') == 1
    assert page.index("</header>") < page.index('role="alert"') < page.index("future_key")
    assert "o/r" in page


def test_render_board_without_a_banner_has_no_alert() -> None:
    assert 'role="alert"' not in render_board(
        Board(scope="s", collected_at="2026-10-12T00:00:00Z", columns=()),
        scope_args=[],
        rendered_at=datetime(2026, 10, 12, tzinfo=UTC),
        refresh=0,
        notes=[],
    )
