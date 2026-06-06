"""Public API stability for the split bridge surface.

The framework (`fr_dispatch`) and the VK adapter (`fr_vk`) are consumed
cross-repo by the live bridge daemon. Renaming or moving any of these
names is a breaking change.
"""


def test_framework_module_importable():
    from fr_dispatch import Runner, TickResult, discover_plans, tick

    assert callable(discover_plans)
    assert callable(tick)
    assert TickResult is not None
    assert Runner is not None


def test_adapter_module_importable():
    from fr_vk import VkMcpClient, VkRunner

    assert VkMcpClient is not None
    assert VkRunner is not None


def test_public_api_stable():
    import fr_dispatch
    import fr_vk

    for name in ("discover_plans", "tick", "TickResult", "Runner"):
        assert hasattr(fr_dispatch, name)
    for name in ("VkMcpClient", "VkRunner"):
        assert hasattr(fr_vk, name)
