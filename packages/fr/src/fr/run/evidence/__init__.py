"""The verifiers `fr run resolve` checks a step's evidence with (spec 2026-11-27-run-verdict R7).

One module per concern, each at most 800 lines. A verifier whose witness the resolve
stores as a `str` returns a `fr.run.verdict.Verdict[str]`; any other function that
refuses raises `fr.run.verdict.RunRefusal`. `fr.commands.run_cmd` prints both.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""
