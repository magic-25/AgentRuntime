from agent_runtime.release import production_release_manifest


def test_release_manifest_includes_1_5_platform_integration_preview_contracts():
    manifest = production_release_manifest()

    platform = manifest["platform_integration_preview"]

    assert platform["version"] == "1.5.0"
    assert platform["support_level"] == "preview"
    assert "policy_registry_contract" in platform["contracts"]
    assert "audit_forwarding_contract" in platform["contracts"]
    assert "run_export_contract" in platform["contracts"]
    assert "adapter_backend_registry_contract" in platform["contracts"]
    assert platform["prod_failure_semantics"]["platform_unavailable"] == "fail_closed"
    assert platform["prod_failure_semantics"]["policy_stale"] == "fail_closed"
    assert platform["run_export"]["full_payload_default"] == "disabled"
    assert "hosted_control_plane" not in manifest["supported"]
