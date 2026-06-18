import json

import pytest

from agent_runtime import AgentMetadata, RuntimeProfile
from agent_runtime.approval.base import StaticApprovalProvider
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.base import ProcessResult
from agent_runtime.testing.provider_agents import OpenAICompatibleToolCallingAgent


class FakeOpenAICompatibleTransport:
    def complete(self, payload):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"message": "trace me"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }


class FailingAgent:
    def run(self, prompt):
        raise RuntimeError(f"agent failed: {prompt}")


class RecordingSandboxExecutor:
    backend_name = "recording-strong-sandbox"
    available = True

    def execute(self, spec):
        return ProcessResult(exit_code=0, stdout="sandbox-ok", stderr="")


def _events(audit_path):
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]


def _trace_event(events, event_type, span_kind):
    return next(
        event
        for event in events
        if event["event_type"] == event_type and event["payload"].get("span_kind") == span_kind
    )


def test_runtime_emits_trace_span_events_for_tool_call(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")

    events = _events(audit_path)
    started = _trace_event(events, "TraceSpanStarted", "tool_call")
    finished = _trace_event(events, "TraceSpanFinished", "tool_call")

    assert started["trace_id"] == finished["trace_id"]
    assert started["span_id"] == finished["span_id"]
    assert started["payload"]["span_kind"] == "tool_call"
    assert "started_at" in started["payload"]
    assert "finished_at" in finished["payload"]
    assert finished["payload"]["duration_ms"] >= 0
    assert finished["payload"]["status"] == "success"


def test_runtime_trace_explains_allowed_tool_policy_and_auditability(tmp_path):
    audit_path = tmp_path / "governed-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 7,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={"id": "agent"}, environment="dev")

    events = _events(audit_path)
    tool_start = _trace_event(events, "TraceSpanStarted", "tool_call")
    tool_finish = _trace_event(events, "TraceSpanFinished", "tool_call")
    policy_finish = _trace_event(events, "TraceSpanFinished", "policy_evaluation")

    assert result.status == "success"
    assert policy_finish["trace_id"] == tool_start["trace_id"]
    assert policy_finish["payload"]["parent_span_id"] == tool_start["span_id"]
    assert policy_finish["payload"]["decision"] == "allow"
    assert policy_finish["payload"]["reason"] == "matched_rule"
    assert policy_finish["payload"]["rule_id"] == "allow-echo"
    assert policy_finish["payload"]["policy_version"] == 7
    assert tool_finish["payload"]["status"] == "success"
    assert tool_finish["payload"]["decision"] == "allow"
    assert tool_finish["payload"]["audit_status"] == "committed"


def test_runtime_trace_explains_denied_tool_without_execution(tmp_path):
    audit_path = tmp_path / "denied-governed-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "blocked"}, actor={"id": "agent"}, environment="dev")

    events = _events(audit_path)
    event_types = [event["event_type"] for event in events]
    tool_start = _trace_event(events, "TraceSpanStarted", "tool_call")
    tool_finish = _trace_event(events, "TraceSpanFinished", "tool_call")
    policy_finish = _trace_event(events, "TraceSpanFinished", "policy_evaluation")

    assert result.status == "denied"
    assert "ToolExecutionStarted" not in event_types
    assert policy_finish["payload"]["decision"] == "deny"
    assert policy_finish["payload"]["reason"] == "default_decision"
    assert policy_finish["payload"]["parent_span_id"] == tool_start["span_id"]
    assert tool_finish["trace_id"] == tool_start["trace_id"]
    assert tool_finish["span_id"] == tool_start["span_id"]
    assert tool_finish["payload"]["status"] == "denied"
    assert tool_finish["payload"]["decision"] == "deny"
    assert tool_finish["payload"]["reason"] == "default_decision"
    assert tool_finish["payload"]["audit_status"] == "committed"


def test_runtime_trace_records_strong_sandbox_isolation(tmp_path):
    audit_path = tmp_path / "sandbox-governed-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [
                {"id": "allow-tool", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:*"]},
                {"id": "allow-command", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:*"]},
            ],
        },
        sandbox_executor=RecordingSandboxExecutor(),
    )
    runtime.sandboxed_command_tool(
        name="sandboxed_status",
        argv=["python", "-c", "print('sandbox-ok')"],
        cwd=str(tmp_path),
        risk_level="high",
        capabilities_required=["tool.invoke:sandboxed_status", "command.execute:python"],
        network_access=False,
        read_paths=[str(tmp_path)],
        write_paths=[],
    )

    result = runtime.call_tool("sandboxed_status", {}, actor={"id": "ops-agent"}, environment="prod")

    events = _events(audit_path)
    tool_start = _trace_event(events, "TraceSpanStarted", "tool_call")
    sandbox_finish = _trace_event(events, "TraceSpanFinished", "sandbox_execution")

    assert result.status == "success"
    assert sandbox_finish["trace_id"] == tool_start["trace_id"]
    assert sandbox_finish["payload"]["parent_span_id"] == tool_start["span_id"]
    assert sandbox_finish["payload"]["isolation_level"] == "strong"
    assert sandbox_finish["payload"]["backend"] == "recording-strong-sandbox"
    assert sandbox_finish["payload"]["available"] is True
    assert sandbox_finish["payload"]["status"] == "success"


def test_runtime_trace_records_approval_gate_when_required(tmp_path):
    audit_path = tmp_path / "approval-governed-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [{"id": "approve-echo", "environment": "prod", "tool": "echo", "effect": "require_approval"}],
        },
        approval_provider=StaticApprovalProvider(approved=True, reason="approved-by-test"),
    )

    @runtime.tool(name="echo", risk_level="high")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "approved"}, actor={"id": "agent"}, environment="prod")

    events = _events(audit_path)
    tool_start = _trace_event(events, "TraceSpanStarted", "tool_call")
    approval_finish = _trace_event(events, "TraceSpanFinished", "approval_gate")

    assert result.status == "success"
    assert approval_finish["trace_id"] == tool_start["trace_id"]
    assert approval_finish["payload"]["parent_span_id"] == tool_start["span_id"]
    assert approval_finish["payload"]["approved"] is True
    assert approval_finish["payload"]["reason"] == "approved-by-test"
    assert approval_finish["payload"]["status"] == "approved"


def test_registered_agent_emits_agent_run_trace_parenting_tool_span(tmp_path):
    audit_path = tmp_path / "agent-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    agent = OpenAICompatibleToolCallingAgent(
        runtime=None,
        transport=FakeOpenAICompatibleTransport(),
        provider="glm",
        model="glm-5.2",
        actor={"id": "glm-agent"},
        environment="dev",
    )
    metadata = AgentMetadata(
        agent_id="glm-agent",
        name="GLM tracing agent",
        provider="glm",
        framework="openai-compatible",
        capabilities=["tool.invoke:echo"],
        runtime_profile=RuntimeProfile(environment="dev", execution_mode="runtime_tools", max_tool_calls=1),
    )

    transcript = runtime.register_agent(
        "glm-agent",
        agent,
        actor={"id": "glm-agent"},
        environment="dev",
        metadata=metadata,
    ).run("Call echo.")

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    trace_starts = [event for event in events if event["event_type"] == "TraceSpanStarted"]
    trace_finishes = [event for event in events if event["event_type"] == "TraceSpanFinished"]
    agent_start = next(event for event in trace_starts if event["payload"]["span_kind"] == "agent_run")
    agent_finish = next(event for event in trace_finishes if event["payload"]["span_kind"] == "agent_run")
    tool_start = next(event for event in trace_starts if event["payload"]["span_kind"] == "tool_call")
    tool_finish = next(event for event in trace_finishes if event["payload"]["span_kind"] == "tool_call")

    assert transcript.trace_id == agent_start["trace_id"]
    assert transcript.agent_span_id == agent_start["span_id"]
    assert agent_start["trace_id"] == tool_start["trace_id"]
    assert agent_finish["trace_id"] == agent_start["trace_id"]
    assert agent_finish["span_id"] == agent_start["span_id"]
    assert tool_start["payload"]["agent_id"] == "glm-agent"
    assert tool_start["payload"]["parent_span_id"] == agent_start["span_id"]
    assert tool_finish["payload"]["parent_span_id"] == agent_start["span_id"]
    assert agent_start["payload"]["metadata"]["framework"] == "openai-compatible"
    assert agent_finish["payload"]["status"] == "completed"


def test_registered_agent_failure_finishes_agent_run_trace_span(tmp_path):
    audit_path = tmp_path / "agent-failure-trace.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [],
        }
    )
    metadata = AgentMetadata(
        agent_id="failing-agent",
        name="Failing tracing agent",
        provider="local",
        framework="custom-python",
        capabilities=[],
        runtime_profile=RuntimeProfile(environment="dev", execution_mode="runtime_tools", max_tool_calls=0),
    )

    registered = runtime.register_agent(
        "failing-agent",
        FailingAgent(),
        actor={"id": "failing-agent"},
        environment="dev",
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match="agent failed"):
        registered.run("boom")

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    agent_run_finished = next(event for event in events if event["event_type"] == "AgentRunFinished")
    trace_started = next(
        event
        for event in events
        if event["event_type"] == "TraceSpanStarted" and event["payload"]["span_kind"] == "agent_run"
    )
    trace_finished = next(
        event
        for event in events
        if event["event_type"] == "TraceSpanFinished" and event["payload"]["span_kind"] == "agent_run"
    )

    assert agent_run_finished["payload"]["status"] == "failed"
    assert agent_run_finished["payload"]["error"] == "RuntimeError"
    assert trace_finished["trace_id"] == trace_started["trace_id"]
    assert trace_finished["span_id"] == trace_started["span_id"]
    assert trace_finished["payload"]["status"] == "failed"
    assert trace_finished["payload"]["error"] == "RuntimeError"
