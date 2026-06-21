from pathlib import Path


def test_e2e_plan_declares_required_paths():
    plan = Path("E2E_TEST_PLAN.md").read_text(encoding="utf-8")

    assert "E2E-001" in plan
    assert "clean wheel install" in plan
    assert "E2E-002" in plan
    assert "production incident run view" in plan
    assert "E2E-003" in plan
    assert "Docker sandbox runtime" in plan
    assert "E2E-004" in plan
    assert "complete report fake provider" in plan
    assert "E2E-MANUAL-001" in plan
    assert "real provider key" in plan


def test_e2e_pytest_suite_exists():
    e2e_dir = Path("tests/e2e")

    assert (e2e_dir / "test_clean_wheel_install.py").exists()
    assert (e2e_dir / "test_production_incident_run_view_e2e.py").exists()
    assert (e2e_dir / "test_docker_sandbox_runtime_e2e.py").exists()
    assert (e2e_dir / "test_complete_report_e2e.py").exists()
