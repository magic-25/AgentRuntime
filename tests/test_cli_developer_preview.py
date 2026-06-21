import json
import importlib.util
import sys
from pathlib import Path

from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.cli.main import main


def _load_agent_run_screenshot_module():
    module_path = Path(__file__).resolve().parents[1] / "examples" / "agent_run_screenshot.py"
    spec = importlib.util.spec_from_file_location("agent_run_screenshot", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_complete_report_module():
    module_path = Path(__file__).resolve().parents[1] / "examples" / "complete_runtime_report.py"
    spec = importlib.util.spec_from_file_location("complete_runtime_report", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_cli_run_view_writes_complete_process_html(tmp_path):
    module = _load_agent_run_screenshot_module()
    module.build_agent_run_screenshot(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "real-provider-agent-run-audit.jsonl"
    snapshot_path = tmp_path / "real-provider-agent-run.json"
    output_path = tmp_path / "run-view.html"

    exit_code = main(
        [
            "run",
            "view",
            "--audit",
            str(audit_path),
            "--snapshot",
            str(snapshot_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    html = output_path.read_text(encoding="utf-8")
    assert "完整运行过程可视化" in html
    assert "Execution Timeline" in html
    assert "Trace Tree" in html
    assert "runtime screenshot" in html


def test_cli_run_view_uses_complete_report_scenario_context(tmp_path):
    module = _load_complete_report_module()
    module.build_complete_report(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "production_incident-audit.jsonl"
    report_path = tmp_path / "complete-report.json"
    output_path = tmp_path / "production-incident-view.html"

    exit_code = main(
        [
            "run",
            "view",
            "--audit",
            str(audit_path),
            "--report",
            str(report_path),
            "--scenario",
            "production_incident",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    html = output_path.read_text(encoding="utf-8")
    assert "Agent Run Report" in html
    assert "investigate checkout production latency" in html
    assert "Agent Phases" in html
    assert "checkout-api degraded in us-east-1" in html
    assert "approved_action" in html
    assert "apply_hotfix" in html
    assert "<code>n/a</code>" not in html
