import json

from agent_runtime.cli.main import main
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend
from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend
from agent_runtime_contrib.packs.sandbox.remote import RemoteSandboxBackend
from agent_runtime_contrib.packs.sandbox.sidecar import LocalSidecarClient, SidecarSandboxBackend
from agent_runtime_contrib.sandbox_conformance import SandboxConformanceRunner, backend_for_name


def test_sandbox_conformance_runner_reports_container_abuse_checks():
    report = SandboxConformanceRunner().run_backend(ContainerSandboxBackend())

    assert report.backend == "container"
    assert report.support_level == "stable_candidate"
    assert report.passed is True
    assert "abuse.path_traversal" in report.checks
    assert "abuse.credential_path" in report.checks
    assert "container_plan_only_no_real_docker_execution" in report.limitations


def test_sandbox_conformance_runner_reports_sidecar_and_remote_support_levels():
    sidecar_report = SandboxConformanceRunner().run_backend(SidecarSandboxBackend(client=LocalSidecarClient()))
    remote_report = SandboxConformanceRunner().run_backend(RemoteSandboxBackend())

    assert sidecar_report.support_level == "preview"
    assert sidecar_report.passed is True
    assert "abuse.network_attempt" in sidecar_report.checks
    assert "abuse.credential_path" in sidecar_report.checks
    assert "abuse.secret_env" in sidecar_report.checks
    assert remote_report.support_level == "contract_beta"
    assert remote_report.passed is False
    assert "remote.contract_beta_only" in remote_report.failure_reasons


def test_docker_sandbox_conformance_reports_preview_real_execution_contract():
    report = SandboxConformanceRunner().run_backend(DockerSandboxBackend())

    assert report.backend == "docker"
    assert report.support_level == "preview"
    assert "docker_real_execution_requires_local_daemon" in report.limitations
    assert "no_absolute_escape_prevention" in report.limitations


def test_backend_for_name_supports_explicit_docker_backend():
    backend = backend_for_name("docker")

    assert isinstance(backend, DockerSandboxBackend)


def test_cli_sandbox_conformance_dry_run_reports_json(capsys):
    exit_code = main(["sandbox", "conformance", "--backend", "container", "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["report"]["backend"] == "container"
    assert payload["report"]["passed"] is True


def test_cli_sandbox_conformance_accepts_docker_backend(capsys):
    exit_code = main(["sandbox", "conformance", "--backend", "docker", "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"]["backend"] == "docker"
    assert payload["report"]["support_level"] == "preview"
