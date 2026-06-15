import json

from agent_runtime.approval.base import TimeoutApprovalProvider
from agent_runtime.cli.main import main
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.observer.memory import InMemoryObserver


class FailingAuditSink:
    def write(self, event):
        raise OSError("disk full")


def test_observer_records_success_denied_and_timeout_metrics(tmp_path):
    observer = InMemoryObserver()
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "audit.jsonl")},
            "rules": [
                {"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"},
                {"id": "approve-risk", "environment": "prod", "tool": "echo", "effect": "require_approval"},
            ],
        },
        approval_provider=TimeoutApprovalProvider(),
        observer=observer,
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    runtime.call_tool("echo", {"value": "ok"}, actor={}, environment="dev")
    runtime.call_tool("missing", {}, actor={}, environment="dev")
    runtime.call_tool("echo", {"value": "timeout"}, actor={}, environment="prod")

    status = observer.status()
    assert status["tool_calls"] == 3
    assert status["failures"] == 2
    assert status["denied"] == 1
    assert status["timeouts"] == 1
    assert status["failure_rate"] > 0
    assert status["reject_rate"] > 0
    assert status["timeout_rate"] > 0


def test_observe_status_cli_reads_observer_snapshot(tmp_path, capsys):
    observer_path = tmp_path / "observer.json"
    observer_path.write_text(
        json.dumps({"tool_calls": 3, "failure_rate": 0.25, "reject_rate": 0.1, "timeout_rate": 0.05}),
        encoding="utf-8",
    )

    exit_code = main(["observe", "status", "--path", str(observer_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "tool_calls" in output
    assert "failure_rate" in output


def test_audit_failure_updates_observer_metric():
    observer = InMemoryObserver()
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"on_write_failure": {"prod": "fail_closed"}},
            "rules": [{"id": "allow-echo", "environment": "prod", "tool": "echo", "effect": "allow"}],
        },
        observer=observer,
    )
    runtime.audit_sink = FailingAuditSink()

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="prod")

    status = observer.status()
    assert status["audit_write_failures"] == 1
    assert status["audit_fail_closed"] == 1
