import json

from agent_runtime.cli.main import main
from agent_runtime_contrib.sandbox_conformance import SandboxConformanceRunner
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend
from agent_runtime_contrib.packs.sandbox.remote import RemoteSandboxBackend
from agent_runtime_contrib.packs.sandbox.sidecar import LocalSidecarClient, SidecarSandboxBackend


def test_sandbox_conformance_runner_reports_container_abuse_checks():
    report = SandboxConformanceRunner().run_backend(ContainerSandboxBackend())

    assert report.backend == "container"
    assert report.support_level == "stable_candidate"
    assert report.passed is True
    assert "abuse.path_traversal" in report.checks
    assert "abuse.credential_path" in report.checks
    assert report.limitations


def test_sandbox_conformance_runner_reports_sidecar_and_remote_support_levels():
    sidecar_report = SandboxConformanceRunner().run_backend(SidecarSandboxBackend(client=LocalSidecarClient()))
    remote_report = SandboxConformanceRunner().run_backend(RemoteSandboxBackend())

    assert sidecar_report.support_level == "preview"
    assert sidecar_report.passed is True
    assert remote_report.support_level == "contract_beta"
    assert remote_report.passed is False
    assert "remote.contract_beta_only" in remote_report.failure_reasons


def test_cli_sandbox_conformance_dry_run_reports_json(capsys):
    exit_code = main(["sandbox", "conformance", "--backend", "container", "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["report"]["backend"] == "container"
    assert payload["report"]["passed"] is True
