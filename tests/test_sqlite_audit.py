from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.core.runtime import AgentRuntime


def test_sqlite_audit_sink_writes_and_queries_by_run_id(tmp_path):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)

    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "tool_call_id": "tc_1"})
    sink.write({"event_type": "ToolExecutionFinished", "run_id": "run_2", "tool_call_id": "tc_2"})

    events = sink.query(run_id="run_1")

    assert len(events) == 1
    assert events[0]["event_type"] == "ToolCallRequested"
    assert events[0]["run_id"] == "run_1"


def test_sqlite_audit_sink_queries_by_trace_id_and_tool_name(tmp_path):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)

    sink.write(
        {
            "event_type": "ToolCallRequested",
            "run_id": "run_1",
            "trace_id": "trace_1",
            "tool_name": "echo",
        }
    )
    sink.write(
        {
            "event_type": "ToolCallRequested",
            "run_id": "run_2",
            "trace_id": "trace_2",
            "tool_name": "other",
        }
    )

    by_trace = sink.query(trace_id="trace_1")
    by_tool = sink.query(tool_name="echo")

    assert len(by_trace) == 1
    assert by_trace[0]["run_id"] == "run_1"
    assert len(by_tool) == 1
    assert by_tool[0]["trace_id"] == "trace_1"


def test_runtime_uses_sqlite_audit_sink_when_configured(tmp_path):
    db_path = tmp_path / "audit.db"
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"sink": "sqlite", "path": str(db_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> str:
        return value

    result = runtime.call_tool("echo", {"value": "hello"}, actor={}, environment="dev")
    events = SQLiteAuditSink(db_path).query(run_id=result.run_id)

    assert result.output == "hello"
    assert [event["event_type"] for event in events] == [
        "ToolCallRequested",
        "PolicyEvaluated",
        "ToolExecutionStarted",
        "ToolExecutionFinished",
    ]
