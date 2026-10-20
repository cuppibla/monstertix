"""Cloud setup failure paths, without provisioning anything or calling gcloud."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cloud_check", ROOT / "scripts/cloud-check.py")
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


def configured():
    return {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VENUE_URL": "https://venue.example.test",
        "AGENT_SERVICE_URL": "https://agent.example.test",
        "CLOUD_SESSION_SERVICE_URI": "postgresql+asyncpg://user:fake@/adk?host=/cloudsql/test:region:db",
        "SQL_CONNECTION_NAME": "test:region:db",
        "STATE_BUCKET": "gs://test-state",
        "CLOUD_ARTIFACT_SERVICE_URI": "gs://test-state/artifacts",
    }


@pytest.mark.parametrize("url", ["", "http://127.0.0.1:8080", "https://localhost", "https://[::1]"])
def test_preflight_blocks_local_venue(tmp_path, monkeypatch, url):
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    env = configured()
    env["VENUE_URL"] = url
    with pytest.raises(ValueError, match="deploy-venue"):
        cloud.check(env)


def test_preflight_requires_storage_and_does_not_print_password(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    env = configured()
    env["CLOUD_ARTIFACT_SERVICE_URI"] = ""
    with pytest.raises(ValueError) as exc:
        cloud.check(env)
    assert "setup-cloud-state" in str(exc.value)
    assert "user:fake" not in str(exc.value)


def test_saved_cloud_url_overrides_local_workbench_url(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    monkeypatch.setenv("VENUE_URL", "http://127.0.0.1:58980")
    (tmp_path / ".env").write_text("VENUE_URL='https://venue.example.test'\n")
    assert cloud.settings()["VENUE_URL"] == "https://venue.example.test"


def test_health_requires_service_url():
    with pytest.raises(ValueError, match="Finish ./deploy-agent"):
        cloud.health({})


@pytest.mark.parametrize("body", [b"", b"not json", b'{"ok": false}'])
def test_empty_or_invalid_health_never_passes(monkeypatch, body):
    monkeypatch.setattr(cloud.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body))
    with pytest.raises(ValueError):
        cloud.get_health("https://venue.example.test")


def test_health_checks_database_read_and_venue(monkeypatch):
    env = configured()
    seen = []
    def request(url, **_):
        seen.append(url)
        if url.endswith("/task"):
            return io.BytesIO(b'{"session_id": null}')
        result = {"ok": True}
        if "agent." in url:
            result.update(app="concert", sessions="/adk?host=/cloudsql/test:region:db",
                          memory="gs://test-state/memory", venue=env["VENUE_URL"])
        return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr(cloud.urllib.request, "urlopen", request)
    cloud.health(env)
    assert seen == ["https://agent.example.test/health", "https://venue.example.test/health",
                    "https://agent.example.test/task"]


def test_database_read_failure_is_not_healthy(monkeypatch):
    env = configured()
    monkeypatch.setattr(cloud, "get_health", lambda _: {
        "ok": True, "app": "concert", "sessions": "/cloudsql/test",
        "memory": "gs://test-state/memory", "venue": env["VENUE_URL"]})
    def fail(*_, **__):
        raise OSError("unavailable")
    monkeypatch.setattr(cloud.urllib.request, "urlopen", fail)
    with pytest.raises(ValueError, match="session store"):
        cloud.health(env)


@pytest.fixture
def shell_lab(tmp_path):
    for name in ("deploy-agent.sh", "deploy-venue.sh", "setup-cloud-state.sh"):
        shutil.copy(ROOT / name, tmp_path / name)
    for name in ("main.py", "Dockerfile", "requirements.txt", "monstertix/index.html", "concert/agent.py"):
        path = tmp_path / "agent" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    # Stub only network health; the shell must still stop at its failed gcloud step.
    (scripts / "cloud-check.py").write_text("print('fixture health ok')\n")
    (tmp_path / ".env").write_text("\n".join(f"{k}={v}" for k, v in configured().items()) + "\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gcloud = bin_dir / "gcloud"
    gcloud.write_text("""#!/usr/bin/env python3
import os,sys
a=sys.argv[1:]; cmd=' '.join(a)
with open(os.environ['CALLS'], 'a') as f: f.write(cmd+'\\n')
if os.environ.get('FAIL') and os.environ['FAIL'] in cmd:
    print('fixture permission failure', file=sys.stderr); sys.exit(7)
if cmd.startswith('config get-value account'): print('learner@example.test')
elif cmd.startswith('projects describe'): print('123456')
elif cmd.startswith('builds get-default-service-account'): print('123456-compute@developer.gserviceaccount.com')
elif cmd.startswith('run services describe'): print('https://agent.example.test')
elif cmd.startswith('sql instances describe'):
    print('RUNNABLE' if 'state' in cmd else 'test:region:db')
elif cmd.startswith('sql databases describe'): sys.exit(1)
""")
    gcloud.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text("""#!/usr/bin/env python3
import os,sys
print(os.environ.get('CURL_BODY','{"ok":true}'))
sys.exit(int(os.environ.get('CURL_EXIT','0')))
""")
    curl.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CALLS": str(tmp_path / "calls")}
    def run(script, fail="", extra=None):
        return subprocess.run(["bash", script], cwd=tmp_path,
                              env={**env, "FAIL": fail, **(extra or {})}, capture_output=True, text=True)
    return tmp_path, run


@pytest.mark.parametrize("failure", [
    "pubsub subscriptions update", "scheduler jobs update",
    "iam service-accounts add-iam-policy-binding", "run deploy",
])
def test_deploy_never_claims_success_after_failed_step(shell_lab, failure):
    _, run = shell_lab
    result = run("deploy-agent.sh", failure)
    assert result.returncode != 0
    assert "✓ deployed." not in result.stdout


def test_database_creation_failure_stops_setup(shell_lab):
    _, run = shell_lab
    result = run("setup-cloud-state.sh", "sql databases create")
    assert result.returncode != 0
    assert "database  adk exists" not in result.stdout
    assert "durable state ready" not in result.stdout


@pytest.mark.parametrize("extra", [{"CURL_BODY": ""}, {"CURL_EXIT": "22"},
                                  {"CURL_BODY": '{"ok":false}'}])
def test_venue_health_failure_never_reports_deployed(shell_lab, extra):
    _, run = shell_lab
    result = run("deploy-venue.sh", extra=extra)
    assert result.returncode != 0
    assert "✓ venue deployed" not in result.stdout


def test_custom_password_is_escaped_and_not_printed(shell_lab, monkeypatch):
    path, run = shell_lab
    password = "fake@pass&word with spaces"
    result = run("setup-cloud-state.sh", extra={"SQL_PASSWORD": password})
    assert result.returncode == 0, result.stderr
    assert password not in result.stdout
    monkeypatch.setattr(cloud, "ROOT", path)
    assert "fake%40pass%26word%20with%20spaces" in cloud.settings()["CLOUD_SESSION_SERVICE_URI"]


def test_complete_script_records_url_only_after_all_cloud_steps(shell_lab):
    path, run = shell_lab
    result = run("deploy-agent.sh")
    assert result.returncode == 0, result.stderr
    assert "✓ deployed." in result.stdout
    calls = (path / "calls").read_text()
    assert "roles/run.builder" in calls
    assert "--service-account=" in calls
    assert "/trigger/wake" in calls


def test_cloud_buttons_resolve_to_their_own_commands():
    # Task IDs are shared across all parts of a chapter. Duplicate "turn" IDs
    # made a button in 6b/6c resolve to an item from 6a.
    import yaml
    from workbench.api import _command
    data = yaml.safe_load((ROOT / "content/steps/06-cloud/step.yaml").read_text())
    ids = set()
    for part in data["parts"]:
        for exercise in part["exercises"].values():
            for task in exercise["tasks"]:
                commands = [(i, item["run"]) for i, item in enumerate(task.get("items", [])) if "run" in item]
                if commands:
                    assert task["id"] not in ids
                    ids.add(task["id"])
                    for index, command in commands:
                        assert _command("cloud", task["id"], index) == command
