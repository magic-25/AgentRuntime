import json

from agent_runtime.cli.main import main
from agent_runtime_contrib.adapter_conformance import AdapterConformanceRunner


def test_adapter_replay_reports_three_code_ci_paths():
    report = AdapterConformanceRunner().run_replay("code-ci", adapter_ids=["openai", "langgraph", "codex"])

    assert report.passed is True
    assert report.scenario == "code-ci"
    assert {item["adapter"] for item in report.paths} == {"openai", "langgraph", "codex"}
    assert all(item["runtime_semantics"] == "policy_audit_sandbox_preserved" for item in report.paths)


def test_cli_adapter_replay_outputs_json(capsys):
    exit_code = main(["adapter", "replay", "--scenario", "code-ci", "--adapter", "openai", "--adapter", "langgraph", "--adapter", "codex"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["scenario"] == "code-ci"
    assert len(payload["paths"]) == 3
