"""R11-R13: the rendered debt jobs hold the dedicated token only where it is used, and
carry each forge's credentials (spec 2026-11-18-consumer-delivery)."""

from __future__ import annotations

import yaml
from fr.acceptance.pin import FrPin
from fr.acceptance.scaffold import render_workflow
from fr.isolation.scaffold import HOST_CLI_PINS

PIN = FrPin("0123456789abcdef0123456789abcdef01234567", "v8.1.5")


def _job(ci: str, name: str) -> dict:
    doc = yaml.safe_load(render_workflow(ci, debt=True, fr_pin=PIN))
    return doc[name] if ci == "gitlab-ci" else doc["jobs"][name]


def _step(job: dict, name: str) -> dict:
    return next(s for s in job["steps"] if s.get("name", "").startswith(name))


def test_github_debt_checkout_keeps_no_credential_and_the_token_is_on_archive_pr_alone() -> None:
    job = _job("github-actions", "debt")
    checkout = job["steps"][0]
    assert checkout["with"]["persist-credentials"] is False
    assert "token" not in checkout["with"]
    holders = [s["name"] for s in job["steps"] if "FR_DEBT_TOKEN" in str(s.get("env", {}))]
    assert holders == ["Archive sweep PR (weekly)"]
    assert "FR_DEBT_TOKEN" not in str(checkout)


def test_gitea_debt_job_installs_the_pinned_tea_and_logs_in_through_env() -> None:
    job = _job("gitea-actions", "debt")
    assert job["steps"][0]["with"]["persist-credentials"] is False
    pin = HOST_CLI_PINS["gitea"]
    install = _step(job, "Install tea")["run"]
    assert pin.version in install
    for url, sha in pin.assets.values():
        assert url in install and sha in install
    login = _step(job, "Log in to tea")
    assert login["env"]["TEA_TOKEN"] == "${{ secrets.FR_DEBT_TOKEN || gitea.token }}"
    assert login["env"]["TEA_URL"] == "${{ gitea.server_url }}"
    assert "${{" not in login["run"]
    archive = _step(job, "Archive sweep PR")["env"]
    assert archive["FR_DEBT_TOKEN"] == "${{ secrets.FR_DEBT_TOKEN }}"
    assert archive["GITEA_TOKEN"] == "${{ gitea.token }}"
    names = [s.get("name", "") for s in job["steps"]]
    assert names.index("Install tea") < names.index("Log in to tea")
    assert names.index("Log in to tea") < names.index("Technical debt issue (weekly)")


def test_gitlab_debt_job_installs_glab_then_requires_the_masked_variable() -> None:
    job = _job("gitlab-ci", "technical-debt")
    assert job["variables"]["GITLAB_TOKEN"] == "$FR_DEBT_TOKEN"
    assert job["variables"]["GITLAB_HOST"] == "$CI_SERVER_HOST"
    before = "\n".join(job["before_script"])
    pin = HOST_CLI_PINS["gitlab"]
    assert pin.version in before
    for url, sha in pin.assets.values():
        assert url in before and sha in before
    check = '[ -n "$FR_DEBT_TOKEN" ] || {'
    assert check in before
    assert before.index(pin.assets["amd64"][1]) < before.index(check)
    assert "FR_DEBT_TOKEN" in before and "api scope" in before
    assert "exit 1" in before


def test_every_template_still_parses_with_every_job() -> None:
    for ci in ("github-actions", "gitea-actions", "gitlab-ci"):
        yaml.safe_load(
            render_workflow(
                ci,
                debt=True,
                pages=ci != "gitea-actions",
                comment=ci == "github-actions",
                fr_pin=PIN,
            )
        )
