def test_oversize_bodies_and_payloads_yield_no_figures() -> None:
    import base64
    import json

    from fr.debt.render import FIGURES_PREFIX, parse_figures

    def block(raw: bytes) -> str:
        return f"{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->"

    ok = block(json.dumps({"owed": 1, "acceptance": {"ci": 2}}).encode())
    assert parse_figures(ok) == {"owed": 1, "acceptance": {"ci": 2}}
    assert parse_figures(ok + " " * 70000) is None  # body past 64 KiB
    assert (
        parse_figures(block(json.dumps({"x": "y" * 9000}).encode())) is None
    )  # payload past 8 KiB
    for hostile in ({"a": [1]}, {"a": {"b": {"c": 1}}}, {"a": "z" * 500}, [1], {"a": {"b": [1]}}):
        assert parse_figures(block(json.dumps(hostile).encode())) is None
