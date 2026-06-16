import json

from agent_runtime.certification import build_platform_ready_certification_report
from agent_runtime.cli.main import main


def test_build_platform_ready_certification_report_requires_evidence_for_candidates():
    report = build_platform_ready_certification_report()

    assert report.passed is True
    subjects = {cert.subject for cert in report.certifications}
    assert "openai_adapter" in subjects
    assert "container_backend" in subjects
    assert all(cert.evidence_refs for cert in report.certifications)


def test_cli_certify_run_outputs_platform_ready_certification_report(capsys):
    exit_code = main(["certify", "run", "--subject", "all"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["release"] == "platform_ready_runtime"
    assert any(item["subject"] == "control_plane_api" for item in payload["certifications"])
