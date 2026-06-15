import json

from agent_runtime.cli.main import main


def test_cli_init_writes_default_config(tmp_path):
    config_path = tmp_path / "agent-runtime.json"

    exit_code = main(["init", "--path", str(config_path)])

    assert exit_code == 0
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["default_decision"] == "deny"


def test_cli_validate_rejects_invalid_config(tmp_path):
    config_path = tmp_path / "bad.json"
    config_path.write_text("{}", encoding="utf-8")

    exit_code = main(["validate", "--path", str(config_path)])

    assert exit_code == 1


def test_cli_validate_requires_policy_config_schema_version(tmp_path, capsys):
    config_path = tmp_path / "agent-runtime.json"
    config_path.write_text('{"default_decision": "deny", "rules": []}', encoding="utf-8")

    exit_code = main(["validate", "--path", str(config_path)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "version" in output
    assert "1" in output


def test_cli_audit_tail_prints_recent_events(tmp_path, capsys):
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text('{"event_type": "ToolCallRequested"}\n', encoding="utf-8")

    exit_code = main(["audit", "tail", "--path", str(audit_path)])

    assert exit_code == 0
    assert "ToolCallRequested" in capsys.readouterr().out
