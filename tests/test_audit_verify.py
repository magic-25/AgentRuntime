import json
import sqlite3

from agent_runtime.audit.jsonl import JsonlAuditSink
from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.audit.verify import verify_audit_chain
from agent_runtime.cli.main import main


def test_verify_jsonl_audit_chain_detects_tampering(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(audit_path)
    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "payload": {"value": "one"}})
    sink.write({"event_type": "ToolExecutionFinished", "run_id": "run_1", "payload": {"value": "two"}})

    assert verify_audit_chain(audit_path, sink="jsonl").valid is True

    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    events[0]["payload"]["value"] = "tampered"
    audit_path.write_text("\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n", encoding="utf-8")

    result = verify_audit_chain(audit_path, sink="jsonl")
    assert result.valid is False
    assert result.error == "event_hash_mismatch"
    assert result.index == 0


def test_verify_sqlite_audit_chain_detects_tampering(tmp_path):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)
    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "payload": {"value": "one"}})
    sink.write({"event_type": "ToolExecutionFinished", "run_id": "run_1", "payload": {"value": "two"}})

    assert verify_audit_chain(db_path, sink="sqlite").valid is True

    with sqlite3.connect(db_path) as connection:
        payload = json.loads(connection.execute("select payload_json from audit_events where id = 1").fetchone()[0])
        payload["payload"]["value"] = "tampered"
        connection.execute("update audit_events set payload_json = ? where id = 1", (json.dumps(payload, sort_keys=True),))

    result = verify_audit_chain(db_path, sink="sqlite")
    assert result.valid is False
    assert result.error == "event_hash_mismatch"
    assert result.index == 0


def test_cli_audit_verify_outputs_result(tmp_path, capsys):
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(audit_path)
    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1"})

    exit_code = main(["audit", "verify", "--path", str(audit_path), "--sink", "jsonl"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
