import json

from agent_runtime.cli.main import main


def test_policy_config_schema_exports_release_candidate_contract():
    from agent_runtime.schema.policy_config import policy_config_schema

    schema = policy_config_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "Agent Runtime Policy Config"
    assert schema["properties"]["version"]["const"] == 1
    assert "default_decision" in schema["required"]
    assert "rules" in schema["required"]
    assert schema["properties"]["default_decision"]["enum"] == ["allow", "deny"]
    assert "audit" in schema["properties"]
    assert "tracing" in schema["properties"]
    assert "redaction" in schema["properties"]
    json.dumps(schema)


def test_cli_exports_policy_config_schema(tmp_path):
    output_path = tmp_path / "policy-config.schema.json"

    exit_code = main(["schema", "export", "--type", "policy-config", "--output", str(output_path)])

    assert exit_code == 0
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["title"] == "Agent Runtime Policy Config"
    assert schema["properties"]["rules"]["type"] == "array"


def test_release_candidate_public_api_contract_resolves_symbols():
    from agent_runtime.compatibility import experimental_public_api, stable_public_api

    stable = stable_public_api()
    experimental = experimental_public_api()

    assert "agent_runtime.AgentRuntime" in stable
    assert "agent_runtime.core.models.ToolCall" in stable
    assert "agent_runtime.audit.sqlite.SQLiteAuditSink" in stable
    assert "agent_runtime.execution.sandbox.SandboxExecutor" in stable
    assert "agent_runtime.execution.sandbox.SandboxCommandSpec" in stable
    assert "agent_runtime.adapters.mcp_style.MCPStyleAdapter" in experimental
    assert all(entry["status"] == "stable" for entry in stable.values())
    assert all(entry["status"] == "experimental" for entry in experimental.values())
