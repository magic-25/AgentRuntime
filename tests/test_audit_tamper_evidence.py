import json

from agent_runtime.audit.jsonl import JsonlAuditSink
from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.audit.hash_chain import attach_event_hash


def test_event_hash_includes_previous_event_hash():
    payload = {"event_type": "ToolExecutionFinished", "run_id": "run_1"}

    first = attach_event_hash(payload, "hash_a")
    second = attach_event_hash(payload, "hash_b")

    assert first["previous_event_hash"] == "hash_a"
    assert second["previous_event_hash"] == "hash_b"
    assert first["event_hash"] != second["event_hash"]


def test_jsonl_audit_sink_writes_hash_chain(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(audit_path)

    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "payload": {"value": "one"}})
    sink.write({"event_type": "ToolExecutionFinished", "run_id": "run_1", "payload": {"value": "two"}})

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event_hash"]
    assert events[0]["previous_event_hash"] is None
    assert events[1]["event_hash"]
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]


def test_sqlite_audit_sink_writes_hash_chain(tmp_path):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)

    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "tool_name": "echo"})
    sink.write({"event_type": "ToolExecutionFinished", "run_id": "run_1", "tool_name": "echo"})

    events = sink.query(run_id="run_1")
    assert events[0]["event_hash"]
    assert events[0]["previous_event_hash"] is None
    assert events[1]["event_hash"]
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]
