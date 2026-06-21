from agent_runtime.release import production_release_manifest


def test_release_manifest_includes_1_1_extension_pilot_without_promoting_to_supported():
    manifest = production_release_manifest()

    extension = manifest["extension_pilot"]

    assert manifest["version"] == "1.0.0"
    assert extension["version"] == "1.1.0"
    assert extension["support_level"] == "extension_pilot"
    assert "openai_adapter_pack" in extension["preview"]
    assert "openai_adapter_pack" not in manifest["supported"]
