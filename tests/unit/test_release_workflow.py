"""`.github/workflows/release.yml` (spec 2026-09-26-version-bump-churn §3.C).

It replaces `auto-tag.yml`: runs on every push to `main` and on a manual
dispatch with an optional `version`, one run at a time, never cancelled, and
drives `scripts/release.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"


def _workflow() -> dict[Any, Any]:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict)
    return data


def _on() -> dict[str, Any]:
    data = _workflow()
    # PyYAML reads the bare key `on` as boolean True.
    on = data.get("on", data.get(True))
    assert isinstance(on, dict)
    return on


def _steps() -> list[dict[str, Any]]:
    return [step for job in _workflow()["jobs"].values() for step in job["steps"]]


def _jobs() -> dict[str, dict[str, Any]]:
    jobs = _workflow()["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _job_steps(name: str) -> list[dict[str, Any]]:
    steps = _jobs()[name]["steps"]
    assert isinstance(steps, list)
    return steps


def _uses(step: dict[str, Any], action: str) -> bool:
    return str(step.get("uses", "")).startswith(action)


def _checkout(name: str) -> dict[str, Any]:
    (checkout,) = [s for s in _job_steps(name) if _uses(s, "actions/checkout")]
    return checkout


def _release_py_steps(name: str) -> list[dict[str, Any]]:
    return [s for s in _job_steps(name) if "scripts/release.py" in str(s.get("run", ""))]


APP_OR_DEFAULT = "${{ steps.app-token.outputs.token || github.token }}"
TOKEN_JOBS = ("prepare", "publish")
CREDENTIAL_FREE_JOBS = ("collect", "test")


def test_triggers_on_push_to_main_and_the_merge_queue_hold_with_no_path_filter() -> None:
    push = _on()["push"]
    # `fr-hold/**` is the merge queue's hold ref (spec 2026-11-19-wave-merge-queue R19): a
    # drain, by landing, forge merge or deferral, starts a release through its push
    assert push["branches"] == ["main", "fr-hold/**"]
    assert "paths" not in push  # every merge may carry a fragment


def _job_runs(job: str, **event: object) -> bool:
    """*job*'s `if:` evaluated for a push event: *ref*, *deleted*, *message*."""
    import re

    expr = _jobs()[job]["if"]
    py = re.sub(r"!(?!=)", " not ", expr.replace("&&", " and ").replace("||", " or "))
    py = py.replace("github.event.deleted", "deleted").replace("github.ref", "ref")
    py = py.replace("github.event.head_commit.message", "message").replace("true", "True")
    return bool(
        eval(  # noqa: S307 - the workflow's own expression, over four names
            py,
            {"startsWith": lambda a, b: str(a).startswith(b)},
            {"ref": "refs/heads/main", "deleted": False, "message": "", **event},
        )
    )


def _prepare_runs(**event: object) -> bool:
    return _job_runs("prepare", **event)


def _relay_runs(**event: object) -> bool:
    return _job_runs("hold-relay", **event)


HOLD = "refs/heads/fr-hold/queue"
DRAINED = "fr-hold: drained scope s wave 1 opened x refreshed y"


def test_a_deleted_hold_starts_no_release() -> None:
    """R19: deleting the hold is the operator clearing it by hand; neither `prepare` nor the
    relay runs, and every job but the relay needs `prepare`'s `cut` output."""
    assert not _prepare_runs(ref=HOLD, deleted=True, message="")
    assert not _relay_runs(ref=HOLD, deleted=True, message=DRAINED)
    for name, job in _jobs().items():
        if name not in ("prepare", "hold-relay"):
            assert "needs.prepare.outputs.cut" in str(job.get("if", "")), name


def test_only_a_drained_hold_push_dispatches_a_release_on_main() -> None:
    """p4-r2: the hold is pushed at open, refreshed hourly and cleared, and only the drain
    needs a release; it is relayed as a dispatch on main, never run on the hold ref."""
    for state in ("open", "cleared"):
        msg = f"fr-hold: {state} scope s wave 1 opened x"
        assert not _relay_runs(ref=HOLD, message=msg)
        assert not _prepare_runs(ref=HOLD, message=msg)
    assert _relay_runs(ref=HOLD, message=DRAINED)
    assert not _prepare_runs(ref=HOLD, message=DRAINED)
    # main pushes, the schedule and a dispatch are unchanged (no head commit message for the
    # last two), and the relay never runs off the hold ref
    assert _prepare_runs(ref="refs/heads/main", message="feat: a change (#1)")
    assert _prepare_runs(ref="refs/heads/main", message="")
    assert not _prepare_runs(ref="refs/heads/main", deleted=True)
    assert not _relay_runs(ref="refs/heads/main", message="fr-hold: drained x")


def test_the_hold_relay_holds_no_secret_and_dispatches_on_main() -> None:
    """Spec 2026-11-21-release-app-hardening R1/R2: a hold push runs the hold branch's own
    workflow file, so it must never reach the `release` environment. The relay names no
    environment, holds only `actions: write`, reads no secret and dispatches on main."""
    job = _jobs()["hold-relay"]
    assert "environment" not in job
    assert job["permissions"] == {"actions": "write"}
    text = yaml.safe_dump(job)
    assert "secrets." not in text and "app-token" not in text
    (step,) = job["steps"]
    assert step["run"] == 'gh workflow run release.yml --repo "$GITHUB_REPOSITORY" --ref main'
    assert step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    for name in TOKEN_JOBS:
        assert _jobs()[name]["environment"] == "release"


def test_the_hold_is_cleared_by_the_job_that_ends_the_run_with_the_token_it_holds() -> None:
    """R18: the clear is release.py's last step, in `prepare` (it cuts nothing) or `publish`
    (after the push), the two jobs that hold the token; no credential-free job runs it."""
    for name in TOKEN_JOBS:
        (step,) = [s for s in _release_py_steps(name)]
        assert "GH_TOKEN" in step["env"]
    for name in CREDENTIAL_FREE_JOBS:
        for step in _release_py_steps(name):
            assert "publish" not in str(step["run"]) and "prepare" not in str(step["run"])


def test_manual_dispatch_takes_an_optional_version() -> None:
    inputs = _on()["workflow_dispatch"]["inputs"]
    assert inputs["version"]["required"] is False


def test_runs_one_at_a_time_and_is_never_cancelled() -> None:
    concurrency = _workflow()["concurrency"]
    assert concurrency["cancel-in-progress"] is False
    assert concurrency["group"].endswith("|| 'release' }}")  # push and schedule share it


def test_a_dispatch_run_has_a_group_of_its_own() -> None:
    """gh#1291: GitHub keeps ONE pending run per group, so a push run queued behind a
    pending `workflow_dispatch --version` run replaced it, silently. A dispatch run is
    keyed by its run id: nothing replaces it, and a dispatch that runs beside a push
    run is superseded loudly (it prints the re-dispatch), never dropped."""
    assert _workflow()["concurrency"]["group"] == (
        "${{ github.event_name == 'workflow_dispatch'"
        " && format('release-dispatch-{0}', github.run_id) || 'release' }}"
    )


def test_permissions_are_contents_and_issues_write_and_pull_requests_read() -> None:
    """`pull-requests: read` is for `fr release status` (exit-gates R21), which reads the
    merged PRs' gate labels with the workflow token, never the app's."""
    assert _workflow()["permissions"] == {
        "contents": "write",
        "issues": "write",
        "pull-requests": "read",
    }


def test_runs_daily_so_a_final_follows_the_last_gate_pass() -> None:
    """Exit-gates R20: a gate passes with no push to main, so a daily run cuts the final."""
    (entry,) = _on()["schedule"]
    assert re.fullmatch(r"\d+ \d+ \* \* \*", entry["cron"])


def test_release_status_reads_the_forge_with_the_workflow_token() -> None:
    """Only `prepare` computes what to release, so only it reads the merged PRs."""
    (run,) = _release_py_steps("prepare")
    assert run["env"]["FR_RELEASE_STATUS_TOKEN"] == "${{ github.token }}"


def test_checks_out_full_history_and_runs_release_py_with_a_token() -> None:
    for name in ("prepare", "collect", "test", "publish"):
        assert _checkout(name)["with"]["fetch-depth"] == 0, name
        assert any(_uses(s, "astral-sh/setup-uv") for s in _job_steps(name)), name
    for name in TOKEN_JOBS:
        (run,) = _release_py_steps(name)
        assert "GH_TOKEN" in run["env"], name
    # The dispatch input reaches the script through env, never spliced into the shell.
    for step in _steps():
        assert "${{" not in str(step.get("run", "")), step.get("name")


def test_header_states_both_token_modes_and_the_bypass_actor() -> None:
    header = " ".join(WORKFLOW.read_text().split("\non:", 1)[0].replace("#", " ").split())
    assert "GITHUB_TOKEN" in header
    assert "no CI" in header  # fallback mode: a GITHUB_TOKEN push triggers nothing
    assert "bypass actor" in header
    assert "FR_AUTOMATION_APP_ID" in header
    assert "no-op" in header  # app mode: CI runs and release.yml re-runs as a no-op


def _app_token_steps() -> list[dict[str, Any]]:
    return [s for s in _steps() if s.get("id") == "app-token"]


def test_app_token_step_is_conditional_and_pinned_to_a_sha() -> None:
    assert len(_app_token_steps()) == len(TOKEN_JOBS)
    for step in _app_token_steps():
        assert step["if"] == "vars.FR_AUTOMATION_APP_ID != ''"
        uses = step["uses"]
        assert uses.startswith("actions/create-github-app-token@")
        assert re.fullmatch(r"[0-9a-f]{40}", uses.split("@", 1)[1])
        assert step["with"]["app-id"] == "${{ vars.FR_AUTOMATION_APP_ID }}"
        assert step["with"]["private-key"] == "${{ secrets.FR_AUTOMATION_APP_KEY }}"


def test_app_token_is_scoped_to_this_repo_with_contents_and_issues_write_only() -> None:
    for step in _app_token_steps():
        w = step["with"]
        assert w["permission-contents"] == "write"
        assert w["permission-issues"] == "write"
        assert w["owner"] == "${{ github.repository_owner }}"
        assert w["repositories"] == "${{ github.event.repository.name }}"
        assert {k for k in w if k.startswith("permission-")} == {
            "permission-contents",
            "permission-issues",
        }


def test_checkout_persists_no_credential() -> None:
    """Every job's checkout, not the first one `next()` finds (spec 2026-11-01 §E2). The
    hold relay checks nothing out."""
    assert not any("checkout" in str(s.get("uses", "")) for s in _job_steps("hold-relay"))
    for name in _jobs():
        if name == "hold-relay":
            continue
        assert _checkout(name)["with"]["persist-credentials"] is False, name


def test_checkout_and_release_step_take_the_app_token_or_the_default() -> None:
    for name in TOKEN_JOBS:
        assert any(s.get("id") == "app-token" for s in _job_steps(name)), name
        assert _checkout(name)["with"]["token"] == APP_OR_DEFAULT, name
        (run,) = _release_py_steps(name)
        assert run["env"]["GH_TOKEN"] == APP_OR_DEFAULT, name


def test_the_staged_suite_jobs_hold_no_token(  # R9
) -> None:
    for name in CREDENTIAL_FREE_JOBS:
        job = _jobs()[name]
        assert job["permissions"] == {"contents": "read"}, name
        assert not any(_uses(s, "actions/create-github-app-token") for s in job["steps"]), name
        assert "token" not in _checkout(name)["with"], name
        envs = [job.get("env") or {}] + [s.get("env") or {} for s in job["steps"]]
        for env in envs:
            assert not {"GH_TOKEN", "FR_RELEASE_STATUS_TOKEN"} & set(env), name
            assert not any("token" in str(v) for v in env.values()), name


def test_the_release_is_a_six_job_graph_gated_on_prepares_cut() -> None:
    jobs = _jobs()
    # plus `hold-relay`, which runs only on a drained hold push and needs nothing
    assert set(jobs) == {"hold-relay", "prepare", "collect", "test", "split-check", "publish"}
    assert "needs" not in jobs["hold-relay"]
    assert jobs["test"]["strategy"]["matrix"]["shard"] == [1, 2, 3, 4, 5, 6]
    assert jobs["test"]["strategy"]["fail-fast"] is False
    assert {"collect", "test"} <= set(jobs["split-check"]["needs"])
    assert "split-check" in jobs["publish"]["needs"]
    cut = "needs.prepare.outputs.cut == 'true'"
    for name in ("collect", "test", "split-check", "publish"):
        assert "prepare" in jobs[name]["needs"], name
        assert jobs[name]["if"] == cut, name
    assert jobs["prepare"]["outputs"]["cut"] == "${{ steps.prepare.outputs.cut }}"


def test_every_release_job_has_its_timeout() -> None:  # R12
    expected = {
        "hold-relay": 5,
        "prepare": 10,
        "collect": 10,
        "test": 20,
        "split-check": 5,
        "publish": 10,
    }
    assert {n: j.get("timeout-minutes") for n, j in _jobs().items()} == expected


def test_the_suite_jobs_materialise_the_staged_commit_pinned_to_the_base() -> None:
    """R8: every shard tests exactly the staged commit, against the base it lands on."""
    for name in CREDENTIAL_FREE_JOBS:
        runs = " ".join(str(s["run"]) for s in _release_py_steps(name))
        assert "release.py materialise" in runs and "--pin-base" in runs, name
        assert _checkout(name)["with"]["ref"] == "${{ needs.prepare.outputs.base_sha }}", name
    test_runs = " ".join(str(s["run"]) for s in _release_py_steps("test"))
    assert "release.py test-shard" in test_runs and "--splits 6" in test_runs
    assert "release.py collect" in " ".join(str(s["run"]) for s in _release_py_steps("collect"))
    publish_runs = " ".join(str(s["run"]) for s in _release_py_steps("publish"))
    assert "release.py publish" in publish_runs and "--pin-base" not in publish_runs


def test_split_check_runs_over_the_releases_one_leg() -> None:
    runs = " ".join(str(s.get("run", "")) for s in _job_steps("split-check"))
    assert "scripts/split_check.py check" in runs
    assert "--collected" in runs


def test_prepare_restores_ci_durations_with_the_committed_fallback() -> None:
    steps = _job_steps("prepare")
    restore = next(s for s in steps if _uses(s, "actions/cache/restore"))
    assert restore["with"]["path"] == "cache/test-durations.json"
    assert restore["with"]["restore-keys"] == "test-durations-"
    assert not any(_uses(s, "actions/cache/save") for s in _steps())  # CI owns the cache
    runs = " ".join(str(s.get("run", "")) for s in steps)
    assert ".test_durations" in runs


def test_header_no_longer_claims_the_staged_diff_check_is_enough() -> None:
    """#854: the diff check proves which lines changed, not how the code behaves
    at the new number — 5.0.0 shipped refusing its own plans under that claim."""
    header = WORKFLOW.read_text().split("\non:", 1)[0]
    assert "safe only because release.py verifies the staged diff" not in " ".join(header.split())
    assert "tests the staged tree" in " ".join(header.replace("#", " ").split())


def test_the_release_job_has_a_budget_for_the_full_suite() -> None:
    budget = yaml.safe_load((REPO / ".github" / "ci-budget.yaml").read_text())
    assert (
        budget["workflows"]["release.yml"]["budget_seconds"] >= 600
    )  # spec 2026-11-01-ci-speed §3.E


def test_auto_tag_workflow_is_gone() -> None:
    assert not (REPO / ".github" / "workflows" / "auto-tag.yml").exists()


def test_p7_r4_header_says_the_status_token_is_the_write_capable_workflow_token() -> None:
    header = " ".join(WORKFLOW.read_text().split("\non:", 1)[0].replace("#", " ").split())
    assert "FR_RELEASE_STATUS_TOKEN is the workflow's github.token" in header
    assert "contents and issues write" in header
    assert "never fr or repo code" in header


def test_p3_r7_only_prepare_holds_the_status_token_and_the_dispatch_input() -> None:
    """Least privilege: `publish` pushes, tags and releases, so it holds GH_TOKEN and
    nothing else; the forge read and the override are `prepare`'s alone (the override
    reaches `publish` inside the plan)."""
    (prepare,) = _release_py_steps("prepare")
    assert {"GH_TOKEN", "FR_RELEASE_STATUS_TOKEN", "RELEASE_VERSION"} <= set(prepare["env"])
    (publish,) = _release_py_steps("publish")
    assert "GH_TOKEN" in publish["env"]
    assert not {"FR_RELEASE_STATUS_TOKEN", "RELEASE_VERSION"} & set(publish["env"])
    job = _jobs()["publish"]
    for env in [job.get("env") or {}] + [s.get("env") or {} for s in job["steps"]]:
        assert not {"FR_RELEASE_STATUS_TOKEN", "RELEASE_VERSION"} & set(env)


def test_p3_r3_collect_and_test_shard_are_handed_the_plan() -> None:
    """Both refuse unless HEAD is the plan's staged commit, so both must be given it."""
    for name, verb in (("collect", "release.py collect"), ("test", "release.py test-shard")):
        (step,) = [s for s in _release_py_steps(name) if verb in str(s["run"])]
        assert '--plan "${RELEASE_OUT}/release-plan.json"' in str(step["run"]), name
        assert step["env"]["RELEASE_OUT"] == "${{ runner.temp }}/release-out", name


def test_p3_r8_no_comment_claims_the_suite_jobs_run_with_no_token_at_all() -> None:
    text = " ".join(WORKFLOW.read_text().replace("#", " ").split())
    assert "no token at all" not in text
    assert "read-only GITHUB_TOKEN" in text


# --- release app hardening (spec 2026-11-21-release-app-hardening R1, R2) ---------

WORKFLOWS = REPO / ".github" / "workflows"


def _declares_release_environment(job: dict[str, Any]) -> bool:
    env = job.get("environment")
    name = env.get("name") if isinstance(env, dict) else env
    return name == "release"


def test_r1_exactly_prepare_and_publish_declare_the_release_environment() -> None:
    declaring = {name for name, job in _jobs().items() if _declares_release_environment(job)}
    assert declaring == {"prepare", "publish"}


def test_r1_no_other_workflow_job_declares_the_environment_or_names_the_key() -> None:
    offenders: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text())
        for name, job in (data.get("jobs") or {}).items():
            allowed = path.name == "release.yml" and name in {"prepare", "publish"}
            if allowed:
                continue
            if _declares_release_environment(job) or "FR_AUTOMATION_APP_KEY" in yaml.safe_dump(job):
                offenders.append(f"{path.name}:{name}")
    assert offenders == []


def test_r2_header_names_the_environment_secret_and_the_setup_script() -> None:
    header = " ".join(WORKFLOW.read_text().split("\non:", 1)[0].replace("#", " ").split())
    assert "release environment" in header
    assert "scripts/setup-release-app.sh" in header
    assert "configure-main-protection" not in header
