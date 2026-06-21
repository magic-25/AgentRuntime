import json
import sys

import pytest

from agent_runtime.audit.jsonl import JsonlAuditSink
from agent_runtime.approval.base import StaticApprovalProvider
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.sandbox import SandboxViolationError
from agent_runtime.execution.subprocess import SubprocessExecutor


def test_jsonl_audit_sink_appends_events(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(audit_path)

    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1"})

    line = audit_path.read_text(encoding="utf-8").strip()
    assert json.loads(line)["event_type"] == "ToolCallRequested"


def test_runtime_calls_python_function_and_writes_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={"id": "alice"}, environment="dev")

    assert result.output == "hello"
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert "PolicyEvaluated" in [event["event_type"] for event in events]
    assert "ToolExecutionFinished" in [event["event_type"] for event in events]


def test_runtime_calls_command_tool_through_same_policy_and_audit_chain(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    script = tmp_path / "tool.py"
    script.write_text("print('command-ok')", encoding="utf-8")
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-command", "environment": "dev", "tool": "check_status", "effect": "allow"}],
        }
    )
    runtime.command_tool(
        name="check_status",
        argv=[sys.executable, str(script)],
        cwd=tmp_path,
        timeout_ms=2000,
        stdout_limit_bytes=64,
        stderr_limit_bytes=64,
    )

    result = runtime.call_tool("check_status", {}, actor={}, environment="dev")

    assert result.status == "success"
    assert "command-ok" in result.output["stdout"]
    events = [json.loads(line)["event_type"] for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert events[:3] == ["ToolCallRequested", "PolicyEvaluated", "ToolExecutionStarted"]


def test_runtime_from_config_loads_json_config(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    config_path = tmp_path / "agent-runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "default_decision": "deny",
                "audit": {"path": str(audit_path)},
                "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
            }
        ),
        encoding="utf-8",
    )
    runtime = AgentRuntime.from_config(config_path)

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")

    assert result.output == "hello"


def test_runtime_denies_unknown_tool_and_writes_runtime_error(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict({"default_decision": "deny", "audit": {"path": str(audit_path)}, "rules": []})

    result = runtime.call_tool("missing", {}, actor={"id": "alice"}, environment="dev")

    assert result.status == "denied"
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event_type"] == "RuntimeError"


def test_runtime_redacts_secret_values_before_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(api_key: str) -> dict[str, str]:
        return {"api_key": api_key}

    runtime.call_tool("echo", {"api_key": "sk-secret"}, actor={}, environment="dev")

    assert "sk-secret" not in audit_path.read_text(encoding="utf-8")


def test_runtime_requires_approval_before_execution(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "approve-echo", "environment": "prod", "tool": "echo", "effect": "require_approval"}],
        },
        approval_provider=StaticApprovalProvider(approved=False),
    )

    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={"id": "alice"}, environment="prod")

    assert result.status == "rejected"
    assert called is False


def test_subprocess_executor_applies_env_allowlist_timeout_and_output_limit(tmp_path):
    script = tmp_path / "tool.py"
    script.write_text(
        "import os; print(os.environ.get('ALLOWED', 'missing')); print('x' * 100)",
        encoding="utf-8",
    )
    executor = SubprocessExecutor()

    result = executor.execute(
        argv=[sys.executable, str(script)],
        cwd=tmp_path,
        env={"ALLOWED": "yes", "SECRET": "no"},
        env_allowlist=["ALLOWED"],
        timeout_ms=2000,
        stdout_limit_bytes=16,
        stderr_limit_bytes=16,
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("yes")
    assert len(result.stdout.encode("utf-8")) <= 16


def test_subprocess_executor_rejects_secret_like_allowlisted_env(tmp_path):
    executor = SubprocessExecutor()

    with pytest.raises(SandboxViolationError, match="env.secret_denied"):
        executor.execute(
            argv=[sys.executable, "-c", "print('should not run')"],
            cwd=tmp_path,
            env={"API_KEY": "secret-value"},
            env_allowlist=["API_KEY"],
            timeout_ms=2000,
        )
