"""Phase 4: tier→model config resolver (`fr models`).

Spec §B.2: `tier` is harness-neutral metadata on a phase; the `tier → model`
binding lives in ~/.config/fr/models.yaml (user) with an optional repo
override (resolution order repo > user), and a missing binding returns None so
the caller can fall back to a runtime prompt.
"""

from __future__ import annotations

from pathlib import Path


class TestLoadModels:
    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        from fr.models import load_models

        assert load_models(tmp_path / "nope.yaml") == {}

    def test_parses_harness_tier_model(self, tmp_path: Path) -> None:
        from fr.models import load_models

        p = tmp_path / "models.yaml"
        p.write_text(
            "claude-code:\n"
            "  mechanical: claude-haiku-4-5\n"
            "  standard: claude-sonnet-5\n"
            "  hard: claude-opus-4-8\n"
        )
        cfg = load_models(p)
        assert cfg["claude-code"]["hard"] == "claude-opus-4-8"


class TestResolve:
    def test_user_binding(self) -> None:
        from fr.models import resolve

        user = {"claude-code": {"hard": "claude-opus-4-8"}}
        assert resolve("claude-code", "hard", repo_cfg={}, user_cfg=user) == "claude-opus-4-8"

    def test_repo_overrides_user(self) -> None:
        from fr.models import resolve

        user = {"claude-code": {"hard": "claude-opus-4-8"}}
        repo = {"claude-code": {"hard": "claude-sonnet-5"}}
        assert resolve("claude-code", "hard", repo_cfg=repo, user_cfg=user) == "claude-sonnet-5"

    def test_missing_binding_returns_none(self) -> None:
        from fr.models import resolve

        assert resolve("claude-code", "hard", repo_cfg={}, user_cfg={}) is None

    def test_unknown_harness_returns_none(self) -> None:
        from fr.models import resolve

        user = {"claude-code": {"hard": "x"}}
        assert resolve("opencode", "hard", repo_cfg={}, user_cfg=user) is None


# ── review r-p2-f2: one rule, two implementations, disagreeing ───────────
#
# Extracting `_resolved_config()` in models_cmd gave the three CLI verbs one
# resolution path — and left `fr.models.resolve()` with no production caller
# at all, so the repo-over-user rule now existed twice. They did not agree:
# `resolve()` treats a falsy binding as "not bound" and falls through to the
# user config, while a dict merge lets the falsy repo value win. Moving the
# whole-config form into `fr.models` and defining `resolve()` on top of it
# is what makes "one rule" true rather than aspirational.


def test_a_falsy_repo_binding_does_not_shadow_a_real_user_one() -> None:
    from fr.models import resolve, resolved_config

    repo = {"opencode": {"hard": ""}}
    user = {"opencode": {"hard": "provider/U"}}

    assert resolve("opencode", "hard", repo_cfg=repo, user_cfg=user) == "provider/U"
    assert resolved_config(repo_cfg=repo, user_cfg=user)["opencode"]["hard"] == "provider/U"


def test_resolve_and_resolved_config_never_disagree() -> None:
    """`resolve()` is a lookup on `resolved_config()`, so any (harness, tier)
    either module can name must give the same answer."""
    from fr.models import resolve, resolved_config

    repo = {"opencode": {"hard": "provider/R"}, "claude-code": {"standard": ""}}
    user = {
        "opencode": {"hard": "provider/U", "standard": "provider/US"},
        "claude-code": {"standard": "provider/CU"},
    }

    merged = resolved_config(repo_cfg=repo, user_cfg=user)
    for harness, tiers in merged.items():
        for tier in tiers:
            assert merged[harness][tier] == resolve(harness, tier, repo_cfg=repo, user_cfg=user), (
                f"{harness}/{tier} disagrees"
            )
