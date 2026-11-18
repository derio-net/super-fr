"""R11-R13: the rendered debt jobs hold the dedicated token only where it is used, and
carry each forge's credentials (spec 2026-11-18-consumer-delivery)."""

from __future__ import annotations

import re

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
    assert login["env"]["GITEA_SERVER_TOKEN"] == "${{ secrets.FR_DEBT_TOKEN || gitea.token }}"
    assert login["env"]["GITEA_SERVER_URL"] == "${{ gitea.server_url }}"
    assert "${{" not in login["run"]
    # tea 0.14.2 `login add` reads both from the environment: no token on the command line.
    assert login["run"] == "tea login add --name fr-ci"
    assert "--token" not in login["run"] and "TOKEN" not in login["run"]
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
    assert before.index(pin.assets["amd64"][1]) > before.index(check)
    assert job["before_script"][0].lstrip().startswith(check)  # first, before any install
    assert before.index(check) < before.index("sha256sum -c")
    assert before.index(check) < before.index("uv tool install")
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


def _gitlab_jobs(*, debt: bool, pages: bool) -> dict[str, dict]:
    doc = yaml.safe_load(render_workflow("gitlab-ci", debt=debt, pages=pages, fr_pin=PIN))
    return {k: v for k, v in doc.items() if isinstance(v, dict) and "stage" in v}


def _guarded(job: dict) -> bool:
    return "FR_DEBT_TOKEN" in "\n".join(job.get("before_script", []))


def test_the_gitlab_token_guard_is_on_the_debt_job_alone() -> None:
    """R13: only `technical-debt` needs FR_DEBT_TOKEN; the report and Pages jobs never
    stop over it (l-docs-accuracy-r1)."""
    for pages in (False, True):
        jobs = _gitlab_jobs(debt=False, pages=pages)
        assert ("pages" in jobs) is pages
        assert [n for n, j in jobs.items() if _guarded(j)] == []
        jobs = _gitlab_jobs(debt=True, pages=pages)
        assert [n for n, j in jobs.items() if _guarded(j)] == ["technical-debt"]


def test_every_gitlab_job_installs_the_pinned_uv_and_pipes_nothing_to_a_shell() -> None:
    """l-security-r3: no `curl … | sh`; the version and every sum come from UV_PIN."""
    from fr.acceptance.scaffold import UV_PIN

    jobs = _gitlab_jobs(debt=True, pages=True)
    assert set(jobs) == {"acceptance-report", "pages", "technical-debt"}
    for name, job in jobs.items():
        before = "\n".join(job["before_script"])
        assert not re.search(r"\|\s*(ba)?sh\b", before), name
        assert "astral.sh" not in before, name
        assert UV_PIN.version in before, name
        for url, sha in UV_PIN.assets.values():
            assert url in before and sha in before, name
            assert f"/releases/download/{UV_PIN.version}/" in url
        assert "sha256sum -c" in before, name
        assert before.index("sha256sum -c") < before.index("uv tool install"), name


def test_the_uv_pin_names_both_linux_architectures() -> None:
    from fr.acceptance.scaffold import UV_PIN

    assert UV_PIN.name == "uv"
    assert set(UV_PIN.assets) == {"amd64", "arm64"}
    assert UV_PIN.assets["amd64"][0].endswith("uv-x86_64-unknown-linux-gnu.tar.gz")
    assert UV_PIN.assets["arm64"][0].endswith("uv-aarch64-unknown-linux-gnu.tar.gz")
    for _url, sha in UV_PIN.assets.values():
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)


def test_gitea_tea_steps_keep_their_config_out_of_home() -> None:
    """l-security-r4: tea 0.14.2 writes its login under $XDG_CONFIG_HOME/tea; the steps
    that log in or read the login point it at the job's temp dir, which the runner
    removes, and a last always-step logs out."""
    job = _job("gitea-actions", "debt")
    scoped = "${{ runner.temp }}/fr-tea"
    tea_steps = [s for s in job["steps"] if s.get("run", "").startswith(("tea ", "fr debt"))]
    assert len(tea_steps) == 4  # login, debt issue, archive-pr, logout
    for step in tea_steps:
        assert step["env"]["XDG_CONFIG_HOME"] == scoped, step["name"]
    last = job["steps"][-1]
    assert last["if"] == "always()"
    assert "tea logout fr-ci" in last["run"]
