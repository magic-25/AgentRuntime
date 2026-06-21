from examples.complete_runtime_report import build_complete_report
from agent_runtime.run_view import load_scenario_snapshot, write_run_view_html


def test_run_view_browser_evidence_e2e(tmp_path):
    report = build_complete_report(tmp_path, provider_mode="fake")
    snapshot = load_scenario_snapshot(tmp_path / "complete-report.json", "production_incident")
    run_view_path = tmp_path / "production-incident-run-view.html"

    output = write_run_view_html(
        tmp_path / "production_incident-audit.jsonl",
        run_view_path,
        snapshot=snapshot,
    )

    assert output["event_count"] > 0
    assert output["trace_id"]
    assert run_view_path.exists()

    html = run_view_path.read_text(encoding="utf-8")
    complete_report_html = (tmp_path / "complete-report.html").read_text(encoding="utf-8")
    screenshot = tmp_path / "complete-report.png"

    assert report["summary"]["provider_mode"] == "fake"
    assert screenshot.exists()
    assert screenshot.stat().st_size > 0

    for expected in [
        "Production Incident Agent",
        "这个 Agent 是做什么的",
        "Agent Run Report",
        "Runtime Governance",
        "Execution Timeline",
        "Tool Calls",
        "Trace Tree",
        "Raw Evidence",
        "json-beauty",
        "Policy",
        "Approval",
        "Sandbox",
        "Audit",
        "apply_hotfix",
        "matched_rule",
        "checkout-api degraded in us-east-1",
    ]:
        assert expected in html

    assert "真实 provider + governed trace" in complete_report_html
    assert "Provider Tool Calling Agent" in complete_report_html
    assert "Policy Deny Agent" in complete_report_html
    assert "Sandboxed Command Agent" in complete_report_html
