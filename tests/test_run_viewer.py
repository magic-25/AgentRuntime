from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from agent_runtime.run_view import build_run_view_from_audit, load_scenario_snapshot, render_run_view_html


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


def test_run_view_model_reconstructs_complete_runtime_process(tmp_path):
    module = _load_agent_run_screenshot_module()
    snapshot = module.build_agent_run_screenshot(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "real-provider-agent-run-audit.jsonl"

    view = build_run_view_from_audit(audit_path, snapshot=snapshot)

    assert view["title"] == "Agent Runtime Run Viewer"
    assert view["overview"]["agent_id"] == "runtime-screenshot-agent"
    assert view["overview"]["provider"] == "fake-glm"
    assert view["overview"]["status"] == "completed"
    assert view["input"]["prompt"] == "Call the echo tool exactly once with message 'runtime screenshot'."
    assert view["agent_decision"]["tool_name"] == "echo"
    assert view["agent_decision"]["arguments"] == {"message": "runtime screenshot"}
    assert view["governance"]["policy"]["decision"] == "allow"
    assert view["governance"]["policy"]["reason"] == "matched_rule"
    assert view["governance"]["audit"]["status"] == "committed"
    assert view["tool_calls"][0]["tool_name"] == "echo"
    assert view["tool_calls"][0]["input"] == {"message": "runtime screenshot"}
    assert view["tool_calls"][0]["result"]["status"] == "success"
    assert view["tool_calls"][0]["result"]["output"] == {"message": "runtime screenshot"}
    assert [step["event_type"] for step in view["timeline"]] == [
        "AgentRegistered",
        "AgentRunStarted",
        "TraceSpanStarted",
        "ToolCallRequested",
        "TraceSpanStarted",
        "TraceSpanStarted",
        "TraceSpanFinished",
        "PolicyEvaluated",
        "ToolExecutionStarted",
        "ToolExecutionFinished",
        "TraceSpanFinished",
        "AgentRunFinished",
        "TraceSpanFinished",
    ]

    trace_root = view["trace_tree"][0]
    assert trace_root["span_kind"] == "agent_run"
    assert trace_root["status"] == "completed"
    assert {child["span_kind"] for child in trace_root["children"]} >= {"tool_call", "policy_evaluation"}
    assert len(view["raw_events"]) == 13


def test_run_view_html_shows_complete_process_sections(tmp_path):
    module = _load_agent_run_screenshot_module()
    snapshot = module.build_agent_run_screenshot(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "real-provider-agent-run-audit.jsonl"
    view = build_run_view_from_audit(audit_path, snapshot=snapshot)

    html = render_run_view_html(view)

    assert "完整运行过程可视化" in html
    assert "Run Overview" in html
    assert "Input" in html
    assert "Agent Decision" in html
    assert "Runtime Governance" in html
    assert "Execution Timeline" in html
    assert "Tool Calls" in html
    assert "Trace Tree" in html
    assert "Raw Evidence" in html
    assert "为什么允许/拒绝" in html
    assert "runtime screenshot" in html
    assert "matched_rule" in html
    assert "TraceSpanFinished" in html
    assert "&quot;message&quot;: &quot;runtime screenshot&quot;" in html


def test_run_view_html_renders_json_as_beauty_view(tmp_path):
    module = _load_agent_run_screenshot_module()
    snapshot = module.build_agent_run_screenshot(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "real-provider-agent-run-audit.jsonl"
    view = build_run_view_from_audit(audit_path, snapshot=snapshot)

    html = render_run_view_html(view)

    assert 'class="json-beauty"' in html
    assert 'class="json-key"' in html
    assert 'class="json-string"' in html
    assert 'class="json-boolean"' in html
    assert 'class="json-null"' in html
    assert '"message"' not in html
    assert "&quot;message&quot;" in html


def test_run_view_can_render_complete_report_scenario_context(tmp_path):
    module = _load_complete_report_module()
    module.build_complete_report(tmp_path, provider_mode="fake")
    audit_path = tmp_path / "production_incident-audit.jsonl"
    report_path = tmp_path / "complete-report.json"
    snapshot = load_scenario_snapshot(report_path, "production_incident")

    view = build_run_view_from_audit(audit_path, snapshot=snapshot)
    html = render_run_view_html(view)

    assert view["input"]["prompt"] == "investigate checkout production latency"
    assert view["agent_context"]["purpose"].startswith("Shows a production-grade incident loop")
    assert view["agent_context"]["phases"] == [
        "intake",
        "investigate",
        "diagnose",
        "remediate",
        "guardrail",
        "summarize",
    ]
    assert view["agent_context"]["findings"]["impact"] == "checkout-api degraded in us-east-1"
    assert view["agent_context"]["remediation"]["approved_action"] == "rollback"
    assert view["agent_context"]["remediation"]["blocked_action"] == "apply_hotfix"
    assert "Production Incident Agent" in html
    assert "这个 Agent 是做什么的" in html
    assert "模拟生产 incident 排障" in html
    assert "为什么用它测试 runtime" in html
    assert "Agent Run Report" in html
    assert "metric-label\">Prompt" in html
    assert "Prompt" in html
    assert "investigate checkout production latency" in html
    assert "Agent Phases" in html
    assert "Findings" in html
    assert "Remediation" in html
    assert "checkout-api degraded in us-east-1" in html
    assert "apply_hotfix" in html
    assert "<code>n/a</code>" not in html
