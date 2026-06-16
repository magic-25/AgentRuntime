import json
import sys

from agent_runtime.cli.main import main


def test_cli_contrib_list_shows_builtin_packs_disabled_by_default(capsys):
    exit_code = main(["contrib", "list"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    openai = next(pack for pack in payload["packs"] if pack["pack_id"] == "openai")
    assert openai["enabled"] is False
    assert openai["disabled_reason"] == "not_allowlisted"


def test_cli_conformance_run_dry_run_reports_preview_packs(capsys):
    exit_code = main(["conformance", "run", "--pack", "all", "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert any(report["pack_id"] == "openai" for report in payload["reports"])


def test_cli_pilot_code_ci_runs_allowlisted_command(tmp_path, capsys):
    report_path = tmp_path / "pilot-report.json"
    command = f"{sys.executable} -c \"print('ok')\""

    exit_code = main(
        [
            "pilot",
            "code-ci",
            "--repo",
            str(tmp_path),
            "--command",
            command,
            "--allow-command",
            command,
            "--write-scope",
            str(tmp_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert report_path.exists()
