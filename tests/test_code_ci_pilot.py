import json
import subprocess
import sys

from agent_runtime_contrib.pilot.code_ci import CodeCIPilot


def test_code_ci_pilot_denies_commit_push_and_pr_commands(tmp_path):
    pilot = CodeCIPilot(allowed_commands=[[sys.executable, "-c", "print('ok')"]])

    result = pilot.run(repo_path=tmp_path, command=["git", "commit"], write_scope=tmp_path)

    assert result.status == "denied"
    assert result.error == "command.denied"
    assert result.commit_push_pr_denied is True


def test_code_ci_pilot_aborts_dirty_workspace_by_default(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "changed.txt").write_text("dirty", encoding="utf-8")
    pilot = CodeCIPilot(allowed_commands=[[sys.executable, "-c", "print('ok')"]])

    result = pilot.run(repo_path=tmp_path, command=[sys.executable, "-c", "print('ok')"], write_scope=tmp_path)

    assert result.status == "aborted"
    assert result.error == "dirty_workspace"
    assert result.dirty_workspace_status == "dirty"


def test_code_ci_pilot_runs_allowlisted_command_and_writes_report(tmp_path):
    report_path = tmp_path / "pilot-report.json"
    command = [sys.executable, "-c", "print('pilot-ok')"]
    pilot = CodeCIPilot(allowed_commands=[command])

    result = pilot.run(repo_path=tmp_path, command=command, write_scope=tmp_path, report_path=report_path)

    assert result.status == "success"
    assert result.audit_mode == "digest-only"
    assert result.network_access is False
    assert result.limitations
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "success"
    assert payload["executed_commands"] == [command]
