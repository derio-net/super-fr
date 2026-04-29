"""Tests for the registry-diff logic in vk admin labels-sync."""

from vk import labels
from vk.commands.admin_cmd import _diff_labels


def _existing(name: str, color: str, desc: str = "") -> dict:
    return {"name": name, "color": color, "description": desc}


class TestDiffLabelsCreate:
    def test_registry_label_missing_yields_create(self) -> None:
        existing = []
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert len(actions) == 1
        assert actions[0].kind == "create"
        assert actions[0].name == "vk-ready"
        assert actions[0].new_color == "0E8AE6"


class TestDiffLabelsUpdate:
    def test_wrong_color_yields_update(self) -> None:
        existing = [_existing("vk-ready", "aaaaaa", "")]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "update"
        assert actions[0].old_color == "aaaaaa"
        assert actions[0].new_color == "0E8AE6"

    def test_wrong_description_yields_update(self) -> None:
        existing = [_existing("vk-ready", "0E8AE6", "wrong")]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "update"


class TestDiffLabelsAlreadyCorrect:
    def test_matching_label_yields_unchanged(self) -> None:
        existing = [_existing("vk-ready", "0E8AE6", labels.VK_READY.description)]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "unchanged"


class TestDiffLabelsCaseInsensitiveColor:
    def test_color_matches_ignoring_case(self) -> None:
        existing = [_existing("vk-ready", "0e8ae6", labels.VK_READY.description)]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "unchanged"


class TestDiffLabelsNullDescription:
    def test_null_description_treated_as_empty_string(self) -> None:
        # GitHub returns {"description": null} — must compare equal to "" (empty registry desc)
        existing = [{"name": "vk-ready", "color": "0E8AE6", "description": None}]
        # VK_READY.description is a non-empty string; null → "" so it should yield update
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "update"
        assert actions[0].old_desc == ""  # None coerced, not passed through as None

    def test_null_description_matches_empty_registry_desc(self) -> None:
        # A label whose registry description is empty and API returns null → unchanged
        from vk.labels import LabelDef

        empty_desc_label = LabelDef("my-label", "aabbcc", "")
        existing = [{"name": "my-label", "color": "aabbcc", "description": None}]
        actions = _diff_labels(existing=existing, registry=[empty_desc_label])
        assert actions[0].kind == "unchanged"


class TestDiffLabelsExtraExistingIgnored:
    def test_extra_existing_label_produces_no_action(self) -> None:
        # Labels present in existing but absent from the registry are silently
        # ignored — _diff_labels only iterates the registry, never existing.
        # Removal of non-registry labels is handled by _default_label_actions.
        existing = [
            _existing("vk-ready", "0E8AE6", labels.VK_READY.description),
            _existing("custom", "aabbcc"),
        ]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert all(a.name != "custom" for a in actions)
        assert len(actions) == 1  # only vk-ready, no action for custom
