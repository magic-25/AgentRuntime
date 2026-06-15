import json

from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.cli.main import main


def test_cli_audit_query_filters_by_run_id(tmp_path, capsys):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)
    sink.write({"event_type": "ToolCallRequested", "run_id": "run_1", "tool_call_id": "tc_1"})
    sink.write({"event_type": "ToolCallRequested", "run_id": "run_2", "tool_call_id": "tc_2"})

    exit_code = main(["audit", "query", "--path", str(db_path), "--run-id", "run_1"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "run_1" in output
    assert "run_2" not in output


def test_cli_doctor_accepts_valid_config(tmp_path, capsys):
    config_path = tmp_path / "agent-runtime.json"
    config_path.write_text(json.dumps({"version": 1, "default_decision": "deny", "rules": []}), encoding="utf-8")

    exit_code = main(["doctor", "--path", str(config_path)])

    assert exit_code == 0
    assert "ok" in capsys.readouterr().out.lower()


def test_cli_doctor_reports_path_field_and_suggestion_for_invalid_config(tmp_path, capsys):
    config_path = tmp_path / "agent-runtime.json"
    config_path.write_text("{}", encoding="utf-8")

    exit_code = main(["doctor", "--path", str(config_path)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert str(config_path) in output
    assert "default_decision" in output
    assert "建议" in output
