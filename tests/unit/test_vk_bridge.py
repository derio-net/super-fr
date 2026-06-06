def test_bridge_module_importable():
    from fr.bridge import TickResult, VkMcpClient, discover_plans, tick

    assert callable(discover_plans)
    assert callable(tick)
    assert TickResult is not None
    assert VkMcpClient is not None


def test_public_bridge_api_stable():
    """The bridge surface is consumed cross-repo by the live bridge daemon.
    Renaming or moving any of these names is a breaking change."""
    import fr

    assert hasattr(fr.bridge, "discover_plans")
    assert hasattr(fr.bridge, "tick")
    assert hasattr(fr.bridge, "TickResult")
    assert hasattr(fr.bridge, "VkMcpClient")
