from agent_runtime.release import production_release_manifest


def test_release_manifest_includes_1_3_adapter_matrix_and_guides():
    manifest = production_release_manifest()

    adapters = manifest["adapter_stabilization"]

    assert adapters["version"] == "1.3.0"
    assert adapters["compatibility_matrix"]["openai"]["support_level"] == "stable_candidate"
    assert adapters["compatibility_matrix"]["anthropic"]["support_level"] == "stable_candidate"
    assert adapters["compatibility_matrix"]["langgraph"]["support_level"] == "stable_candidate"
    assert adapters["compatibility_matrix"]["mcp"]["support_level"] == "stable_candidate"
    assert adapters["compatibility_matrix"]["codex_workspace"]["support_level"] == "stable_candidate"
    assert adapters["compatibility_matrix"]["codex_workflow"]["support_level"] == "preview"
    assert adapters["compatibility_matrix"]["codex_connectors"]["support_level"] == "experimental"
    assert "0.4_spike_to_1.3_adapter" in adapters["migration_guide"]
    assert "sandbox_required" in adapters["failure_mode_guide"]
    assert "codex_connectors" not in manifest["supported"]
