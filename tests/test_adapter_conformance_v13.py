import json

from agent_runtime.cli.main import main
from agent_runtime_contrib.adapter_conformance import AdapterConformanceRunner


def test_adapter_conformance_runner_passes_stable_candidate_set_and_replay_paths():
    report = AdapterConformanceRunner().run_all()

    assert report.passed is True
    assert {"openai", "anthropic", "langgraph", "mcp", "codex"} <= set(report.adapters)
    assert all(item["support_level"] == "stable_candidate" for item in report.adapters.values())
    assert {"replay.openai", "replay.langgraph", "replay.codex"} <= set(report.replay_paths)


def test_cli_adapter_conformance_dry_run_reports_json(capsys):
    exit_code = main(["adapter", "conformance", "--adapter", "all", "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["report"]["passed"] is True
    assert "openai" in payload["report"]["adapters"]
