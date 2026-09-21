"""Triage state models, schema refusal and the state directory (spec §3.B, §3.D).

Plan 2026-09-21-fr-triage, P2.T1. Every test that needs a HOME sandboxes it to
tmp_path, so nothing here reads or writes the real cache.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.triage.errors import TriageError
from fr.triage.model import (
    Judgements,
    Scope,
    issue_key,
    normalize_key,
    load_facts,
    load_judgements,
    state_dir,
)

JUDGEMENTS_YAML = """\
schema: 1
ranked_at: 2026-09-21
tiers:
  - {n: 1, title: Data loss, description: Work destroyed with no prompt or salvage.}
  - {n: 2, title: Silent wrongness, description: The failure looks like success.}
issues:
  "super-fr#435":
    tier: 1
    theme: isolation
    cx: S
    verified: true
    detail: "`gc()` trusts `pr_state == MERGED` and calls `down(force=False)`"
    note: ""
  "super-fr#1":  {tier: 2, cx: XS}
  "super-fr#2":  {tier: 2, cx: S-M}
  "super-fr#3":  {tier: 2, cx: M}
  "super-fr#4":  {tier: 2, cx: L}
  "super-fr#5":  {tier: 2, cx: "-"}
patterns:
  - title: A fact about remote state used to justify local destruction
    ids: ["super-fr#435"]
    body: "x"
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_a_judgements_file_shaped_like_the_spec_loads(tmp_path: Path) -> None:
    j = load_judgements(_write(tmp_path / "judgements.yaml", JUDGEMENTS_YAML))

    assert isinstance(j, Judgements)
    assert [t.n for t in j.tiers] == [1, 2]
    assert j.issues["super-fr#435"].verified is True
    assert j.issues["super-fr#435"].theme == "isolation"
    assert {j.issues[f"super-fr#{n}"].cx for n in range(1, 6)} == {"XS", "S-M", "M", "L", "-"}
    assert j.issues["super-fr#435"].cx == "S"
    assert j.patterns[0].ids == ["super-fr#435"]


@pytest.mark.parametrize("key", ["derio-net/super-fr#435", "super-fr 435", "super-fr#", "#435"])
def test_a_judgement_key_must_be_repo_name_hash_number(tmp_path: Path, key: str) -> None:
    text = JUDGEMENTS_YAML.replace('"super-fr#1"', json.dumps(key))
    path = _write(tmp_path / "judgements.yaml", text)

    with pytest.raises(TriageError, match=str(path)):
        load_judgements(path)


def test_an_unknown_cx_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path / "judgements.yaml", JUDGEMENTS_YAML.replace("cx: XS", "cx: XL"))

    with pytest.raises(TriageError, match=str(path)):
        load_judgements(path)


def test_schema_2_in_judgements_is_refused_naming_the_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "judgements.yaml", JUDGEMENTS_YAML.replace("schema: 1", "schema: 2"))

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_judgements(path)
    assert "schema" in str(exc.value)


def test_schema_2_in_facts_is_refused_naming_the_file(tmp_path: Path) -> None:
    facts = {
        "schema": 2,
        "scope": "derio-net--super-fr",
        "kind": "repo",
        "collected_at": "2026-09-21T00:00:00+00:00",
        "repos": ["derio-net/super-fr"],
        "issues": [],
        "skipped": [],
        "warnings": [],
    }
    path = _write(tmp_path / "facts.json", json.dumps(facts))

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_facts(path)
    assert "schema" in str(exc.value)


def test_unreadable_yaml_is_refused_naming_the_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "judgements.yaml", "schema: [1\n")

    with pytest.raises(TriageError, match=str(path)):
        load_judgements(path)


def test_default_state_dir_for_a_repo_is_under_home_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-must-be-ignored"))

    got = state_dir(Scope(kind="repo", target="derio-net/super-fr"))

    assert got == tmp_path / ".cache" / "fr" / "triage" / "derio-net--super-fr"


def test_default_state_dir_for_an_org_is_under_home_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    got = state_dir(Scope(kind="org", target="derio-net"))

    assert got == tmp_path / ".cache" / "fr" / "triage" / "derio-net"


@pytest.mark.parametrize(
    "scope",
    [Scope(kind="repo", target="derio-net/super-fr"), Scope(kind="org", target="derio-net")],
)
def test_dir_overrides_the_default_for_both_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scope: Scope
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    override = tmp_path / "elsewhere"

    assert state_dir(scope, override) == override


# ------------------------------------------------ review r-p2-case


def test_normalize_key_lowercases_a_judgement_key() -> None:
    assert normalize_key("Super-FR#435") == "super-fr#435"
    assert normalize_key("super-fr#435") == "super-fr#435"


def test_issue_key_is_constructed_lowercase() -> None:
    assert issue_key("Derio-Net/Super-FR", 5) == "super-fr#5"


def test_scope_name_is_lowercase_so_typed_case_names_one_state_dir() -> None:
    assert Scope(kind="repo", target="Derio-Net/Super-FR").name == "derio-net--super-fr"
    assert Scope(kind="org", target="Derio-Net").name == "derio-net"


def test_judgement_keys_are_lowercased_on_load(tmp_path: Path) -> None:
    text = JUDGEMENTS_YAML.replace('"super-fr#435"', '"Super-FR#435"')
    j = load_judgements(_write(tmp_path / "judgements.yaml", text))

    assert "super-fr#435" in j.issues
    assert "Super-FR#435" not in j.issues


def test_two_judgement_keys_differing_only_by_case_are_a_conflict(tmp_path: Path) -> None:
    text = JUDGEMENTS_YAML.replace('"super-fr#1":  {tier: 2, cx: XS}', '"Super-FR#435": {tier: 2}')
    path = _write(tmp_path / "judgements.yaml", text)

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_judgements(path)
    assert "conflict" in str(exc.value)
    assert "Super-FR#435" in str(exc.value)


# ------------------------------------------------ review r-p2-pattern-ids


@pytest.mark.parametrize("bad", ["super-fr 435", "derio-net/super-fr#435", "super-fr#", "435"])
def test_a_typod_pattern_id_is_refused_naming_the_file(tmp_path: Path, bad: str) -> None:
    text = JUDGEMENTS_YAML.replace('ids: ["super-fr#435"]', f"ids: [{json.dumps(bad)}]")
    path = _write(tmp_path / "judgements.yaml", text)

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_judgements(path)
    assert bad in str(exc.value)


def test_pattern_ids_go_through_the_same_normaliser_as_keys(tmp_path: Path) -> None:
    text = JUDGEMENTS_YAML.replace('ids: ["super-fr#435"]', 'ids: ["Super-FR#435"]')
    j = load_judgements(_write(tmp_path / "judgements.yaml", text))

    assert j.patterns[0].ids == ["super-fr#435"]


# ------------------------------------------------ review r-p2-schema-strict


def _facts_doc(**over: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "schema": 1,
        "scope": "example-org",
        "kind": "org",
        "collected_at": "2026-09-21T00:00:00+00:00",
        "repos": ["example-org/alpha", "example-org/beta"],
        "issues": [],
        "skipped": [{"repo": "example-org/beta", "reason": "HTTP 403"}],
        "warnings": [],
    }
    doc.update(over)
    return doc


@pytest.mark.parametrize("value", ["true", "1.0"])
def test_a_schema_equal_to_1_but_not_the_int_1_is_refused_in_judgements(
    tmp_path: Path, value: str
) -> None:
    path = _write(
        tmp_path / "judgements.yaml", JUDGEMENTS_YAML.replace("schema: 1", f"schema: {value}")
    )

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_judgements(path)
    assert "schema" in str(exc.value)


@pytest.mark.parametrize("value", [True, 1.0])
def test_a_schema_equal_to_1_but_not_the_int_1_is_refused_in_facts(
    tmp_path: Path, value: object
) -> None:
    path = _write(tmp_path / "facts.json", json.dumps(_facts_doc(schema=value)))

    with pytest.raises(TriageError, match=str(path)) as exc:
        load_facts(path)
    assert "schema" in str(exc.value)


# ------------------------------------------------ review r-p2-repos-doc


def test_collected_is_the_scope_minus_the_skipped_repos(tmp_path: Path) -> None:
    facts = load_facts(_write(tmp_path / "facts.json", json.dumps(_facts_doc())))

    assert facts.repos == ["example-org/alpha", "example-org/beta"]
    assert facts.collected == ["example-org/alpha"]
