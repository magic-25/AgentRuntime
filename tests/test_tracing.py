import json

from agent_runtime.core.runtime import AgentRuntime


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

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    started = next(event for event in events if event["event_type"] == "TraceSpanStarted")
    finished = next(event for event in events if event["event_type"] == "TraceSpanFinished")

    assert started["trace_id"] == finished["trace_id"]
    assert started["span_id"] == finished["span_id"]
    assert started["payload"]["span_kind"] == "tool_call"
    assert "started_at" in started["payload"]
    assert "finished_at" in finished["payload"]
    assert finished["payload"]["duration_ms"] >= 0
    assert finished["payload"]["status"] == "success"
