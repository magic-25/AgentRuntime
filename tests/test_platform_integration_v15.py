import json

import pytest

from agent_runtime.cli.main import main
from agent_runtime.control_plane.platform import (
    AppendOnlyAuditForwarder,
    PlatformIntegrationError,
    PlatformPolicyBundle,
    PlatformRegistryContract,
    PlatformSimulationHarness,
    RunExporter,
    evaluate_platform_policy_state,
    validate_policy_bundle,
)


def test_runtime_core_remains_independent_without_platform():
    from agent_runtime.policy.engine import PolicyEngine

    assert PolicyEngine is not None


def test_policy_registry_bundle_validates_locally_and_rejects_invalid_bundle():
    bundle = PlatformPolicyBundle(
        bundle_id="bundle-1",
        version=1,
        policy_config={"version": 1, "default_decision": "deny", "rules": []},
    )

    assert validate_policy_bundle(bundle).bundle_id == "bundle-1"

    with pytest.raises(PlatformIntegrationError, match="policy.bundle.invalid"):
        validate_policy_bundle(
            PlatformPolicyBundle(bundle_id="bad", version=1, policy_config={"version": 1, "default_decision": "maybe"})
        )


def test_platform_unavailable_or_stale_policy_fails_closed_in_prod_unless_explicit_degrade():
    unavailable = evaluate_platform_policy_state(environment="prod", platform_available=False, policy_stale=False)
    stale = evaluate_platform_policy_state(environment="prod", platform_available=True, policy_stale=True)
    degraded = evaluate_platform_policy_state(
        environment="prod", platform_available=False, policy_stale=False, explicit_degrade=True
    )

    assert unavailable.decision == "deny"
    assert unavailable.reason == "platform.unavailable"
    assert unavailable.fail_closed is True
    assert stale.decision == "deny"
    assert stale.reason == "policy.stale"
    assert degraded.decision == "degrade"
    assert degraded.degraded is True


def test_audit_forwarding_failure_does_not_mutate_local_hash_chain():
    forwarder = AppendOnlyAuditForwarder(fail_forwarding=True)
    before = ["hash-1", "hash-2"]

    result = forwarder.forward(event={"type": "ToolCalled"}, local_hash_chain=before)

    assert result.forwarded is False
    assert result.reason == "forwarding.failed"
    assert result.local_hash_chain == before


def test_run_export_redacts_payload_by_default():
    exported = RunExporter().export_run(
        run_id="run-1",
        payload={"prompt": "secret", "token": "abc"},
        include_full_payload=False,
    )

    assert exported["run_id"] == "run-1"
    assert exported["payload"] == {"redacted": True}
    assert "secret" not in json.dumps(exported)


def test_registry_contract_never_auto_enables_pack_and_remote_disabled_wins():
    contract = PlatformRegistryContract(remote_disabled=["openai"], local_allowlist=["openai", "mcp"])

    openai = contract.resolve("openai")
    mcp = contract.resolve("mcp")
    anthropic = contract.resolve("anthropic")

    assert openai.enabled is False
    assert openai.reason == "disabled_remotely"
    assert mcp.enabled is True
    assert anthropic.enabled is False
    assert anthropic.reason == "not_allowlisted"


def test_platform_simulation_harness_covers_required_failure_modes():
    report = PlatformSimulationHarness().run_all()

    assert report.passed is True
    assert set(report.scenarios) == {
        "platform_unavailable",
        "policy_stale",
        "audit_forwarding_failed",
        "registry_mismatch",
        "disabled_remotely",
    }


def test_cli_platform_simulation_reports_json(capsys):
    exit_code = main(["platform", "simulate", "--scenario", "all"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert "platform_unavailable" in payload["scenarios"]
