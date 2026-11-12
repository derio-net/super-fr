"""R9 tripwire (spec 2026-11-04-repo-feature-settings; p3-r3): every forge write call site in
`packages/*/src` is listed here with the `forge_allows`-family check that guards it.

A forge write is a call to a write method of the forge adapters (an issue or PR comment,
label, issue creation, edit or close) or a raw `gh issue|pr comment|edit|create|close` /
`gh api -X POST|PATCH|DELETE` argv. The adapters themselves (`fr.gh`, `fr.glab`, `fr.tea`,
`fr.ghclient`, the `real_*client` modules) implement those writes and are not call sites.

A new call site fails this test until it is listed below, with a comment naming the
check that decides it: `forge_block` / `forge_allows` / `require_forge` (tracker writes),
`ledger_block` (the PR gate ledger), or `fr.settings.remote`'s policy for a repo fr has
no checkout of. A listed site that no longer exists fails too, so the list stays true.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[2] / "packages"

WRITE_METHODS = frozenset({
    "comment_issue", "comment_pr", "edit_issue_comment", "edit_issue_labels", "edit_pr_labels",
    "swap_issue_labels", "ensure_labels", "ensure_label", "delete_label", "create_issue",
    "close_issue", "comment_close_issue", "edit_issue_state", "edit_issue_body", "edit_issue",
    "create_pr", "pr_create",
})  # fmt: skip
"""The adapters' issue/PR comment, label and issue writes (the `forge.*` kinds), and PR
creation (`git.pr`, R11/R12: `fr pr create` for the skills, the internal openers listed)."""

ADAPTERS = frozenset({
    "fr/src/fr/gh.py", "fr/src/fr/glab.py", "fr/src/fr/tea.py", "fr/src/fr/ghclient.py",
    "fr/src/fr/real_ghclient.py", "fr/src/fr/real_ghrestclient.py",
    "fr/src/fr/real_glabclient.py", "fr/src/fr/real_teaclient.py",
})  # fmt: skip

_VERBS = frozenset({"comment", "edit", "create", "close"})
_ARGV_VERBS = {"issue": _VERBS, "pr": _VERBS}
_API_WRITES = {"POST", "PATCH", "DELETE", "PUT"}

GATED: dict[str, str] = {
    # -- tracker writes on this checkout's repo --------------------------------------------
    "fr/src/fr/apply.py::_execute_one":
        "apply_cmd._apply_one: require_forge(issues), require_forge(labels); "
        "fr_dispatch.tick: _quiet_filtered (client_policy per mutation's repo and kind)",
    "fr/src/fr/archive_followups.py::file_open_ends":
        "archive_cmd / journal_cmd file / run.closeout: require_forge(issues, labels)",
    "fr/src/fr/archive_followups.py::file_owed_ends":
        "archive_cmd / journal_cmd file / run.closeout: require_forge(issues, labels)",
    "fr/src/fr/commands/acceptance_cmd.py::comment_cmd":
        "forge.report_comment must be on, and forge_block(comments) refuses; --yes writes",
    "fr/src/fr/commands/debt_cmd.py::issue_cmd":
        "forge_block(issues) refuses; forge_block(comments) makes the zero-debt close bare",
    "fr/src/fr/commands/journal_cmd.py::_close_owed_issue":
        "require_forge(issues); forge_allows(comments) for the discharge comment",
    "fr/src/fr/commands/undispatch_cmd.py::undispatch_command":
        "require_forge(issues); forge_allows(comments) for the close comment",
    # -- triage: the batch's repo ----------------------------------------------------------
    "fr/src/fr/commands/triage_batch_cmd.py::batch_cancel_command":
        "_tracking_gate: require_forge(labels), require_forge(comments) on the batch's clone",
    "fr/src/fr/commands/triage_batch_cmd.py::_forge_writes":
        "callers dispatch_batch / adopt_batch run _tracking_gate (labels, comments) first",
    "fr/src/fr/commands/triage_batch_cmd.py::adopt_batch._comment":
        "adopt_batch runs _tracking_gate (labels, comments) before any forge call",
    "fr/src/fr/commands/triage_batch_cmd.py::_Driver._label_awaiting":
        "_Driver.forge_off(labels): the checkout's policy, else the forge-read policy",
    "fr/src/fr/commands/triage_batch_cmd.py::_Driver._collected_merged":
        "_Driver.forge_off(labels) on the marker's repo",
    "fr/src/fr/triage/approval.py::settle_approvals":
        "_labels_off: client_policy(labels) (a dry run writes nothing)",
    "fr/src/fr/triage/approval.py::ensure_approval_label": "_labels_off: client_policy(labels)",
    "fr/src/fr/triage/claim_writes.py::_add_label":
        "reached only from claim/refresh, after _gate (quiet_block: labels, comments)",
    "fr/src/fr/triage/claim_writes.py::_remove_label":
        "reached only from release/settle_closed, after _gate (quiet_block)",
    "fr/src/fr/triage/claim_writes.py::_drop_orphan_label":
        "reached only from claim, after _gate (quiet_block)",
    "fr/src/fr/triage/claim_writes.py::claim": "_gate: quiet_block (labels, comments)",
    "fr/src/fr/triage/claim_writes.py::refresh": "_gate: quiet_block (labels, comments)",
    "fr/src/fr/triage/claim_writes.py::release": "_gate: quiet_block (labels, comments)",
    "fr/src/fr/triage/claim_writes.py::settle_closed": "_gate: quiet_block (labels, comments)",
    "fr/src/fr/triage/claim_writes.py::take": "_gate: quiet_block (labels, comments)",
    # -- the PR gate ledger (forge.labels / forge.comments only) ---------------------------
    "fr/src/fr/verification/labels.py::sync_exit_labels": "ledger_block(labels)",
    "fr/src/fr/verification/labels.py::pass_gate":
        "callers: gate_cmd._forge_policy (ledger_block labels refuses, comments decides "
        "`comment=`); _Driver._pass_gate (_Driver.ledger_off labels, comments)",
    "fr/src/fr/gatebackfill/apply.py::_Writer._ensure":
        "gate_cmd.backfill_command: ledger_block(labels) refuses before apply_plan",
    "fr/src/fr/gatebackfill/apply.py::_Writer.pr_label":
        "gate_cmd.backfill_command: ledger_block(labels)",
    "fr/src/fr/gatebackfill/apply.py::_Writer.issue_labels":
        "backfill_command: ledger_block(labels); tracker issues only with issues=forge_allows",
    "fr/src/fr/gatebackfill/apply.py::_Writer.create_issue":
        "backfill_command: apply_plan(issues=forge_allows(issues))",
    "fr/src/fr/gatebackfill/apply.py::_Writer.rewrite_body":
        "backfill_command: apply_plan(issues=forge_allows(issues))",
    "fr/src/fr/gatebackfill/apply.py::_Writer.comment":
        "backfill_command: apply_plan(comments=issues and forge_allows(comments))",
    "fr/src/fr/gatebackfill/apply.py::_Writer.close":
        "backfill_command: apply_plan(issues=forge_allows(issues))",
    "fr/src/fr/gatebackfill/apply.py::_Apply._own":
        "backfill_command: apply_plan(issues=forge_allows(issues))",
    "fr/src/fr/gatebackfill/close.py::_close_owned":
        "callers: close_gate_trackers <- gate_cmd.pass_command (trackers_off: forge block "
        "issues, comments); _Driver._pass_gate (_Driver.forge_off issues, comments)",
    "fr/src/fr/gatebackfill/close.py::_keep_owned":
        "callers: close_gate_trackers <- gate_cmd.pass_command (trackers_off: forge block "
        "issues, comments); _Driver._pass_gate (_Driver.forge_off issues, comments)",
    "fr/src/fr/gatebackfill/close.py::_keep_adopted":
        "callers: close_gate_trackers <- gate_cmd.pass_command (trackers_off: forge block "
        "issues, comments); _Driver._pass_gate (_Driver.forge_off issues, comments)",
    # -- a repo fr has no checkout of: fr.settings.remote ----------------------------------
    "fr/src/fr/tracker/github.py::GithubTracker.transition":
        "_require_quiet_ok: client_policy(labels[, issues])",
    "fr-dispatch/src/fr_dispatch/__init__.py::tick":
        "_forge_block(labels) for the dispatch stamp (client_policy)",
    "fr-vk/src/fr_vk/pr_state.py::_default_close_gh_issue": "client_policy(issues)",
    # -- PR creation: git.pr (R11, R12) -----------------------------------------------------
    "fr/src/fr/commands/pr_cmd.py::create_cmd":
        "fr pr create: require_approval under git.pr: ask; always a draft",
    "fr/src/fr/commands/triage_batch_cmd.py::_Driver._export":
        "the triage driver's state export: R12's internal pusher, refused under push: ask by R5",
    "fr/src/fr/commands/triage_batch_cmd.py::adopt_batch._create":
        "batch adopt's supersede: the triage driver's own PR (R5 refuses push: ask there)",
    "fr/src/fr/triage/batch_closeout.py::execute":
        "the batch close-out PR: the triage driver's, R5 refuses push: ask for a driven scope",
    "fr/src/fr/ops/gate.py::stage_8":
        "the DevOps gate at the operator's terminal: R12's named internal opener",
    "fr/src/fr/commands/debt_cmd.py::_open_or_refresh":
        "the debt sweep's bot-owned branch PR, opened at the operator's command",
    # -- not a forge write ------------------------------------------------------------------
    "fr-vk/src/fr_vk/dispatch.py::dispatch_phase":
        "not a forge write: `mcp.create_issue` makes a VibeKanban card",
}  # fmt: skip


def _argv_write(node: ast.List) -> str | None:
    words = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    if words[:1] == ["gh"]:
        words = words[1:]
    if len(words) >= 2 and words[1] in _ARGV_VERBS.get(words[0], set()):
        return f"gh {words[0]} {words[1]}"
    if words[:1] == ["api"]:
        for flag, value in zip(words, words[1:], strict=False):
            if flag in ("-X", "--method") and value.upper() in _API_WRITES:
                return f"gh api {value.upper()}"
    return None


def call_sites(src_root: Path, base: Path) -> dict[str, list[str]]:
    """`<path relative to base>::<qualified function>` -> the writes it makes."""
    found: dict[str, list[str]] = {}
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(base).as_posix()
        if rel in ADAPTERS:
            continue
        stack: list[str] = []

        def note(what: str, rel: str = rel) -> None:
            found.setdefault(f"{rel}::{'.'.join(stack) or '<module>'}", []).append(what)

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815
            visit_ClassDef = visit_FunctionDef  # type: ignore[assignment]  # noqa: N815

            def visit_Call(self, node: ast.Call) -> None:
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if name in WRITE_METHODS:
                    note(name)
                self.generic_visit(node)

            def visit_List(self, node: ast.List) -> None:
                what = _argv_write(node)
                if what is not None:
                    note(what)
                self.generic_visit(node)

        Visitor().visit(ast.parse(path.read_text(), filename=str(path)))
    return found


def _all_sites() -> dict[str, list[str]]:
    sites: dict[str, list[str]] = {}
    for src in sorted(PACKAGES.glob("*/src")):
        sites.update(call_sites(src, PACKAGES))
    return sites


def test_every_forge_write_call_site_is_gated() -> None:
    ungated = {k: v for k, v in _all_sites().items() if k not in GATED}
    assert not ungated, (
        "forge writes with no recorded forge_allows check (R9). Gate each with "
        "fr.settings (forge_block / ledger_block / fr.settings.remote) and list it in "
        f"GATED with the check that guards it:\n{ungated}"
    )


def test_every_listed_site_still_writes() -> None:
    stale = sorted(set(GATED) - set(_all_sites()))
    assert not stale, f"GATED lists sites that make no forge write any more: {stale}"


def test_every_listed_site_names_its_guard() -> None:
    assert all(why.strip() for why in GATED.values())


def test_a_new_ungated_call_is_caught(tmp_path: Path) -> None:
    """The tripwire fires on a synthetic module: a client write method, a raw `gh` argv
    and a `gh api` POST, each named by file and function."""
    src = tmp_path / "pkg" / "src" / "mod"
    src.mkdir(parents=True)
    (src / "rogue.py").write_text(
        "def label_it(client):\n"
        "    client.edit_issue_labels('o/r', 1, add=frozenset({'x'}), remove=frozenset())\n"
        "\n"
        "class Poster:\n"
        "    def post(self, run):\n"
        "        run(['gh', 'pr', 'comment', '5', '--body', 'hi'])\n"
        "        run(['api', '-X', 'POST', 'repos/o/r/issues/1/comments'])\n"
        "\n"
        "def read_only(client):\n"
        "    client.view_issue('o/r', 1)\n"
        "    run(['gh', 'issue', 'view', '1'])\n"
    )
    sites = call_sites(tmp_path / "pkg" / "src", tmp_path)
    assert sites == {
        "pkg/src/mod/rogue.py::label_it": ["edit_issue_labels"],
        "pkg/src/mod/rogue.py::Poster.post": ["gh pr comment", "gh api POST"],
    }
    assert set(sites) - set(GATED) == set(sites)  # none of them is listed: each would fail
