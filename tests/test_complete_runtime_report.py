from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from agent_runtime.reporting.complete_report import _render_html


def _load_complete_report_module():
    module_path = Path(__file__).resolve().parents[1] / "examples" / "complete_runtime_report.py"
    spec = importlib.util.spec_from_file_location("complete_runtime_report", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_runtime_report_generates_multi_agent_runtime_outputs(tmp_path):
    module = _load_complete_report_module()

    report = module.build_complete_report(tmp_path, provider_mode="fake")

    assert report["report_type"] == "complete_runtime_report"
    assert report["product"] == "Agent Runtime"
    assert report["summary"]["scenario_count"] == 6
    assert report["summary"]["provider_mode"] == "fake"
    assert report["summary"]["questions_answered"] == [
        "agent做了什么",
        "为什么允许、为什么拒绝、是否经过approval、是否强隔离、是否可审计",
    ]

    scenarios = {scenario["id"]: scenario for scenario in report["scenarios"]}
    assert set(scenarios) == {
        "scripted_echo",
        "provider_tool_call",
        "policy_deny",
        "approval_gate",
        "sandboxed_command",
        "production_incident",
    }

    assert scenarios["scripted_echo"]["transcript"]["status"] == "completed"
    assert scenarios["scripted_echo"]["tool_results"][0]["output"] == {"message": "hello from scripted agent"}
    assert scenarios["scripted_echo"]["governance"]["policy"]["decision"] == "allow"
    assert scenarios["scripted_echo"]["governance"]["audit"]["status"] == "committed"

    assert scenarios["provider_tool_call"]["agent"]["framework"] == "openai-compatible"
    assert scenarios["provider_tool_call"]["transcript"]["raw_tool_name"] == "echo"
    assert scenarios["provider_tool_call"]["tool_results"][0]["status"] == "success"

    assert scenarios["policy_deny"]["transcript"]["status"] == "blocked"
    assert scenarios["policy_deny"]["tool_results"][0]["status"] == "denied"
    assert scenarios["policy_deny"]["governance"]["policy"]["decision"] == "deny"
    assert scenarios["policy_deny"]["governance"]["execution"]["tool_executed"] is False

    assert scenarios["approval_gate"]["governance"]["approval"]["approved"] is True
    assert scenarios["approval_gate"]["trace"]["contains"]["approval_gate"] is True

    assert scenarios["sandboxed_command"]["governance"]["sandbox"]["isolation_level"] == "strong"
    assert scenarios["sandboxed_command"]["governance"]["sandbox"]["backend"] == "complete-report-sandbox"
    assert scenarios["sandboxed_command"]["trace"]["contains"]["sandbox_execution"] is True

    assert scenarios["production_incident"]["agent"]["framework"] == "state-machine-python"
    assert scenarios["production_incident"]["transcript"]["status"] == "completed_with_denial"
    assert scenarios["production_incident"]["transcript"]["phases"] == [
        "intake",
        "investigate",
        "diagnose",
        "remediate",
        "guardrail",
        "summarize",
    ]
    assert scenarios["production_incident"]["transcript"]["findings"]["impact"] == "checkout-api degraded in us-east-1"
    assert scenarios["production_incident"]["transcript"]["remediation"]["approved_action"] == "rollback"
    assert scenarios["production_incident"]["transcript"]["remediation"]["blocked_action"] == "apply_hotfix"
    assert len(scenarios["production_incident"]["tool_results"]) == 6
    assert scenarios["production_incident"]["governance"]["approval"]["approved"] is True
    assert scenarios["production_incident"]["governance"]["sandbox"]["isolation_level"] == "strong"
    assert scenarios["production_incident"]["governance"]["policy"]["decision"] == "deny"

    for scenario in scenarios.values():
        assert scenario["trace"]["trace_id"]
        assert scenario["trace"]["contains"]["agent_run"] is True
        assert scenario["trace"]["contains"]["tool_call"] is True
        assert scenario["trace"]["contains"]["policy_evaluation"] is True
        assert scenario["governance"]["audit"]["event_count"] > 0

    json_path = tmp_path / "complete-report.json"
    markdown_path = tmp_path / "complete-report.md"
    html_path = tmp_path / "complete-report.html"
    screenshot_path = tmp_path / "complete-report.png"
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"] == report["summary"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Agent Runtime Complete Report" in markdown
    assert "Governed Trace" in markdown
    assert "真实 provider" in html_path.read_text(encoding="utf-8")
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0


def test_complete_runtime_report_html_escapes_dynamic_values():
    report = {
        "summary": {"scenario_count": 1, "provider_mode": "fake"},
        "scenarios": [
            {
                "title": "<script>alert(1)</script>",
                "purpose": "<img src=x onerror=alert(2)>",
                "agent": {"agent_id": "agent<script>x</script>", "framework": "fw<script>y</script>"},
                "transcript": {"status": "completed<script>z</script>"},
                "tool_results": [{"status": "success", "output": {"message": "<script>alert(3)</script>"}}],
                "governance": {
                    "policy": {"decision": "allow", "reason": "<script>alert(4)</script>"},
                    "approval": {"status": None},
                    "sandbox": {"isolation_level": None, "backend": None},
                    "audit": {"status": "committed", "event_count": 1},
                },
                "trace": {"trace_id": "trace<script>alert(5)</script>"},
            }
        ],
    }

    html = _render_html(report)

    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;script&gt;alert(3)&lt;/script&gt;" in html
