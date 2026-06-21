import shutil

import pytest

from agent_runtime.core.runtime import AgentRuntime
from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend


@pytest.mark.integration
def test_docker_sandbox_runtime_e2e(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("docker binary is not available")

    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [
                {"id": "allow-docker-e2e", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:docker_echo"]},
                {"id": "allow-python", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:python"]},
            ],
        },
        sandbox_executor=DockerSandboxBackend(image="python:3.12-slim"),
    )
    runtime.sandboxed_command_tool(
        name="docker_echo",
        argv=["python", "-c", "print('docker-e2e-ok')"],
        cwd=str(tmp_path),
        capabilities_required=["tool.invoke:docker_echo", "command.execute:python"],
        read_paths=[str(tmp_path)],
        network_access=False,
    )

    result = runtime.call_tool("docker_echo", {}, actor={"id": "e2e"}, environment="prod")

    if result.status == "error" and result.error == "sandbox.unavailable":
        pytest.skip("docker daemon is not available")
    assert result.status == "success"
    assert result.output["exit_code"] == 0
    assert "docker-e2e-ok" in result.output["stdout"]

    audit_text = audit_path.read_text(encoding="utf-8")
    assert "SandboxEnforced" in audit_text
    assert "TraceSpanStarted" in audit_text
    assert "TraceSpanFinished" in audit_text
