import json

from agent_runtime.cli.main import main


def test_production_release_manifest_declares_supported_and_experimental_boundaries():
    from agent_runtime.release import production_release_manifest

    manifest = production_release_manifest()

    assert manifest["version"] == "1.0.0"
    assert manifest["support_level"] == "production_core"
    assert "python_sdk_core" in manifest["supported"]
    assert "policy_config_schema_v1" in manifest["supported"]
    assert "sqlite_audit_sink" in manifest["supported"]
    assert "approval_provider_interface" in manifest["supported"]
    assert "stable_public_api" in manifest["supported"]
    assert "sandbox_provider_interface" in manifest["supported"]
    assert "tamper_evident_audit_chain" in manifest["supported"]
    assert "audit_chain_verifier" in manifest["supported"]
    assert "openai_style_adapter" in manifest["experimental"]
    assert "mcp_style_adapter" in manifest["experimental"]
    assert "weak_subprocess_for_high_risk_prod" in manifest["unsupported"]
    assert "strong_sandbox_guarantee" not in manifest["unsupported"]
    assert manifest["security_defaults"]["unknown_tool"] == "deny"
    assert manifest["security_defaults"]["approval_timeout"] == "reject"
    assert manifest["security_defaults"]["prod_post_execution_audit_write_failure"] == "return_error"
    json.dumps(manifest)


def test_cli_release_status_outputs_manifest(capsys):
    exit_code = main(["release", "status"])

    assert exit_code == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["version"] == "1.0.0"
    assert manifest["support_level"] == "production_core"
