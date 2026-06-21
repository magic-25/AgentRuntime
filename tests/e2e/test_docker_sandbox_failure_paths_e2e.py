import shutil

import pytest

from agent_runtime.core.runtime import AgentRuntime
from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend


def _runtime(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [
                {"id": "allow-tools", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:*"]},
                {"id": "allow-python", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:python"]},
            ],
        },
        sandbox_executor=DockerSandboxBackend(image="python:3.12-slim"),
    )
    return runtime, audit_path


def _call(runtime, tool_name):
    result = runtime.call_tool(tool_name, {}, actor={"id": "docker-e2e"}, environment="prod")
    if result.status == "error" and result.error == "sandbox.unavailable":
        pytest.skip("docker daemon is not available")
    return result


@pytest.mark.integration
def test_docker_sandbox_failure_paths_e2e(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("docker binary is not available")

    runtime, audit_path = _runtime(tmp_path)
    runtime.sandboxed_command_tool(
        name="env_allowlist",
        argv=[
            "python",
            "-c",
            "import os; print('PUBLIC=' + os.getenv('PUBLIC','')); print('SECRET=' + os.getenv('SECRET',''))",
        ],
        cwd=str(tmp_path),
        env={"PUBLIC": "visible", "SECRET": "hidden"},
        env_allowlist=["PUBLIC"],
        capabilities_required=["tool.invoke:env_allowlist", "command.execute:python"],
        read_paths=[str(tmp_path)],
        network_access=False,
    )
    runtime.sandboxed_command_tool(
        name="network_denied",
        argv=["python", "-c", "print('should not reach docker')"],
        cwd=str(tmp_path),
        capabilities_required=["tool.invoke:network_denied", "command.execute:python"],
        read_paths=[str(tmp_path)],
        network_access=True,
    )
    runtime.sandboxed_command_tool(
        name="read_only_workspace",
        argv=["python", "-c", "from pathlib import Path; Path('/workspace/blocked.txt').write_text('nope')"],
        cwd=str(tmp_path),
        capabilities_required=["tool.invoke:read_only_workspace", "command.execute:python"],
        read_paths=[str(tmp_path)],
        write_paths=[],
        network_access=False,
    )
    runtime.sandboxed_command_tool(
        name="timeout_command",
        argv=["python", "-c", "import time; time.sleep(5)"],
        cwd=str(tmp_path),
        capabilities_required=["tool.invoke:timeout_command", "command.execute:python"],
        read_paths=[str(tmp_path)],
        timeout_ms=100,
        network_access=False,
    )

    env_result = _call(runtime, "env_allowlist")
    assert env_result.status == "success"
    assert env_result.output["exit_code"] == 0
    assert "PUBLIC=visible" in env_result.output["stdout"]
    assert "SECRET=hidden" not in env_result.output["stdout"]
    assert "SECRET=" in env_result.output["stdout"]

    network_result = _call(runtime, "network_denied")
    assert network_result.status == "denied"
    assert network_result.error == "sandbox.network_denied"
    assert network_result.output is None

    read_only_result = _call(runtime, "read_only_workspace")
    assert read_only_result.status == "success"
    assert read_only_result.output["exit_code"] != 0
    assert not (tmp_path / "blocked.txt").exists()
    assert "Read-only file system" in read_only_result.output["stderr"] or "Permission denied" in read_only_result.output["stderr"]

    timeout_result = _call(runtime, "timeout_command")
    assert timeout_result.status == "success"
    assert timeout_result.output["exit_code"] == 124
    assert "docker.timeout" in timeout_result.output["stderr"]

    audit_text = audit_path.read_text(encoding="utf-8")
    assert audit_text.count("SandboxEnforced") >= 4
    assert "SECRET=hidden" not in audit_text
    assert "sandbox.network_denied" in audit_text
    assert "TraceSpanFinished" in audit_text
