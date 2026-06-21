import json
import subprocess

from agent_runtime.cli.main import main
import agent_runtime_contrib.sandbox_evidence as sandbox_evidence
from agent_runtime_contrib.sandbox_evidence import DockerRuntimeEvidenceCollector


class FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_docker_runtime_evidence_collector_records_daemon_without_smoke():
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[:2] == ["docker", "--version"]:
            return FakeCompleted("Docker version 28.0.1, build test\n")
        if argv[:2] == ["docker", "info"]:
            return FakeCompleted('"28.0.1"\n')
        raise AssertionError(argv)

    evidence = DockerRuntimeEvidenceCollector(run=fake_run).collect(run_smoke=False)

    assert evidence.backend == "docker"
    assert evidence.daemon_available is True
    assert evidence.server_version == "28.0.1"
    assert evidence.smoke_ran is False
    assert "container_trusted_base_required" in evidence.limitations
    assert calls == [["docker", "--version"], ["docker", "info", "--format", "{{json .ServerVersion}}"]]


def test_docker_runtime_evidence_collector_reports_smoke_result_when_requested():
    def fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "--version"]:
            return FakeCompleted("Docker version 28.0.1, build test\n")
        if argv[:2] == ["docker", "info"]:
            return FakeCompleted('"28.0.1"\n')
        if argv[:2] == ["docker", "run"]:
            assert "--network" in argv
            assert "none" in argv
            assert "--read-only" in argv
            return FakeCompleted("agent-runtime-smoke\n")
        raise AssertionError(argv)

    evidence = DockerRuntimeEvidenceCollector(run=fake_run).collect(run_smoke=True, image="busybox:latest")

    assert evidence.smoke_ran is True
    assert evidence.smoke_passed is True
    assert evidence.smoke_output == "agent-runtime-smoke"


def test_cli_sandbox_evidence_outputs_json(monkeypatch, capsys):
    def fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "--version"]:
            return FakeCompleted("Docker version 28.0.1, build test\n")
        if argv[:2] == ["docker", "info"]:
            return FakeCompleted('"28.0.1"\n')
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(sandbox_evidence.subprocess, "run", fake_run)

    exit_code = main(["sandbox", "evidence", "--backend", "container"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "docker"
    assert payload["daemon_available"] is True
    assert payload["smoke_ran"] is False
