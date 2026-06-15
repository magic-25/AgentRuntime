import json
import sqlite3
import sys

from agent_runtime.audit.verify import verify_audit_chain
from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.cli.main import main
from agent_runtime.core.runtime import AgentRuntime


def test_pilot_report_records_required_production_boundaries(tmp_path):
    from agent_runtime.pilot.records import PilotScenarioRecord, ProductionPilotReport

    report = ProductionPilotReport(
        pilot_name="internal-admin-staging",
        environment="staging",
        isolation_level="subprocess_limited_no_strong_sandbox",
        data_retention_policy="sqlite audit retained for 30 days; raw payload disabled by default",
        audit_sink_boundary="application owns sqlite file, runtime owns append-only event shape",
        failure_mode_drills=["approval.timeout", "policy.deny_unknown_tool"],
        risk_bypasses=["host application direct database writes"],
        scenarios=[
            PilotScenarioRecord(
                name="内部后台助手",
                production_support_judgement="pilot_supported_with_approval",
                data_governance_judgement="no_raw_secret_payloads",
                evidence={"audit_sink": "sqlite", "observer": "memory"},
            )
        ],
    )

    path = tmp_path / "pilot-report.json"
    report.write_json(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["isolation_level"] == "subprocess_limited_no_strong_sandbox"
    assert payload["data_retention_policy"].startswith("sqlite audit retained")
    assert payload["audit_sink_boundary"].startswith("application owns")
    assert payload["failure_mode_drills"] == ["approval.timeout", "policy.deny_unknown_tool"]
    assert payload["risk_bypasses"] == ["host application direct database writes"]
    assert payload["scenarios"][0]["production_support_judgement"] == "pilot_supported_with_approval"
    assert payload["scenarios"][0]["data_governance_judgement"] == "no_raw_secret_payloads"


def test_staging_internal_admin_pilot_generates_audit_observer_and_report(tmp_path):
    from examples.staging_internal_admin_pilot import run_pilot

    result = run_pilot(tmp_path)

    assert result["read_customer"].status == "success"
    assert result["approved_write"].status == "success"
    assert result["timed_out_write"].status == "rejected"
    assert result["timed_out_write"].error == "approval.timeout"
    assert result["unknown_prod_tool"].status == "denied"
    assert result["command_status"].status == "success"
    assert "SECRET_TOKEN" not in result["command_status"].output["stdout"]
    assert "BUILD_ID=build-123" in result["command_status"].output["stdout"]

    audit = SQLiteAuditSink(result["audit_path"])
    assert audit.query(run_id=result["read_customer"].run_id)
    assert audit.query(tool_name="read_customer")
    trace_events = audit.query(tool_name="read_customer")
    assert audit.query(trace_id=trace_events[0]["trace_id"])

    observer = json.loads(result["observer_path"].read_text(encoding="utf-8"))
    assert observer["tool_calls"] >= 4
    assert observer["approval_requests"] >= 2
    assert observer["approval_rejected"] >= 1

    report = json.loads(result["report_path"].read_text(encoding="utf-8"))
    assert report["environment"] == "staging"
    assert report["isolation_level"] == "subprocess_limited_no_strong_sandbox"
    assert len(report["scenarios"]) == 3
    assert all(scenario["production_support_judgement"] for scenario in report["scenarios"])
    assert all(scenario["data_governance_judgement"] for scenario in report["scenarios"])


def test_staging_pilot_reset_clears_legacy_audit_before_demo_run(tmp_path):
    from examples.staging_internal_admin_pilot import run_pilot

    db_path = tmp_path / "pilot-audit.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            create table audit_events (
                id integer primary key autoincrement,
                event_type text not null,
                run_id text,
                payload_json text not null
            )
            """
        )
        connection.execute(
            "insert into audit_events(event_type, run_id, payload_json) values (?, ?, ?)",
            ("ToolCallRequested", "legacy_run", json.dumps({"event_type": "ToolCallRequested", "run_id": "legacy_run"})),
        )

    result = run_pilot(tmp_path, reset=True)

    assert result["read_customer"].status == "success"
    verification = verify_audit_chain(result["audit_path"], sink="sqlite")
    assert verification.valid is True


def test_cli_audit_query_filters_by_trace_id_and_tool_name(tmp_path, capsys):
    db_path = tmp_path / "audit.db"
    sink = SQLiteAuditSink(db_path)
    sink.write(
        {
            "event_type": "ToolCallRequested",
            "run_id": "run_1",
            "trace_id": "trace_1",
            "tool_name": "read_customer",
            "tool_call_id": "tc_1",
        }
    )
    sink.write(
        {
            "event_type": "ToolCallRequested",
            "run_id": "run_2",
            "trace_id": "trace_2",
            "tool_name": "write_customer",
            "tool_call_id": "tc_2",
        }
    )

    exit_code = main(["audit", "query", "--path", str(db_path), "--trace-id", "trace_1", "--tool-name", "read_customer"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "trace_1" in output
    assert "read_customer" in output
    assert "trace_2" not in output
    assert "write_customer" not in output


def test_runtime_classifies_executor_timeout_and_tool_error(tmp_path):
    config = {
        "version": 1,
        "default_decision": "deny",
        "audit": {"sink": "sqlite", "path": str(tmp_path / "audit.db")},
        "rules": [
            {"id": "allow-tools", "environment": "staging", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            {"id": "allow-python", "environment": "staging", "effect": "allow", "capabilities": ["command.execute:*"]},
        ],
    }
    runtime = AgentRuntime.from_dict(config)
    runtime.command_tool(
        name="slow_command",
        argv=[sys.executable, "-c", "import time; time.sleep(1)"],
        cwd=str(tmp_path),
        timeout_ms=10,
        capabilities_required=["tool.invoke:slow_command", "command.execute:python"],
    )

    @runtime.tool(name="broken_tool", capabilities_required=["tool.invoke:broken_tool"])
    def broken_tool():
        raise ValueError("broken")

    timeout = runtime.call_tool("slow_command", {}, actor={}, environment="staging")
    tool_error = runtime.call_tool("broken_tool", {}, actor={}, environment="staging")

    assert timeout.status == "error"
    assert timeout.error == "executor.timeout"
    assert tool_error.status == "error"
    assert tool_error.error == "tool.error"

    errors = [event["payload"]["error"] for event in SQLiteAuditSink(tmp_path / "audit.db").query() if event["event_type"] == "RuntimeError"]
    assert "executor.timeout" in errors
    assert "tool.error" in errors
