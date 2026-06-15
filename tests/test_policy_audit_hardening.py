import json

from agent_runtime.approval.base import TimeoutApprovalProvider
from agent_runtime.core.runtime import AgentRuntime


def test_policy_evaluated_audit_event_records_capability_actor_environment_and_policy_version(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [
                {
                    "id": "allow-dev-echo",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:echo"],
                }
            ],
        }
    )

    @runtime.tool(name="echo", capabilities_required=["tool.invoke:echo"])
    def echo(value: str) -> str:
        return value

    runtime.call_tool("echo", {"value": "hello"}, actor={"type": "user", "id": "alice"}, environment="dev")

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    policy_event = next(event for event in events if event["event_type"] == "PolicyEvaluated")

    assert policy_event["payload"]["capability"] == "tool.invoke:echo"
    assert policy_event["payload"]["environment"] == "dev"
    assert policy_event["payload"]["actor"] == {"type": "user", "id": "alice"}
    assert policy_event["payload"]["policy_version"] == 1


def test_audit_events_include_stable_event_id_trace_id_and_tool_name(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")

    event = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["event_id"].startswith("evt_")
    assert event["trace_id"].startswith("trace_")
    assert event["tool_name"] == "echo"


def test_policy_hook_exception_denies_tool_and_writes_runtime_error(tmp_path):
    audit_path = tmp_path / "audit.jsonl"

    def broken_policy_hook(ctx):
        raise RuntimeError("policy backend down")

    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        },
        policy_hook=broken_policy_hook,
    )
    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")

    assert result.status == "denied"
    assert result.error == "policy.hook_failed"
    assert called is False
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event_type"] == "RuntimeError"
    assert events[-1]["payload"]["error"] == "policy.hook_failed"


def test_approval_timeout_rejects_tool_and_writes_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "approve-echo", "environment": "prod", "tool": "echo", "effect": "require_approval"}],
        },
        approval_provider=TimeoutApprovalProvider(),
    )
    called = False

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        nonlocal called
        called = True
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="prod")

    assert result.status == "rejected"
    assert result.error == "approval.timeout"
    assert called is False
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    approval_event = next(event for event in events if event["event_type"] == "ApprovalResolved")
    assert approval_event["payload"]["approved"] is False
    assert approval_event["payload"]["reason"] == "approval.timeout"


def test_custom_redaction_fields_are_removed_from_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "redaction": {"sensitive_fields": ["customer_note"]},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(customer_note: str) -> dict[str, str]:
        return {"customer_note": customer_note}

    runtime.call_tool("echo", {"customer_note": "private note"}, actor={}, environment="dev")

    assert "private note" not in audit_path.read_text(encoding="utf-8")
