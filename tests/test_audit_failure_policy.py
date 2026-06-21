from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.sandbox import SandboxExecutor, SandboxViolationError


class RejectingSandboxExecutor(SandboxExecutor):
    backend_name = "rejecting"
    available = True

    def execute(self, spec):
        raise SandboxViolationError("sandbox.network_denied")


class FailingAuditSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event):
        self.events.append(event)
        raise OSError("disk full")


class FailingAfterFirstAuditSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event):
        self.events.append(event)
        if len(self.events) > 1:
            raise OSError("disk full after request")


class FailingOnExecutionFinishedAuditSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event):
        self.events.append(event)
        if event.event_type == "ToolExecutionFinished":
            raise OSError("disk full after execution")


class FailingOnRuntimeErrorAuditSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event):
        self.events.append(event)
        if event.event_type == "RuntimeError":
            raise OSError("disk full on runtime error")


def test_audit_failure_warn_allows_dev_tool_call():
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"dev": "warn"}},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )
    runtime.audit_sink = FailingAuditSink()

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")

    assert result.status == "success"
    assert result.output == "hello"


def test_audit_failure_fail_closed_blocks_prod_tool_call():
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"prod": "fail_closed"}},
            "rules": [{"id": "allow-echo", "environment": "prod", "tool": "echo", "effect": "allow"}],
        }
    )
    runtime.audit_sink = FailingAuditSink()
    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="prod")

    assert result.status == "denied"
    assert result.error == "audit.write_failed"
    assert called is False


def test_audit_failure_fail_closed_blocks_prod_before_execution_when_policy_audit_fails():
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"prod": "fail_closed"}},
            "rules": [{"id": "allow-echo", "environment": "prod", "tool": "echo", "effect": "allow"}],
        }
    )
    runtime.audit_sink = FailingAfterFirstAuditSink()
    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="prod")

    assert result.status == "denied"
    assert result.error == "audit.write_failed"
    assert called is False


def test_audit_failure_after_prod_execution_is_reported_as_error():
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"prod": "fail_closed"}},
            "rules": [{"id": "allow-echo", "environment": "prod", "tool": "echo", "effect": "allow"}],
        }
    )
    runtime.audit_sink = FailingOnExecutionFinishedAuditSink()
    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="prod")

    assert called is True
    assert result.status == "error"
    assert result.error == "audit.write_failed_after_execution"


def test_audit_failure_fail_closed_blocks_runtime_error_path():
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"prod": "fail_closed"}},
            "rules": [{"id": "allow-cmd", "environment": "prod", "tool": "cmd", "effect": "allow"}],
        },
        sandbox_executor=RejectingSandboxExecutor(),
    )
    runtime.audit_sink = FailingOnRuntimeErrorAuditSink()
    runtime.sandboxed_command_tool("cmd", ["python", "-V"], cwd=".")

    result = runtime.call_tool("cmd", {}, actor={}, environment="prod")

    assert result.status == "denied"
    assert result.error == "audit.write_failed"
