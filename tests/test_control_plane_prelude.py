from agent_runtime.control_plane.prelude import (
    AuditForwardingTarget,
    PackEnablement,
    PolicyBundle,
    RuntimeRun,
)


def test_control_plane_prelude_defines_contract_models_without_service_side_effects():
    run = RuntimeRun(run_id="run_1", environment="dev", status="created")
    bundle = PolicyBundle(bundle_id="policy_1", version=1, default_decision="deny")
    pack = PackEnablement(pack_id="openai", enabled=False, reason="not_allowlisted")
    target = AuditForwardingTarget(target_id="local", kind="jsonl", enabled=False)

    assert run.run_id == "run_1"
    assert bundle.default_decision == "deny"
    assert pack.enabled is False
    assert target.kind == "jsonl"
