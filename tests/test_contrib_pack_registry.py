import pytest

from agent_runtime_contrib.packs.base import PackMetadata, PackRegistry, PackValidationError


def test_pack_registry_keeps_discovered_pack_disabled_without_allowlist():
    metadata = PackMetadata(pack_id="openai", kind="adapter", support_level="preview", dependencies_group="openai")
    registry = PackRegistry([metadata], allowlist=[])

    result = registry.resolve()

    assert result.enabled == []
    assert result.disabled["openai"] == "not_allowlisted"


def test_pack_registry_enables_only_explicitly_allowlisted_pack():
    openai = PackMetadata(pack_id="openai", kind="adapter", support_level="preview", dependencies_group="openai")
    mcp = PackMetadata(pack_id="mcp", kind="adapter", support_level="preview", dependencies_group="mcp")
    registry = PackRegistry([openai, mcp], allowlist=["mcp"])

    result = registry.resolve()

    assert [pack.pack_id for pack in result.enabled] == ["mcp"]
    assert result.disabled["openai"] == "not_allowlisted"


def test_pack_metadata_rejects_default_enabled_pack():
    with pytest.raises(PackValidationError, match="default_enabled"):
        PackMetadata(
            pack_id="unsafe",
            kind="adapter",
            support_level="preview",
            dependencies_group="unsafe",
            default_enabled=True,
        )


def test_pack_metadata_rejects_unknown_support_level():
    with pytest.raises(PackValidationError, match="support_level"):
        PackMetadata(pack_id="unknown", kind="adapter", support_level="stable", dependencies_group="unknown")
