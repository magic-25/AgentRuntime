import sys

from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.base import ProcessResult


class RecordingSandboxExecutor:
    backend_name = "recording-strong-sandbox"
    available = True

    def __init__(self) -> None:
        self.calls = []

    def execute(self, spec):
        self.calls.append(spec)
        return ProcessResult(exit_code=0, stdout="sandbox-ok", stderr="")


def _prod_config(tmp_path):
    return {
        "version": 1,
        "default_decision": "deny",
        "audit": {"sink": "sqlite", "path": str(tmp_path / "audit.db")},
        "rules": [
            {"id": "allow-tool", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            {"id": "allow-command", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:*"]},
        ],
    }


def test_prod_high_risk_command_requires_strong_sandbox(tmp_path):
    runtime = AgentRuntime.from_dict(_prod_config(tmp_path))
    runtime.command_tool(
        name="dangerous_write",
        argv=[sys.executable, "-c", "print('should-not-run')"],
        cwd=str(tmp_path),
        risk_level="high",
        capabilities_required=["tool.invoke:dangerous_write", "command.execute:python"],
    )

    result = runtime.call_tool("dangerous_write", {}, actor={}, environment="prod")

    assert result.status == "denied"
    assert result.error == "sandbox.required"
    events = SQLiteAuditSink(tmp_path / "audit.db").query(tool_name="dangerous_write")
    assert any(event["event_type"] == "RuntimeError" and event["payload"]["error"] == "sandbox.required" for event in events)


def test_sandboxed_command_fails_closed_when_backend_unavailable(tmp_path):
    runtime = AgentRuntime.from_dict(_prod_config(tmp_path))
    runtime.sandboxed_command_tool(
        name="sandboxed_write",
        argv=[sys.executable, "-c", "print('should-not-run')"],
        cwd=str(tmp_path),
        risk_level="high",
        capabilities_required=["tool.invoke:sandboxed_write", "command.execute:python"],
        network_access=False,
        read_paths=[str(tmp_path)],
        write_paths=[],
    )

    result = runtime.call_tool("sandboxed_write", {}, actor={}, environment="prod")

    assert result.status == "error"
    assert result.error == "sandbox.unavailable"


def test_sandboxed_command_uses_configured_provider_and_audits_enforcement(tmp_path):
    sandbox = RecordingSandboxExecutor()
    runtime = AgentRuntime.from_dict(_prod_config(tmp_path), sandbox_executor=sandbox)
    runtime.sandboxed_command_tool(
        name="sandboxed_status",
        argv=[sys.executable, "-c", "print('sandbox-ok')"],
        cwd=str(tmp_path),
        env={"ALLOWED": "yes", "SECRET": "no"},
        env_allowlist=["ALLOWED"],
        risk_level="high",
        capabilities_required=["tool.invoke:sandboxed_status", "command.execute:python"],
        network_access=False,
        read_paths=[str(tmp_path)],
        write_paths=[],
    )

    result = runtime.call_tool("sandboxed_status", {}, actor={}, environment="prod")

    assert result.status == "success"
    assert result.output["stdout"] == "sandbox-ok"
    assert len(sandbox.calls) == 1
    spec = sandbox.calls[0]
    assert spec.isolation_level == "strong"
    assert spec.network_access is False
    assert spec.env == {"ALLOWED": "yes"}
    assert spec.env_allowlist == ["ALLOWED"]

    events = SQLiteAuditSink(tmp_path / "audit.db").query(tool_name="sandboxed_status")
    sandbox_events = [event for event in events if event["event_type"] == "SandboxEnforced"]
    assert sandbox_events
    assert sandbox_events[0]["payload"]["isolation_level"] == "strong"
    assert sandbox_events[0]["payload"]["backend"] == "recording-strong-sandbox"
