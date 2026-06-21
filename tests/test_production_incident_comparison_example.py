from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_comparison_module():
    module_path = Path(__file__).resolve().parents[1] / "examples" / "production_incident_comparison.py"
    spec = importlib.util.spec_from_file_location("production_incident_comparison", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_production_incident_comparison_runs_direct_and_registered_paths(tmp_path):
    module = _load_comparison_module()

    report = module.build_production_incident_comparison(tmp_path)

    assert report["agent"]["name"] == "Production Incident Agent"
    assert report["direct"]["registration"] == "unregistered"
    assert report["direct"]["status"] == "completed"
    assert report["direct"]["audit_events"] == []
    assert report["direct"]["tool_result_statuses"] == ["success", "success", "success", "success", "success", "success"]
    assert report["direct"]["tool_run_ids"] == [None, None, None, None, None, None]

    assert report["registered"]["registration"] == "registered"
    assert report["registered"]["status"] == "completed_with_denial"
    assert report["registered"]["tool_result_statuses"] == [
        "success",
        "success",
        "success",
        "success",
        "success",
        "denied",
    ]
    assert "AgentRegistered" in report["registered"]["audit_events"]
    assert "AgentRunFinished" in report["registered"]["audit_events"]
    assert all(run_id for run_id in report["registered"]["tool_run_ids"])

    assert report["comparison"]["policy_enforced"] is True
    assert report["comparison"]["approval_enforced"] is True
    assert report["comparison"]["sandbox_enforced"] is True
    assert report["comparison"]["audit_available"] is True
    assert report["comparison"]["direct_hotfix_applied"] is True
    assert report["comparison"]["registered_hotfix_blocked"] is True

    comparison_path = tmp_path / "comparison.json"
    run_view_path = tmp_path / "registered-run-view.html"
    audit_path = tmp_path / "registered-audit.jsonl"
    assert json.loads(comparison_path.read_text(encoding="utf-8"))["comparison"] == report["comparison"]
    assert "这个 Agent 是做什么的" in run_view_path.read_text(encoding="utf-8")
    assert "AgentRegistered" in audit_path.read_text(encoding="utf-8")
