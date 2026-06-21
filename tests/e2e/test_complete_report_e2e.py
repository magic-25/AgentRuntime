from examples.complete_runtime_report import build_complete_report


def test_complete_report_fake_provider_e2e(tmp_path):
    report = build_complete_report(tmp_path, provider_mode="fake")

    assert report["summary"]["provider_mode"] == "fake"
    assert report["summary"]["scenario_count"] >= 6
    assert (tmp_path / "complete-report.json").exists()
    assert (tmp_path / "complete-report.md").exists()
    assert (tmp_path / "complete-report.html").exists()
    assert (tmp_path / "complete-report.png").exists()

    scenario_ids = {scenario["id"] for scenario in report["scenarios"]}
    assert "provider_tool_call" in scenario_ids
    assert "production_incident" in scenario_ids

    production_incident = next(scenario for scenario in report["scenarios"] if scenario["id"] == "production_incident")
    assert production_incident["transcript"]["status"] == "completed_with_denial"
    assert production_incident["governance"]["sandbox"]["isolation_level"] == "strong"
    assert production_incident["governance"]["sandbox"]["status"] == "success"
    assert production_incident["governance"]["audit"]["status"] == "committed"
