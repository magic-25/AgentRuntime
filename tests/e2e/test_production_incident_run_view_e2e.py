import json

from examples.production_incident_comparison import build_production_incident_comparison


def test_production_incident_run_view_e2e(tmp_path):
    report = build_production_incident_comparison(tmp_path)

    assert report["comparison"]["direct_hotfix_applied"] is True
    assert report["comparison"]["registered_hotfix_blocked"] is True
    assert report["comparison"]["registered_deny_no_direct_fallback"] is True
    assert report["comparison"]["policy_enforced"] is True
    assert report["comparison"]["sandbox_enforced"] is True
    assert report["comparison"]["audit_available"] is True

    comparison_json = tmp_path / "comparison.json"
    audit_path = tmp_path / "registered-audit.jsonl"
    run_view = tmp_path / "registered-run-view.html"

    assert comparison_json.exists()
    assert audit_path.exists()
    assert run_view.exists()

    persisted = json.loads(comparison_json.read_text(encoding="utf-8"))
    assert persisted["registered"]["status"] == "completed_with_denial"
    assert persisted["direct"]["tool_outputs"][-1]["execution_path"] == "direct-only"
    assert persisted["registered"]["tool_outputs"][-1] == {"status": "denied", "error": "matched_rule"}
    assert "direct-only" not in json.dumps(persisted["registered"], ensure_ascii=False)
    assert "SandboxEnforced" in persisted["registered"]["audit_events"]

    html = run_view.read_text(encoding="utf-8")
    assert "Production Incident Agent" in html
    assert "Investigate checkout production latency" in html
    assert "Policy" in html
    assert "Sandbox" in html
    assert "Trace Tree" in html
    assert "Raw Evidence" in html
