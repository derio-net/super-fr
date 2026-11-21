# ruff: noqa: E501
"""`scripts/setup-release-app.sh` (spec 2026-11-21-release-app-hardening, R3-R14).

The script runs against a stateful stub `gh` and a stub `curl` on PATH; nothing here
touches a real repo or the network. The sandbox directory `<tmp>/stub/` is the stubs'
world, one JSON file per piece of state:

    installations.json    orgs/o/installations answer
    environment.json      the `release` environment (absent file = HTTP 404)
    policies.json         its deployment branch policies, [{id, name, type}]
    secrets_env.json      [{name}] of the environment's secrets
    secrets_repo.json     [{name}] of the repository's secrets
    variables.json        [{name, value}]
    release_yml.txt       main's release.yml text (absent file = HTTP 404)
    rulesets.json         full rulesets, each with id/name/source_type
    tags.json, runs.json  tags and the push-event Actions runs of the newest tag's sha
    app.json, app_status, inst_repos.json   what `curl` answers for GET /app,
                          its status, and GET /installation/repositories

The stubs apply every write to those files, so a second run sees the first, and log
every call: `calls.log` (gh argv), `curl_calls.log` (curl argv), `bodies.log` (write
bodies, which never hold a secret) and `auth.log` (the Authorization header curl read
from its `-H @<fd>`, which the real script never writes anywhere).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "setup-release-app.sh"
APP_ID = 424242
INST_ID = 55
SHA = "a" * 40
TOKEN = "ghs_STUBTOKEN0123456789abcdef"

GH_STUB = r"""#!/usr/bin/env bash
d="$STUB_DIR"
echo "$*" >> "$d/calls.log"
body() { local b; b="$(cat)"; echo "$1 $2 $(jq -c . <<<"$b")" >> "$d/bodies.log"; printf '%s' "$b"; }
nf() { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
case "$*" in
  "api orgs/o/installations") cat "$d/installations.json" ;;
  "api repos/o/r/environments/release") [ -f "$d/environment.json" ] && cat "$d/environment.json" || nf ;;
  "api repos/o/r/environments/release/deployment-branch-policies")
    jq '{total_count: length, branch_policies: .}' "$d/policies.json" ;;
  "api -X PUT repos/o/r/environments/release --input -")
    body PUT env | jq '{name: "release", can_admins_bypass,
      deployment_branch_policy,
      protection_rules: ([{type: "branch_policy"}]
        + (if .wait_timer > 0 then [{type: "wait_timer", wait_timer}] else [] end)
        + (if (.reviewers | length) > 0 then [{type: "required_reviewers", reviewers}] else [] end))}' \
      > "$d/environment.json"
    [ -f "$d/policies.json" ] || echo '[]' > "$d/policies.json" ;;
  "api -X POST repos/o/r/environments/release/deployment-branch-policies --input -")
    b="$(body POST policy)"
    jq --argjson b "$b" '. + [$b + {id: (length + 100)}]' "$d/policies.json" > "$d/p.tmp" && mv "$d/p.tmp" "$d/policies.json" ;;
  "api -X DELETE repos/o/r/environments/release/deployment-branch-policies/"*)
    s="$*"; id="${s##*/}"
    jq --argjson id "$id" 'map(select(.id != $id))' "$d/policies.json" > "$d/p.tmp" && mv "$d/p.tmp" "$d/policies.json" ;;
  "secret list --env release --repo o/r --json name") cat "$d/secrets_env.json" ;;
  "secret list --repo o/r --json name") cat "$d/secrets_repo.json" ;;
  "secret set FR_AUTOMATION_APP_KEY --env release --repo o/r")
    sha256sum_="$(cat | openssl dgst -sha256 | awk '{print $NF}')"
    echo "$sha256sum_" > "$d/env_secret.sha"
    jq '. + [{name: "FR_AUTOMATION_APP_KEY"}]' "$d/secrets_env.json" > "$d/s.tmp" && mv "$d/s.tmp" "$d/secrets_env.json" ;;
  "secret delete FR_AUTOMATION_APP_KEY --repo o/r") echo '[]' > "$d/secrets_repo.json" ;;
  "variable list --repo o/r --json name,value") cat "$d/variables.json" ;;
  "variable set FR_AUTOMATION_APP_ID --body "*" --repo o/r")
    s="$*"; v="${s#*--body }"; v="${v%% --repo*}"
    echo "[{\"name\":\"FR_AUTOMATION_APP_ID\",\"value\":\"$v\"}]" > "$d/variables.json" ;;
  "variable delete FR_AUTOMATION_APP_ID --repo o/r") echo '[]' > "$d/variables.json" ;;
  "api repos/o/r/contents/.github/workflows/release.yml?ref=main")
    [ -f "$d/release_yml.txt" ] || nf
    jq -n --arg c "$(openssl base64 -A < "$d/release_yml.txt")" '{content: $c}' ;;
  "api repos/o/r/rulesets") jq '[.[] | {id, name, source_type}]' "$d/rulesets.json" ;;
  "api repos/o/r/rulesets/"[0-9]*)
    s="$*"; id="${s##*/}"; jq --argjson id "$id" '.[] | select(.id == $id)' "$d/rulesets.json" ;;
  "api -X POST repos/o/r/rulesets --input -")
    b="$(body POST ruleset)"
    jq --argjson b "$b" '. + [$b + {id: (length + 200), source_type: "Repository"}]' "$d/rulesets.json" > "$d/r.tmp" && mv "$d/r.tmp" "$d/rulesets.json" ;;
  "api -X PUT repos/o/r/rulesets/"*" --input -")
    id="$(awk '{print $4}' <<<"$*")"; id="${id##*/}"
    b="$(body PUT "ruleset/$id")"
    jq --argjson b "$b" --argjson id "$id" \
      'map(if .id == $id then $b + {id: $id, source_type: "Repository"} else . end)' "$d/rulesets.json" > "$d/r.tmp" && mv "$d/r.tmp" "$d/rulesets.json" ;;
  "api --paginate repos/o/r/tags?per_page=100") cat "$d/tags.json" ;;
  "api repos/o/r/actions/runs?head_sha=$STUB_SHA&event=push") cat "$d/runs.json" ;;
  *) echo "stub gh: unexpected call: $*" >&2; exit 99 ;;
esac
"""

CURL_STUB = r"""#!/usr/bin/env bash
d="$STUB_DIR"
echo "$*" >> "$d/curl_calls.log"
out="" method=GET url="" hf=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -w) shift 2 ;;
    -X) method="$2"; shift 2 ;;
    -H) case "$2" in @*) [ -z "$hf" ] && hf="${2#@}" ;; esac; shift 2 ;;
    -s | -S | -sS) shift ;;
    *) url="$1"; shift ;;
  esac
done
auth="$(cat "$hf" 2>/dev/null | tr -d '\r\n')"
echo "$method $url $auth" >> "$d/auth.log"
code=200
case "$method $url" in
  "GET https://api.github.com/app")
    code="$(cat "$d/app_status" 2>/dev/null || echo 200)"
    if [ "$code" = 200 ]; then cp "$d/app.json" "$out"; else echo '{"message":"BODYSECRET"}' > "$out"; fi ;;
  "POST https://api.github.com/app/installations/55/access_tokens")
    code=201; echo '{"token":"ghs_STUBTOKEN0123456789abcdef"}' > "$out" ;;
  "GET https://api.github.com/installation/repositories")
    if [ "$auth" = "Authorization: Bearer ghs_STUBTOKEN0123456789abcdef" ]; then
      cp "$d/inst_repos.json" "$out"
    else code=401; echo '{"message":"BODYSECRET"}' > "$out"; fi ;;
  "DELETE https://api.github.com/installation/token")
    code=204; : > "$out"; echo revoked >> "$d/revoked.log" ;;
  *) echo "stub curl: unexpected call: $method $url" >&2; exit 99 ;;
esac
printf '%s' "$code"
"""

WRITE_RE = re.compile(r"^(api -X (PUT|POST|DELETE)|secret (set|delete)|variable (set|delete))")


@pytest.fixture(scope="session")
def key_pem(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("key")
    pem = d / "app.pem"
    subprocess.run(["openssl", "genrsa", "-out", str(pem), "2048"], check=True, capture_output=True)
    return pem


def _j(sandbox: Path, name: str, obj: Any) -> None:
    (sandbox / "stub" / name).write_text(json.dumps(obj))


def _rm(sandbox: Path, name: str) -> None:
    (sandbox / "stub" / name).unlink(missing_ok=True)


def _read(sandbox: Path, name: str) -> Any:
    return json.loads((sandbox / "stub" / name).read_text())


GOOD_PERMS = {"contents": "write", "issues": "write", "metadata": "read"}


def installation(**over: Any) -> dict[str, Any]:
    inst = {
        "id": INST_ID,
        "app_id": APP_ID,
        "app_slug": "derio-fr-automation",
        "repository_selection": "selected",
        "permissions": dict(GOOD_PERMS),
    }
    inst.update(over)
    return {"installations": [{"id": 1, "app_id": 1, "app_slug": "other"}, inst]}


def good_env() -> dict[str, Any]:
    return {
        "name": "release",
        "can_admins_bypass": False,
        "protection_rules": [{"type": "branch_policy"}],
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
    }


APP_BYPASS = {"actor_id": APP_ID, "actor_type": "Integration", "bypass_mode": "always"}
DEFAULT_COND = {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}


def protect_main(*, bypass: bool = False, rsc: bool = False) -> dict[str, Any]:
    rules: list[dict[str, Any]] = [{"type": "deletion"}, {"type": "non_fast_forward"}]
    if rsc:
        rules.append(
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [{"context": "ci-ok"}],
                },
            }
        )
    return {
        "id": 7,
        "name": "protect main",
        "target": "branch",
        "enforcement": "active",
        "source_type": "Repository",
        "node_id": "RRS_abc",
        "conditions": DEFAULT_COND,
        "rules": rules,
        "bypass_actors": [dict(APP_BYPASS)] if bypass else [],
    }


def tag_ruleset() -> dict[str, Any]:
    return {
        "id": 8,
        "name": "protect release tags",
        "target": "tag",
        "enforcement": "active",
        "source_type": "Repository",
        "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "update"}],
        "bypass_actors": [],
    }


def require_ruleset() -> dict[str, Any]:
    return {
        "id": 9,
        "name": "require ci-ok",
        "target": "branch",
        "enforcement": "active",
        "source_type": "Repository",
        "conditions": DEFAULT_COND,
        "rules": protect_main(rsc=True)["rules"][2:],
        "bypass_actors": [dict(APP_BYPASS)],
    }


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """The finished setup: every step is `ok`. Tests break the one thing they probe."""
    d = tmp_path / "stub"
    d.mkdir()
    (tmp_path / "tmp").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("gh", GH_STUB), ("curl", CURL_STUB)):
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod(0o755)
    _j(tmp_path, "installations.json", installation())
    _j(tmp_path, "environment.json", good_env())
    _j(tmp_path, "policies.json", [{"id": 1, "name": "main", "type": "branch"}])
    _j(tmp_path, "secrets_env.json", [{"name": "FR_AUTOMATION_APP_KEY"}])
    _j(tmp_path, "secrets_repo.json", [])
    _j(tmp_path, "variables.json", [{"name": "FR_AUTOMATION_APP_ID", "value": str(APP_ID)}])
    (d / "release_yml.txt").write_text(
        "jobs:\n  prepare:\n    environment: release\n    runs-on: x\n"
    )
    _j(tmp_path, "rulesets.json", [protect_main(), tag_ruleset(), require_ruleset()])
    _j(
        tmp_path,
        "tags.json",
        [
            {"name": "v5.9.0", "commit": {"sha": "b" * 40}},
            {"name": "v5.21.0", "commit": {"sha": SHA}},
        ],
    )
    _j(
        tmp_path,
        "runs.json",
        {"workflow_runs": [{"triggering_actor": {"login": "derio-fr-automation[bot]"}}]},
    )
    _j(tmp_path, "app.json", {"id": APP_ID, "slug": "derio-fr-automation"})
    _j(tmp_path, "inst_repos.json", {"repositories": [{"full_name": "o/r"}]})
    return tmp_path


def half_done(sandbox: Path) -> None:
    """The live state of 2026-11-20: variable set, no env, no key, combined ruleset with the bypass."""
    _rm(sandbox, "environment.json")
    _rm(sandbox, "policies.json")
    _j(sandbox, "secrets_env.json", [])
    _j(sandbox, "rulesets.json", [protect_main(bypass=True)])
    _rm(sandbox, "release_yml.txt")


def run(
    sandbox: Path, *args: str, stdin: str = "", repo: str | None = "o/r"
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{sandbox / 'bin'}:{os.environ['PATH']}",
        "STUB_DIR": str(sandbox / "stub"),
        "STUB_SHA": SHA,
        "HOME": str(sandbox),
        "TMPDIR": str(sandbox / "tmp"),
    }
    cmd = ["bash", str(SCRIPT)]
    if repo:
        cmd += ["--repo", repo]
    return subprocess.run(
        cmd + list(args), input=stdin, capture_output=True, text=True, env=env, check=False
    )


def calls(sandbox: Path) -> list[str]:
    p = sandbox / "stub" / "calls.log"
    return p.read_text().splitlines() if p.exists() else []


def writes(sandbox: Path) -> list[str]:
    return [c for c in calls(sandbox) if WRITE_RE.match(c)]


def answers(*lines: str) -> str:
    return "".join(f"{x}\n" for x in lines)


# --- the frame: arguments, syntax, confirmation, dry-run (R3, R4, R5) ---


def test_bad_arguments_exit_2_with_usage(sandbox: Path) -> None:
    for args in (["--nope"], ["--repo"], ["stage"]):
        r = run(sandbox, *args, repo=None)
        assert r.returncode == 2 and "usage:" in r.stderr, args
    assert run(sandbox, "--repo", "noslash", repo=None).returncode == 2
    assert not writes(sandbox)


def test_the_script_is_valid_shell_and_never_traces() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0
    if shutil.which("shellcheck"):
        assert subprocess.run(["shellcheck", str(SCRIPT)], check=False).returncode == 0
    text = SCRIPT.read_text()
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text
    assert not re.search(r"^\s*set\s+-\w*x", text, re.M)
    assert os.access(SCRIPT, os.X_OK)


def test_the_old_script_and_its_tests_are_gone() -> None:
    assert not (REPO / "scripts" / "configure-main-protection.sh").exists()
    assert not (REPO / "tests" / "unit" / "test_configure_main_protection.py").exists()


def test_a_finished_setup_prints_ok_for_every_step_and_writes_nothing(sandbox: Path) -> None:
    r = run(sandbox)
    assert r.returncode == 0, r.stderr
    assert not writes(sandbox)
    for step in ("1 app", "2 env", "3 key", "4 variable", "5 history", "6 tags", "7 require"):
        section = r.stdout.split(f"== {step} ==")[1].split("==")[0]
        assert "ok:" in section, (step, section)


def test_a_declined_step_write_stops_the_script_with_no_later_write(sandbox: Path) -> None:
    _rm(sandbox, "environment.json")
    _rm(sandbox, "policies.json")
    _j(sandbox, "rulesets.json", [])  # later steps would also write
    r = run(sandbox, stdin=answers("n"))
    assert r.returncode != 0 and "declined" in r.stderr
    assert writes(sandbox) == []


def test_a_declined_offer_continues(sandbox: Path) -> None:
    _j(sandbox, "secrets_repo.json", [{"name": "FR_AUTOMATION_APP_KEY"}])
    r = run(sandbox, stdin=answers("n"))
    assert r.returncode == 0, r.stderr
    assert "leak path" in r.stdout and "== 7 require ==" in r.stdout
    assert writes(sandbox) == []


def test_dry_run_from_the_half_done_state_prints_every_pending_step_in_order(sandbox: Path) -> None:
    half_done(sandbox)
    r = run(sandbox, "--dry-run")
    assert r.returncode == 0, r.stderr
    would = [line for line in r.stdout.splitlines() if line.startswith("would")]
    joined = "\n".join(would)
    order = [
        "would offer: unset FR_AUTOMATION_APP_ID",
        "would: PUT repos/o/r/environments/release",
        "would: POST repos/o/r/environments/release/deployment-branch-policies",
        "would: read the key path",
        "would: PUT repos/o/r/rulesets/7",
        "would: POST repos/o/r/rulesets",
    ]
    pos = [joined.find(x) for x in order]
    assert all(p >= 0 for p in pos), joined
    assert pos == sorted(pos), joined
    assert writes(sandbox) == []
    assert not (sandbox / "stub" / "curl_calls.log").exists()


# --- app installation (R6) ---


def test_the_app_step_passes_on_selected_and_exact_permissions(sandbox: Path) -> None:
    r = run(sandbox)
    assert "ok: derio-fr-automation installed" in r.stdout
    assert not any("user/installations" in c for c in calls(sandbox))


@pytest.mark.parametrize(
    "over",
    [
        {"permissions": {**GOOD_PERMS, "actions": "write"}},
        {"permissions": {**GOOD_PERMS, "contents": "read"}},
        {"repository_selection": "all"},
    ],
)
def test_the_app_step_refuses_a_wrong_installation_and_names_the_web_ui(
    sandbox: Path, over: dict[str, Any]
) -> None:
    _j(sandbox, "installations.json", installation(**over))
    r = run(sandbox)
    assert r.returncode != 0 and "web UI" in r.stderr
    assert writes(sandbox) == []
    assert not any("user/installations" in c for c in calls(sandbox))


def test_the_app_step_refuses_a_missing_installation(sandbox: Path) -> None:
    _j(
        sandbox,
        "installations.json",
        {"installations": [{"id": 1, "app_id": 1, "app_slug": "other"}]},
    )
    r = run(sandbox)
    assert r.returncode != 0 and "not installed" in r.stderr


# --- environment (R2, R7) ---


def test_an_absent_environment_is_created_then_given_the_main_policy(sandbox: Path) -> None:
    _rm(sandbox, "environment.json")
    _rm(sandbox, "policies.json")
    _j(sandbox, "variables.json", [])
    r = run(sandbox, stdin=answers("y", "y"))  # then the key step reads an empty path and stops
    assert "no such file" in r.stderr
    w = writes(sandbox)[:2]
    assert w == [
        "api -X PUT repos/o/r/environments/release --input -",
        "api -X POST repos/o/r/environments/release/deployment-branch-policies --input -",
    ]
    bodies = (sandbox / "stub" / "bodies.log").read_text().splitlines()
    put = json.loads(bodies[0].split(" ", 2)[2])
    assert put == {
        "wait_timer": 0,
        "reviewers": [],
        "can_admins_bypass": False,
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
    }
    assert json.loads(bodies[1].split(" ", 2)[2]) == {"name": "main", "type": "branch"}


def test_an_environment_with_admin_bypass_and_reviewers_is_corrected(sandbox: Path) -> None:
    env = good_env()
    env["can_admins_bypass"] = True
    env["protection_rules"].append({"type": "required_reviewers", "reviewers": [{"type": "User"}]})
    _j(sandbox, "environment.json", env)
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == ["api -X PUT repos/o/r/environments/release --input -"]
    fixed = _read(sandbox, "environment.json")
    assert fixed["can_admins_bypass"] is False
    assert all(p["type"] != "required_reviewers" for p in fixed["protection_rules"])


@pytest.mark.parametrize(
    "extra", [{"name": "dev", "type": "branch"}, {"name": "v*", "type": "tag"}]
)
def test_an_extra_policy_is_deleted(sandbox: Path, extra: dict[str, str]) -> None:
    _j(sandbox, "policies.json", [{"id": 1, "name": "main", "type": "branch"}, {"id": 2, **extra}])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == [
        "api -X DELETE repos/o/r/environments/release/deployment-branch-policies/2"
    ]
    assert _read(sandbox, "policies.json") == [{"id": 1, "name": "main", "type": "branch"}]


def test_a_missing_main_policy_is_added(sandbox: Path) -> None:
    _j(sandbox, "policies.json", [])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == [
        "api -X POST repos/o/r/environments/release/deployment-branch-policies --input -"
    ]


# --- the key (R8, R9, R10) ---


def _no_secret_state(sandbox: Path) -> None:
    _j(sandbox, "secrets_env.json", [])
    _j(sandbox, "variables.json", [])
    (sandbox / "stub" / "release_yml.txt").write_text("jobs: {}\n")  # variable waits: no prompt


def _everything_logged(sandbox: Path, r: subprocess.CompletedProcess[str]) -> str:
    parts = [r.stdout, r.stderr]
    for name in ("calls.log", "curl_calls.log", "bodies.log"):
        p = sandbox / "stub" / name
        if p.exists():
            parts.append(p.read_text())
    return "\n".join(parts)


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def test_the_key_is_proved_then_stored_from_stdin_and_never_leaks(
    sandbox: Path, key_pem: Path
) -> None:
    _no_secret_state(sandbox)
    key = sandbox / "app.pem"
    shutil.copy(key_pem, key)
    r = run(sandbox, stdin=answers(str(key), "y", "n"))
    assert r.returncode == 0, r.stderr
    # stored as the environment secret, the file untouched (offer declined), digest of the bytes
    assert "secret set FR_AUTOMATION_APP_KEY --env release --repo o/r" in calls(sandbox)
    assert key.exists()
    want = hashlib.sha256(key.read_bytes()).hexdigest()
    assert (sandbox / "stub" / "env_secret.sha").read_text().strip() == want
    # the JWT: signed by the key, iss the app id, at most 10 minutes
    auth = [
        line
        for line in (sandbox / "stub" / "auth.log").read_text().splitlines()
        if line.startswith("GET https://api.github.com/app ")
    ]
    assert len(auth) == 1
    jwt = auth[0].split("Bearer ", 1)[1]
    h, p, s = jwt.split(".")
    claims = json.loads(_b64url_decode(p))
    assert str(claims["iss"]) == str(APP_ID) and claims["exp"] - claims["iat"] <= 600
    assert json.loads(_b64url_decode(h)) == {"alg": "RS256", "typ": "JWT"}
    pub = sandbox / "pub.pem"
    subprocess.run(
        ["openssl", "rsa", "-in", str(key), "-pubout", "-out", str(pub)],
        check=True,
        capture_output=True,
    )
    (sandbox / "sig.bin").write_bytes(_b64url_decode(s))
    (sandbox / "data.txt").write_text(f"{h}.{p}")
    v = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(pub),
            "-signature",
            str(sandbox / "sig.bin"),
            str(sandbox / "data.txt"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert v.returncode == 0, v.stdout + v.stderr
    # the token was minted with the JWT, used for the repo list, and revoked
    assert (sandbox / "stub" / "revoked.log").read_text().strip() == "revoked"
    repo_call = [
        x
        for x in (sandbox / "stub" / "auth.log").read_text().splitlines()
        if "installation/repositories" in x
    ]
    assert repo_call and TOKEN in repo_call[0]
    # the leak test: no PEM line, no JWT segment, no token in any output, log or argv
    seen = _everything_logged(sandbox, r)
    for line in key.read_text().splitlines()[1:-1]:
        assert line not in seen
    assert "eyJ" not in seen and TOKEN not in seen and jwt not in seen
    assert list((sandbox / "tmp").iterdir()) == []


def test_the_key_file_is_deleted_when_the_offer_is_accepted(sandbox: Path, key_pem: Path) -> None:
    _no_secret_state(sandbox)
    key = sandbox / "app.pem"
    shutil.copy(key_pem, key)
    r = run(sandbox, stdin=answers(str(key), "y", "y"))
    assert r.returncode == 0, r.stderr
    assert not key.exists()


def test_a_non_pem_file_is_refused_before_any_curl_call(sandbox: Path) -> None:
    _no_secret_state(sandbox)
    junk = sandbox / "junk.pem"
    junk.write_text("not a key\n")
    r = run(sandbox, stdin=answers(str(junk)))
    assert r.returncode != 0 and "not a PEM private key" in r.stderr
    assert not (sandbox / "stub" / "curl_calls.log").exists()
    assert writes(sandbox) == []


def test_no_curl_argv_holds_a_credential(sandbox: Path, key_pem: Path) -> None:
    _no_secret_state(sandbox)
    run(sandbox, stdin=answers(str(key_pem), "y", "n"))
    argv = (sandbox / "stub" / "curl_calls.log").read_text()
    assert "Authorization" not in argv and "eyJ" not in argv and TOKEN not in argv
    assert "-H @/dev/fd/" in argv


@pytest.mark.parametrize("status", ["401", "404"])
def test_an_http_error_from_get_app_refuses_and_stores_nothing(
    sandbox: Path, key_pem: Path, status: str
) -> None:
    _no_secret_state(sandbox)
    (sandbox / "stub" / "app_status").write_text(status)
    r = run(sandbox, stdin=answers(str(key_pem), "y"))
    assert r.returncode != 0 and f"HTTP {status}" in r.stderr
    assert "BODYSECRET" not in r.stdout + r.stderr
    assert not any(c.startswith("secret set") for c in calls(sandbox))


def test_a_key_of_another_app_refuses_and_stores_nothing(sandbox: Path, key_pem: Path) -> None:
    _no_secret_state(sandbox)
    _j(sandbox, "app.json", {"id": 999, "slug": "someone-else"})
    r = run(sandbox, stdin=answers(str(key_pem), "y"))
    assert r.returncode != 0 and "different app" in r.stderr
    assert not any(c.startswith("secret set") for c in calls(sandbox))
    assert not (sandbox / "stub" / "revoked.log").exists()  # no token was minted


@pytest.mark.parametrize(
    "repos",
    [
        [{"full_name": "o/other"}],
        [{"full_name": "o/r"}, {"full_name": "o/second"}],
    ],
)
def test_a_wrong_repository_list_refuses_stores_nothing_and_revokes(
    sandbox: Path, key_pem: Path, repos: list[dict[str, str]]
) -> None:
    _no_secret_state(sandbox)
    _j(sandbox, "inst_repos.json", {"repositories": repos})
    r = run(sandbox, stdin=answers(str(key_pem), "y"))
    assert r.returncode != 0 and "not only o/r" in r.stderr
    assert not any(c.startswith("secret set") for c in calls(sandbox))
    assert (sandbox / "stub" / "revoked.log").read_text().strip() == "revoked"
    assert TOKEN not in r.stdout + r.stderr
    assert list((sandbox / "tmp").iterdir()) == []


def test_a_declined_secret_write_revokes_the_token_and_stops(sandbox: Path, key_pem: Path) -> None:
    _no_secret_state(sandbox)
    r = run(sandbox, stdin=answers(str(key_pem), "n"))
    assert r.returncode != 0
    assert not any(c.startswith("secret set") for c in calls(sandbox))
    assert (sandbox / "stub" / "revoked.log").exists()


def test_an_existing_environment_secret_is_ok_and_asks_to_confirm_the_installation(
    sandbox: Path,
) -> None:
    r = run(sandbox)
    assert "ok: environment secret FR_AUTOMATION_APP_KEY exists" in r.stdout
    assert f"https://github.com/organizations/o/settings/installations/{INST_ID}" in r.stdout
    assert not (sandbox / "stub" / "curl_calls.log").exists()


def test_rotate_key_replaces_the_secret_and_proves_the_repo_list(
    sandbox: Path, key_pem: Path
) -> None:
    r = run(sandbox, "--rotate-key", stdin=answers(str(key_pem), "y", "n"))
    assert r.returncode == 0, r.stderr
    assert "secret set FR_AUTOMATION_APP_KEY --env release --repo o/r" in calls(sandbox)
    assert (sandbox / "stub" / "revoked.log").exists()


def test_a_repository_level_secret_is_reported_and_offered_for_deletion(sandbox: Path) -> None:
    _j(sandbox, "secrets_repo.json", [{"name": "FR_AUTOMATION_APP_KEY"}])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert "secret delete FR_AUTOMATION_APP_KEY --repo o/r" in calls(sandbox)
    assert _read(sandbox, "secrets_repo.json") == []


def test_a_repository_secret_is_not_offered_before_the_environment_secret_exists(
    sandbox: Path,
) -> None:
    _no_secret_state(sandbox)
    _j(sandbox, "secrets_repo.json", [{"name": "FR_AUTOMATION_APP_KEY"}])
    r = run(sandbox, "--dry-run")
    assert "leak path" in r.stdout  # dry-run assumes the env secret is stored first
    r2 = run(sandbox, stdin=answers("/nonexistent"))
    assert "leak path" not in r2.stdout


# --- the variable and the half-done state (R11) ---


def test_the_half_done_state_is_named_and_the_unset_is_offered(sandbox: Path) -> None:
    _j(sandbox, "secrets_env.json", [])
    r = run(sandbox, "--dry-run")
    assert (
        "half-done" in r.stdout
        and "releases fail" in r.stdout.lower()
        or "Releases fail" in r.stdout
    )
    assert "would offer: unset FR_AUTOMATION_APP_ID" in r.stdout


def test_accepting_the_unset_offer_deletes_the_variable(sandbox: Path, key_pem: Path) -> None:
    _j(sandbox, "secrets_env.json", [])
    (sandbox / "stub" / "release_yml.txt").write_text("jobs: {}\n")
    r = run(sandbox, stdin=answers("y", str(key_pem), "y", "n"))
    assert r.returncode == 0, r.stderr
    assert "variable delete FR_AUTOMATION_APP_ID --repo o/r" in calls(sandbox)
    assert _read(sandbox, "variables.json") == []


def test_declining_the_unset_offer_keeps_the_variable_and_continues(
    sandbox: Path, key_pem: Path
) -> None:
    _j(sandbox, "secrets_env.json", [])
    r = run(sandbox, stdin=answers("n", str(key_pem), "y", "n"))
    assert r.returncode == 0, r.stderr
    assert not any(c.startswith("variable delete") for c in calls(sandbox))
    assert "secret set FR_AUTOMATION_APP_KEY --env release --repo o/r" in calls(sandbox)


def test_the_variable_is_never_set_without_the_environment_secret(sandbox: Path) -> None:
    _no_secret_state(sandbox)
    r = run(sandbox, stdin=answers(""))  # the key step reads an empty path and stops
    assert r.returncode != 0
    assert not any(c.startswith("variable set") for c in calls(sandbox))


def test_the_variable_waits_while_mains_release_yml_lacks_the_environment(sandbox: Path) -> None:
    _j(sandbox, "variables.json", [])
    (sandbox / "stub" / "release_yml.txt").write_text("jobs:\n  prepare:\n    runs-on: x\n")
    r = run(sandbox)
    assert r.returncode == 0, r.stderr
    assert "waits: main's release.yml does not declare 'environment: release'" in r.stdout
    assert writes(sandbox) == []


def test_the_variable_is_set_to_the_installations_app_id_once_both_hold(sandbox: Path) -> None:
    _j(sandbox, "variables.json", [])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == [f"variable set FR_AUTOMATION_APP_ID --body {APP_ID} --repo o/r"]
    assert _read(sandbox, "variables.json")[0]["value"] == str(APP_ID)


def test_a_variable_with_the_right_value_is_ok(sandbox: Path) -> None:
    r = run(sandbox)
    assert f"ok: FR_AUTOMATION_APP_ID is {APP_ID}" in r.stdout


# --- the rulesets (R12, R13, R14) ---


def _puts_and_posts(sandbox: Path) -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for line in (sandbox / "stub" / "bodies.log").read_text().splitlines():
        method, path, body = line.split(" ", 2)
        out.append((method, path, json.loads(body)))
    return out


def test_the_history_step_strips_the_bypass_in_place_and_keeps_every_rule(sandbox: Path) -> None:
    main = protect_main(bypass=True)
    main["rules"].append({"type": "required_linear_history"})
    _j(sandbox, "rulesets.json", [main, tag_ruleset(), require_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == ["api -X PUT repos/o/r/rulesets/7 --input -"]
    ((method, path, body),) = _puts_and_posts(sandbox)
    assert (method, path) == ("PUT", "ruleset/7")
    assert body["bypass_actors"] == []
    assert {x["type"] for x in body["rules"]} == {
        "deletion",
        "non_fast_forward",
        "required_linear_history",
    }
    assert body["name"] == "protect main" and body["conditions"] == DEFAULT_COND
    assert _read(sandbox, "rulesets.json")[0]["id"] == 7


def test_a_missing_protect_main_is_created_with_both_rules(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [tag_ruleset(), require_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    ((method, _, body),) = _puts_and_posts(sandbox)
    assert method == "POST"
    assert [x["type"] for x in body["rules"]] == ["deletion", "non_fast_forward"]
    assert body["bypass_actors"] == []


def test_an_org_ruleset_of_the_same_name_is_ignored(sandbox: Path) -> None:
    org = protect_main(bypass=True)
    org["source_type"] = "Organization"
    org["id"] = 70
    _j(sandbox, "rulesets.json", [org, tag_ruleset(), require_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    ((method, _, _body),) = _puts_and_posts(sandbox)
    assert method == "POST"


def test_a_missing_rule_is_added_never_dropped(sandbox: Path) -> None:
    main = protect_main()
    main["rules"] = [{"type": "deletion"}]
    _j(sandbox, "rulesets.json", [main, tag_ruleset(), require_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    ((_, _, body),) = _puts_and_posts(sandbox)
    assert {x["type"] for x in body["rules"]} == {"deletion", "non_fast_forward"}


def test_the_old_ci_ok_rule_defers_the_history_step_and_keeps_the_bypass(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(bypass=True, rsc=True), tag_ruleset()])
    # require does the move once a release was pushed by the app; here it is not, so nothing is written
    _j(sandbox, "runs.json", {"workflow_runs": []})
    r = run(sandbox)
    assert r.returncode == 0, r.stderr
    assert "deferred" in r.stdout and "require step moves both" in r.stdout
    assert writes(sandbox) == []


def test_the_tag_ruleset_is_created_without_a_bypass(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(), require_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    ((method, _, body),) = _puts_and_posts(sandbox)
    assert method == "POST"
    assert body["target"] == "tag" and body["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]
    assert [x["type"] for x in body["rules"]] == ["deletion", "update"]
    assert body["bypass_actors"] == []


def test_a_present_correct_tag_ruleset_is_ok(sandbox: Path) -> None:
    r = run(sandbox)
    assert "ok: 'protect release tags'" in r.stdout


def test_require_never_runs_after_a_declined_history_write(sandbox: Path) -> None:
    # a bypass left on "protect main" is the history step's to remove; declining stops the script
    _j(sandbox, "rulesets.json", [protect_main(bypass=True), tag_ruleset()])
    r = run(sandbox, stdin=answers("n"))
    assert r.returncode != 0
    assert not any(c.startswith("api -X POST repos/o/r/rulesets") for c in calls(sandbox))


def test_require_waits_without_an_app_pushed_release_and_exits_0(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(), tag_ruleset()])
    _j(
        sandbox,
        "runs.json",
        {"workflow_runs": [{"triggering_actor": {"login": "github-actions[bot]"}}]},
    )
    r = run(sandbox)
    assert r.returncode == 0, r.stderr
    assert "waits:" in r.stdout and "not pushed by the app" in r.stdout
    assert writes(sandbox) == []


def test_the_newest_tag_is_found_across_pages(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(), tag_ruleset()])
    # two pages concatenated, as `gh api --paginate` prints them
    (sandbox / "stub" / "tags.json").write_text(
        json.dumps([{"name": "v5.9.0", "commit": {"sha": "b" * 40}}])
        + json.dumps([{"name": "v5.21.0", "commit": {"sha": SHA}}])
    )
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert any(c == "api -X POST repos/o/r/rulesets --input -" for c in calls(sandbox))


def test_force_skips_only_the_release_check(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(), tag_ruleset()])
    _j(sandbox, "runs.json", {"workflow_runs": []})
    r = run(sandbox, "--force", stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    assert any(c == "api -X POST repos/o/r/rulesets --input -" for c in calls(sandbox))
    # ...never the secret or variable
    _j(sandbox, "rulesets.json", [protect_main(), tag_ruleset()])
    _j(sandbox, "secrets_env.json", [])
    r2 = run(sandbox, "--force", stdin=answers("n"))
    assert r2.returncode != 0


def test_require_creates_the_ruleset_with_the_app_as_its_only_bypass(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(), tag_ruleset()])
    r = run(sandbox, stdin=answers("y"))
    assert r.returncode == 0, r.stderr
    ((method, _, body),) = _puts_and_posts(sandbox)
    assert method == "POST" and body["name"] == "require ci-ok"
    assert body["bypass_actors"] == [APP_BYPASS]
    (rule,) = body["rules"]
    assert rule["type"] == "required_status_checks"
    assert rule["parameters"]["strict_required_status_checks_policy"] is True
    assert rule["parameters"]["required_status_checks"] == [{"context": "ci-ok"}]
    assert _read(sandbox, "rulesets.json")[-1]["name"] == "require ci-ok"


def test_in_the_deferred_state_require_comes_first_then_one_put_removes_both(sandbox: Path) -> None:
    _j(sandbox, "rulesets.json", [protect_main(bypass=True, rsc=True), tag_ruleset()])
    r = run(sandbox, stdin=answers("y", "y"))
    assert r.returncode == 0, r.stderr
    assert writes(sandbox) == [
        "api -X POST repos/o/r/rulesets --input -",
        "api -X PUT repos/o/r/rulesets/7 --input -",
    ]
    _, put = _puts_and_posts(sandbox)
    body = put[2]
    assert body["bypass_actors"] == []
    assert {x["type"] for x in body["rules"]} == {"deletion", "non_fast_forward"}


# --- idempotence and the end-to-end order (R4, R5) ---


def test_the_end_to_end_order_and_an_idempotent_rerun(sandbox: Path, key_pem: Path) -> None:
    # a fresh repo: nothing set up, main's release.yml already declares the environment
    _rm(sandbox, "environment.json")
    _rm(sandbox, "policies.json")
    _j(sandbox, "secrets_env.json", [])
    _j(sandbox, "variables.json", [])
    _j(sandbox, "rulesets.json", [protect_main(bypass=True)])
    first = run(
        sandbox,
        stdin=answers(
            "y",  # PUT environment
            "y",  # POST main policy
            str(key_pem),
            "y",  # gh secret set
            "n",  # keep the file
            "y",  # variable set
            "y",  # history PUT
            "y",  # tags POST
            "y",  # require POST
        ),
    )
    assert first.returncode == 0, first.stderr
    w = writes(sandbox)
    idx = {
        "env": w.index("api -X PUT repos/o/r/environments/release --input -"),
        "secret": w.index("secret set FR_AUTOMATION_APP_KEY --env release --repo o/r"),
        "variable": w.index(f"variable set FR_AUTOMATION_APP_ID --body {APP_ID} --repo o/r"),
        "history": w.index("api -X PUT repos/o/r/rulesets/7 --input -"),
        "tags": w.index("api -X POST repos/o/r/rulesets --input -"),
    }
    posts = [i for i, c in enumerate(w) if c == "api -X POST repos/o/r/rulesets --input -"]
    assert idx["env"] < idx["secret"] < idx["variable"] < idx["history"] < posts[0] < posts[1]
    before = len(calls(sandbox))
    second = run(sandbox)  # no stdin at all
    assert second.returncode == 0, second.stderr
    assert not [c for c in calls(sandbox)[before:] if WRITE_RE.match(c)]
