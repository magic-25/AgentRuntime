import json
import threading
import time

from agent_runtime.audit.jsonl import JsonlAuditSink
from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.audit.hash_chain import attach_event_hash
from agent_runtime.audit.verify import verify_audit_chain


class SlowLastHashJsonlAuditSink(JsonlAuditSink):
    def _last_event_hash(self) -> str | None:
        value = super()._last_event_hash()
        time.sleep(0.02)
        return value


class SlowLastHashSQLiteAuditSink(SQLiteAuditSink):
    def _last_event_hash(self, connection):
        value = super()._last_event_hash(connection)
        time.sleep(0.02)
        return value


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


def test_sqlite_audit_sink_serializes_concurrent_writes(tmp_path):
    db_path = tmp_path / "audit.db"
    sink = SlowLastHashSQLiteAuditSink(db_path)
    barrier = threading.Barrier(8)

    def write_event(index: int) -> None:
        barrier.wait(timeout=2)
        sink.write({"event_type": "ToolCallRequested", "run_id": f"run_{index}", "payload": {"index": index}})

    threads = [threading.Thread(target=write_event, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    result = verify_audit_chain(db_path, sink="sqlite")
    assert result.valid is True
    assert result.checked_events == 8


def test_jsonl_audit_sink_serializes_concurrent_writes(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = SlowLastHashJsonlAuditSink(audit_path)
    barrier = threading.Barrier(8)

    def write_event(index: int) -> None:
        barrier.wait(timeout=2)
        sink.write({"event_type": "ToolCallRequested", "run_id": f"run_{index}", "payload": {"index": index}})

    threads = [threading.Thread(target=write_event, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    result = verify_audit_chain(audit_path, sink="jsonl")
    assert result.valid is True
    assert result.checked_events == 8


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
